import { createPortfolio } from '@/lib/rotation/engine';
import type { Amounts, Cadence } from '@/lib/rotation/contract';
import { apiError, ApiError, audit, commitPortfolio, dbRequest, freshMarket, getPortfolio, rateLimit, readBody, requireSameOrigin, protectedRoute, response } from '@/lib/rotation/server';
export const dynamic = 'force-dynamic';
export const GET = protectedRoute(async (request, user) => {
  try {
    const portfolio = await getPortfolio(user);
    if (new URL(request.url).searchParams.get('export') === '1') {
      const trials = await dbRequest(`wpr_trials?owner_id=eq.${encodeURIComponent(user.id)}&select=id,kind,data,created_at&order=created_at.asc`, {}, user.accessToken);
      const previews = await dbRequest(`wpr_previews?owner_id=eq.${encodeURIComponent(user.id)}&consumed_at=not.is.null&select=id,portfolio_id,revision,data,created_at,expires_at,consumed_at&order=created_at.asc`, {}, user.accessToken);
      await audit(user.id, 'export', { portfolioId: portfolio?.id ?? null });
      const events = await dbRequest(`wpr_audit?owner_id=eq.${encodeURIComponent(user.id)}&select=id,kind,detail,created_at&order=created_at.asc`, {}, user.accessToken);
      const result = response({ version: 1, exportedAt: new Date().toISOString(), portfolio, trials, previews, audit: events });
      result.headers.set('Content-Disposition', 'attachment; filename="wolfpack-rotation-workspace.json"');
      return result;
    }
    return response({ portfolio });
  } catch (error) { return apiError(error); }
});
export const POST = protectedRoute(async (request, user) => {
  try {
    requireSameOrigin(request); await rateLimit(request, `create:${user.id}`);
    if (await getPortfolio(user)) throw new ApiError('A paper portfolio already exists. Reload this workspace.', 409);
    const body = await readBody(request);
    const market = await freshMarket();
    const next = createPortfolio({ name: body.name as string, opening: body.opening as Amounts, cadence: body.cadence as Cadence, feeBps: body.feeBps as number }, market);
    return response({ portfolio: await commitPortfolio(user, next, null), market }, 201);
  } catch (error) { return apiError(error); }
});
