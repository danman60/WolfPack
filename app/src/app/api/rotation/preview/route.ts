import { previewShift } from '@/lib/rotation/engine';
import type { Asset } from '@/lib/rotation/contract';
import { apiError, dbRequest, freshMarket, rateLimit, readBody, requirePortfolio, requireSameOrigin, protectedRoute, response } from '@/lib/rotation/server';
export const dynamic = 'force-dynamic';
export const POST = protectedRoute(async (request, user) => {
  try {
    requireSameOrigin(request); await rateLimit(request, `preview:${user.id}`, 30);
    const body = await readBody(request);
    const portfolio = await requirePortfolio(user, body.expectedRevision);
    const market = await freshMarket(); const generatedAt = new Date();
    const preview = previewShift(portfolio, market, body.from as Asset, body.to as Asset, body.amount as string, generatedAt);
    await dbRequest('wpr_previews', { method: 'POST', body: JSON.stringify({ id: preview.id, owner_id: user.id, portfolio_id: portfolio.id, revision: portfolio.revision, expires_at: preview.expiresAt, data: { market, generatedAt: generatedAt.toISOString(), preview } }) });
    return response({ preview, market });
  } catch (error) { return apiError(error); }
});
