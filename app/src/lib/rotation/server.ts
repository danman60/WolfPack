import { createHash } from 'node:crypto';
import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import type { Portfolio, MarketSnapshot } from './contract';
import { RotationValidationError, validatePortfolio } from './engine';

const ACCESS = 'wpr_access';
const REFRESH = 'wpr_refresh';
export type RotationUser = { id: string; email: string; demo: boolean; accessToken: string };
export class ApiError extends Error { constructor(message: string, public status = 400) { super(message); } }
export function config() {
  const url = process.env.WPR_SUPABASE_URL;
  const anon = process.env.WPR_SUPABASE_ANON_KEY;
  const service = process.env.WPR_SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !anon || !service) throw new ApiError('Rotation workshop connection is not configured.', 503);
  return { url: url.replace(/\/$/, ''), anon, service };
}
export function response(value: unknown, status = 200) { return NextResponse.json(value, { status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } }); }
export function apiError(error: unknown) {
  const correlationId = crypto.randomUUID();
  let status: number; let message: string;
  if (error instanceof ApiError) { status = error.status; message = error.message; }
  else if (error instanceof RotationValidationError) { status = 400; message = error.message; }
  else {
    status = error instanceof Error && /fetch failed|timeout|network/i.test(error.message) ? 503 : 500;
    message = status === 503 ? 'Rotation service is temporarily unreachable. Retry shortly.' : 'Rotation request failed. Keep this reference if you need help.';
    // Never log request bodies, credentials, URLs, SQL or arbitrary exception text.
    console.error(JSON.stringify({ event: 'rotation_request_failed', correlationId, status, errorType: error instanceof Error ? error.constructor.name : typeof error }));
  }
  const result = response({ error: message, correlationId }, status);
  result.headers.set('X-Request-ID', correlationId);
  return result;
}
/** Private handlers use this base so authentication is applied before route logic. */
export function protectedRoute(handler: (request: Request, user: RotationUser) => Promise<NextResponse>) {
  return async (request: Request): Promise<NextResponse> => {
    try { return await handler(request, await requireUser()); }
    catch (error) { return apiError(error); }
  };
}
export function requireSameOrigin(request: Request): void {
  const origin = request.headers.get('origin');
  // Next may normalize request.url to its bind hostname (localhost) while the
  // browser uses 127.0.0.1. Host is the actual HTTP authority browsers cannot set.
  const host = request.headers.get('host');
  const protocol = new URL(request.url).protocol;
  if (!origin || !host || origin !== `${protocol}//${host}`) throw new ApiError('A same-origin request is required.', 403);
  if (request.headers.get('sec-fetch-site') === 'cross-site') throw new ApiError('Cross-site request rejected.', 403);
}
export async function readBody<T extends Record<string, unknown> = Record<string, unknown>>(request: Request, maxBytes = 128_000): Promise<T> {
  if (maxBytes > 512_000 || maxBytes < 1) throw new ApiError('Invalid request size limit.', 500);
  if (!request.headers.get('content-type')?.includes('application/json')) throw new ApiError('JSON request required.', 415);
  const declared = Number(request.headers.get('content-length') ?? 0);
  if (!Number.isFinite(declared) || declared > maxBytes) throw new ApiError('Request is too large.', 413);
  const reader = request.body?.getReader();
  if (!reader) throw new ApiError('JSON body required.');
  const chunks: Uint8Array[] = []; let total = 0;
  while (true) {
    const part = await reader.read();
    if (part.done) break;
    total += part.value.byteLength;
    if (total > maxBytes) { await reader.cancel(); throw new ApiError('Request is too large.', 413); }
    chunks.push(part.value);
  }
  const raw = Buffer.concat(chunks).toString('utf8');
  let value: unknown;
  try { value = JSON.parse(raw); } catch { throw new ApiError('Invalid JSON request.'); }
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ApiError('JSON object required.');
  return value as T;
}
export async function dbRequest<T>(path: string, init: RequestInit = {}, accessToken?: string): Promise<T> {
  if (!path.startsWith('wpr_') && !path.startsWith('rpc/wpr_')) throw new ApiError('Rotation database scope rejected.', 500);
  const cfg = config();
  const result = await fetch(`${cfg.url}/rest/v1/${path}`, { ...init, cache: 'no-store', signal: AbortSignal.timeout(15_000), headers: {
    apikey: accessToken ? cfg.anon : cfg.service, Authorization: `Bearer ${accessToken ?? cfg.service}`, 'Content-Type': 'application/json', Prefer: 'return=representation', ...init.headers,
  } });
  const body = await result.json().catch(() => null);
  if (!result.ok) {
    if (body?.code === '23505' || body?.code === '40001') throw new ApiError('Portfolio or record changed. Reload before continuing; an approval cannot run twice.', 409);
    if (result.status === 401 || result.status === 403) throw new ApiError('Rotation database access was refused.', 403);
    // Do not return SQL detail, schema internals, query values or credentials.
    throw new ApiError('Workshop could not complete this request. Saved data was not replaced.', 503);
  }
  return body as T;
}
async function authRequest(path: string, init: RequestInit = {}, token?: string) {
  const cfg = config();
  return fetch(`${cfg.url}/auth/v1/${path}`, { ...init, cache: 'no-store', signal: AbortSignal.timeout(15_000), headers: { apikey: cfg.anon, 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers } });
}
async function storeSession(session: { access_token?: string; refresh_token?: string; expires_in?: number }) {
  if (!session.access_token || !session.refresh_token) throw new ApiError('Authentication did not return a usable session.', 503);
  const jar = await cookies();
  const options = { httpOnly: true, sameSite: 'strict' as const, secure: process.env.NODE_ENV === 'production', path: '/api/rotation' };
  jar.set(ACCESS, session.access_token, { ...options, maxAge: Math.min(session.expires_in ?? 3600, 3600) });
  jar.set(REFRESH, session.refresh_token, { ...options, maxAge: 60 * 60 * 24 * 7 });
}
export async function requireUser(): Promise<RotationUser> {
  const jar = await cookies();
  let token = jar.get(ACCESS)?.value;
  let result = token ? await authRequest('user', {}, token) : null;
  if (!result?.ok && jar.get(REFRESH)?.value) {
    const refresh = await authRequest('token?grant_type=refresh_token', { method: 'POST', body: JSON.stringify({ refresh_token: jar.get(REFRESH)!.value }) });
    if (refresh.ok) {
      const session = await refresh.json();
      await storeSession(session); token = session.access_token;
      result = await authRequest('user', {}, token);
    }
  }
  if (!result?.ok || !token) throw new ApiError('Sign in to your rotation paper workspace.', 401);
  const user = await result.json();
  if (typeof user.id !== 'string' || typeof user.email !== 'string') throw new ApiError('Invalid authentication session.', 401);
  // The shared workshop contains other apps. A valid workshop JWT alone grants no rotation membership.
  const rows = await dbRequest<{ user_id: string; is_demo: boolean }[]>(`wpr_members?user_id=eq.${encodeURIComponent(user.id)}&select=user_id,is_demo`, {}, token);
  if (rows.length !== 1) throw new ApiError('This account does not have rotation workspace access.', 403);
  return { id: user.id, email: user.email, demo: rows[0].is_demo, accessToken: token };
}
export function publicUser(user: RotationUser) { return { id: user.id, email: user.email, demo: user.demo }; }
export function demoEnabled() { return process.env.WPR_DEMO_ENABLED === 'true' && Boolean(process.env.WPR_DEMO_EMAIL && process.env.WPR_DEMO_PASSWORD); }
export async function rateLimit(request: Request, scope: string, maximum = 15, seconds = 60): Promise<void> {
  const ip = request.headers.get('x-forwarded-for')?.split(',')[0].trim() ?? 'local';
  const hash = createHash('sha256').update(`${scope}:${ip}`).digest('hex');
  const allowed = await dbRequest<boolean>('rpc/wpr_take_rate_limit', { method: 'POST', body: JSON.stringify({ p_key: hash, p_limit: maximum, p_seconds: seconds }) });
  if (!allowed) throw new ApiError('Too many requests. Wait a minute and try again.', 429);
}
export async function signIn(email: string, password: string): Promise<RotationUser> {
  if (!email || email.length > 254 || !password || password.length > 1024) throw new ApiError('Enter a valid email and password.');
  const result = await authRequest('token?grant_type=password', { method: 'POST', body: JSON.stringify({ email, password }) });
  if (!result.ok) throw new ApiError('Sign-in failed. Check your workspace credentials.', 401);
  const session = await result.json();
  const rows = await dbRequest<{ user_id: string; is_demo: boolean }[]>(`wpr_members?user_id=eq.${encodeURIComponent(session.user.id)}&select=user_id,is_demo`, {}, session.access_token);
  if (rows.length !== 1) throw new ApiError('This account does not have rotation workspace access.', 403);
  await storeSession(session);
  await audit(session.user.id, 'signin');
  return { id: session.user.id, email: session.user.email, demo: rows[0].is_demo, accessToken: session.access_token };
}
export async function audit(ownerId: string, kind: string, detail: Record<string, unknown> = {}): Promise<void> {
  await dbRequest('wpr_audit', { method: 'POST', body: JSON.stringify({ owner_id: ownerId, kind, detail }) });
}
export async function demoSignIn(request: Request): Promise<RotationUser> {
  if (!demoEnabled()) throw new ApiError('Demo sign-in is disabled.', 404);
  try { return await requireUser(); } catch (error) { if (!(error instanceof ApiError) || error.status !== 401) throw error; }
  // Existing seeded accounts remain available for controlled QA. Public visitors get
  // separate real GoTrue identities, so one visitor cannot overwrite another ledger.
  await rateLimit(request, 'demo-create', 3, 3600);
  const globalAllowed = await dbRequest<boolean>('rpc/wpr_take_rate_limit', { method: 'POST', body: JSON.stringify({ p_key: 'demo-create-global-v1', p_limit: 50, p_seconds: 86400 }) });
  if (!globalAllowed) throw new ApiError('Demo account creation is at its daily capacity. Existing workspace sign-in remains available.', 429);
  const cfg = config();
  const email = `wpr-demo-${crypto.randomUUID()}@workshop.invalid`;
  const password = `${crypto.randomUUID()}${crypto.randomUUID()}`;
  const result = await authRequest('admin/users', { method: 'POST', headers: { apikey: cfg.service }, body: JSON.stringify({ email, password, email_confirm: true, app_metadata: { app: 'wolfpack-rotation', demo: true } }) }, cfg.service);
  if (!result.ok) throw new ApiError('Demo account could not be created. Try again later.', 503);
  const user = await result.json();
  await dbRequest('wpr_members', { method: 'POST', body: JSON.stringify({ user_id: user.id, is_demo: true }) });
  return signIn(email, password);
}
export async function signOut(): Promise<void> {
  const jar = await cookies();
  let user: RotationUser | null = null;
  try { user = await requireUser(); } catch (error) { if (!(error instanceof ApiError) || error.status !== 401) throw error; }
  const token = user?.accessToken;
  if (user) await audit(user.id, 'signout');
  if (token) {
    const revoked = await authRequest('logout?scope=local', { method: 'POST' }, token);
    if (!revoked.ok && revoked.status !== 401 && revoked.status !== 403) throw new ApiError('Session revocation failed. Retry signing out.', 503);
  }
  for (const name of [ACCESS, REFRESH]) jar.set(name, '', { httpOnly: true, sameSite: 'strict', secure: process.env.NODE_ENV === 'production', path: '/api/rotation', maxAge: 0 });
}
export async function getPortfolio(user: RotationUser): Promise<Portfolio | null> {
  const rows = await dbRequest<{ data: unknown }[]>(`wpr_portfolios?owner_id=eq.${encodeURIComponent(user.id)}&select=data`, {}, user.accessToken);
  if (rows.length > 1) throw new ApiError('Portfolio ownership is inconsistent.', 503);
  return rows.length ? validatePortfolio(rows[0].data) : null;
}
export async function requirePortfolio(user: RotationUser, expectedRevision: unknown): Promise<Portfolio> {
  if (!Number.isSafeInteger(expectedRevision) || (expectedRevision as number) < 0) throw new ApiError('Valid expected revision required.');
  const portfolio = await getPortfolio(user);
  if (!portfolio) throw new ApiError('Create a paper portfolio first.', 404);
  if (portfolio.revision !== expectedRevision) throw new ApiError('Portfolio changed. Reload before continuing.', 409);
  return portfolio;
}
export async function commitPortfolio(user: RotationUser, next: Portfolio, expected: number | null, previewId: string | null = null, recommendationId: string | null = null, expectedPlan: number | null = null): Promise<Portfolio> {
  validatePortfolio(next);
  const saved = await dbRequest<unknown>('rpc/wpr_commit_decision', { method: 'POST', body: JSON.stringify({ p_owner: user.id, p_next: next, p_expected: expected, p_preview: previewId, p_recommendation: recommendationId, p_plan_expected: expectedPlan }) });
  return validatePortfolio(saved);
}
export async function freshMarket(): Promise<MarketSnapshot> {
  // Reuse the same public market adapter; never trust browser-supplied prices.
  const { GET } = await import('@/app/api/rotation/market/route');
  const marketResponse = await GET();
  const body = await marketResponse.json();
  if (!marketResponse.ok) throw new ApiError(body.error ?? 'Fresh public books are unavailable.', 503);
  return body as MarketSnapshot;
}
