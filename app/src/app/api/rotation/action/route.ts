import { approveShift, previewShift, recordCashFlow, recordHold } from '@/lib/rotation/engine';
import type { MarketSnapshot, ShiftPreview } from '@/lib/rotation/contract';
import { apiError, ApiError, commitPortfolio, dbRequest, rateLimit, readBody, requirePortfolio, requireSameOrigin, protectedRoute, response } from '@/lib/rotation/server';
export const dynamic = 'force-dynamic';
type StoredPreview = { id: string; revision: number; expires_at: string; consumed_at: string | null; data: { market: MarketSnapshot; generatedAt: string; preview: ShiftPreview } };
export const POST = protectedRoute(async (request, user) => {
  try {
    requireSameOrigin(request); await rateLimit(request, `action:${user.id}`, 40);
    const body = await readBody(request); const portfolio = await requirePortfolio(user, body.expectedRevision);
    let next; let previewId: string | null = null;
    if (body.kind === 'approve') {
      if (typeof body.previewId !== 'string' || !/^[0-9a-f-]{36}$/i.test(body.previewId)) throw new ApiError('Valid preview ID required.');
      const rows = await dbRequest<StoredPreview[]>(`wpr_previews?id=eq.${encodeURIComponent(body.previewId)}&owner_id=eq.${encodeURIComponent(user.id)}&select=id,revision,expires_at,consumed_at,data`, {}, user.accessToken);
      const saved = rows[0];
      if (!saved || saved.consumed_at || saved.revision !== portfolio.revision || Date.parse(saved.expires_at) <= Date.now()) throw new ApiError('Preview expired, changed or already approved. Generate a fresh preview.', 409);
      const trusted = saved.data.preview;
      // Recreate the engine's private preview seal from server-owned inputs. Client economics are ignored.
      const regenerated = previewShift(portfolio, saved.data.market, trusted.from, trusted.to, trusted.amount, new Date(saved.data.generatedAt));
      // PostgreSQL jsonb canonicalizes object-key order. Compare values, not the
      // original JavaScript insertion order; economic fields still match exactly.
      if (!isDeepStrictEqual({ ...regenerated, id: '' }, { ...trusted, id: '' })) throw new ApiError('Stored preview no longer reconciles. Generate a fresh preview.', 409);
      next = approveShift(portfolio, regenerated); previewId = saved.id;
      // Persist the ID the owner actually approved. The transient regenerated ID
      // exists only to establish the engine seal; commitPortfolio validates again.
      next.events[next.events.length - 1].id = saved.id;
    } else if (body.kind === 'hold') next = recordHold(portfolio);
    else if ((body.kind === 'deposit' || body.kind === 'withdrawal') && typeof body.amount === 'string') next = recordCashFlow(portfolio, body.kind, body.amount);
    else throw new ApiError('Unknown paper action.');
    return response({ portfolio: await commitPortfolio(user, next, portfolio.revision, previewId) });
  } catch (error) { return apiError(error); }
});
import { isDeepStrictEqual } from 'node:util';
