import { previewShift } from '@/lib/rotation/engine';
import type { Asset } from '@/lib/rotation/contract';
import { apiError, ApiError, dbRequest, freshMarket, rateLimit, readBody, requirePortfolio, requireSameOrigin, protectedRoute, response } from '@/lib/rotation/server';
import { requireRecommendation, sizeStrategyStep } from '@/lib/rotation/strategy-server';
export const dynamic = 'force-dynamic';
export const POST = protectedRoute(async (request, user) => {
  try {
    requireSameOrigin(request); await rateLimit(request, `preview:${user.id}`, 30);
    const body = await readBody(request);
    const portfolio = await requirePortfolio(user, body.expectedRevision);
    const recommendation = body.recommendationId !== undefined ? await requireRecommendation(user, body.recommendationId, portfolio, body.expectedPlanRevision) : null;
    if (recommendation && ('from' in body || 'to' in body || 'amount' in body)) throw new ApiError('Recommended quotes cannot override server-owned amounts.');
    if (recommendation && (recommendation.data.decision !== 'shift' || !recommendation.data.nextShift)) throw new ApiError('This recommendation has no executable shift.');
    const market = await freshMarket(); const generatedAt = new Date();
    const sized = recommendation?.data.rebalance ? sizeStrategyStep(portfolio, market, recommendation.data.rebalance) : null;
    if (recommendation && (!sized || sized.decision !== 'shift' || !sized.nextShift)) throw new ApiError(sized?.executionNote ?? 'Refresh the strategy recommendation before quoting.', 409);
    const shift = sized?.nextShift ?? {from: body.from as Asset, to: body.to as Asset, amount: body.amount as string};
    const preview = previewShift(portfolio, market, shift.from, shift.to, shift.amount, generatedAt);
    await dbRequest('wpr_previews', { method: 'POST', body: JSON.stringify({ id: preview.id, owner_id: user.id, portfolio_id: portfolio.id, revision: portfolio.revision, expires_at: preview.expiresAt, data: { market, generatedAt: generatedAt.toISOString(), preview, ...(recommendation ? {recommendationId: recommendation.id, planId: recommendation.data.planId, planRevision: recommendation.data.planRevision, rebalance: sized!.rebalance} : {}) } }) });
    return response({ preview, market });
  } catch (error) { return apiError(error); }
});
