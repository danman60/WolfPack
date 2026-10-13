import { apiError, ApiError, demoEnabled, demoSignIn, hasPreviousWorkspace, returnPreviousWorkspace, publicUser, rateLimit, readBody, requireSameOrigin, requireUser, response, signIn, signOut } from '@/lib/rotation/server';
export const dynamic = 'force-dynamic';
export async function GET() {
  try { return response({ authenticated: true, user: publicUser(await requireUser()), demoEnabled: demoEnabled(), hasPreviousWorkspace: await hasPreviousWorkspace() }); }
  catch (error) { if (error instanceof ApiError && error.status === 401) return response({ authenticated: false, user: null, demoEnabled: demoEnabled() }); return apiError(error); }
}
export async function POST(request: Request) {
  try {
    requireSameOrigin(request); await rateLimit(request, 'session');
    const body = await readBody(request);
    if (body.action === 'logout') { await signOut(); return response({ authenticated: false, user: null, demoEnabled: demoEnabled() }); }
    let email: string; let password: string;
    if (body.action === 'demo' || body.action === 'demo-example' || body.action === 'demo-return') {
      const workspace = body.action === 'demo-return' ? await returnPreviousWorkspace() : await demoSignIn(request, body.action === 'demo-example');
      return response({ ...workspace, authenticated: true, user: publicUser(workspace.user), demoEnabled: demoEnabled(), hasPreviousWorkspace: await hasPreviousWorkspace() });
    } else if (body.action === 'login' && typeof body.email === 'string' && typeof body.password === 'string') {
      email = body.email; password = body.password;
    } else throw new ApiError('Choose demo or workspace sign-in.');
    const user = await signIn(email, password);
    return response({ authenticated: true, user: publicUser(user), demoEnabled: demoEnabled() });
  } catch (error) { return apiError(error); }
}
