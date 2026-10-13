import { createHash } from 'node:crypto';
import { GET as getHistory } from '@/app/api/rotation/history/route';
import { ASSETS, CRYPTO_ASSETS, type HistoryDataset, type MarketSnapshot, type Portfolio, type ShiftPreview } from './contract';
import { approveShift, previewShift, RotationValidationError } from './engine';
import { ApiError, dbRequest, freshMarket, requirePortfolio, type RotationUser } from './server';
import { STRATEGY_STUDY_VERSION, type StrategyStudyConfig, type StrategyStudyReport } from './strategy-contract';
import { runStrategyStudy, strategyStudyFingerprintSource } from './strategy-study';
import type { StrategyDevelopmentData, StrategyPlanState, StrategyProtocolData, StrategyTrial, StrategyRebalance } from './strategy-api-contract';

const SCALE = 100_000_000n;
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ApiError('Strategy inputs must be an object.');
  return value as Record<string, unknown>;
}
export function strategyId(value: unknown): string {
  if (typeof value !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) throw new ApiError('A valid strategy record ID is required.');
  return value;
}
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(',')}}`;
  return JSON.stringify(value);
}
export function strategyHash(value: unknown): string { return createHash('sha256').update(canonical(value)).digest('hex'); }
function fingerprint(): string { return strategyHash(strategyStudyFingerprintSource()); }
function units(value: string): bigint {
  if (!/^\d{1,16}(?:\.\d{1,8})?$/.test(value)) throw new ApiError('Strategy amount is outside fixed precision.');
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole) * SCALE + BigInt(fraction.padEnd(8, '0'));
}
function decimal(value: bigint): string { return `${value / SCALE}.${(value % SCALE).toString().padStart(8, '0')}`; }
function marks(market: MarketSnapshot) {
  return { CAD: SCALE, BTC: (units(market.books.BTC.bid) + units(market.books.BTC.ask)) / 2n,
    ETH: (units(market.books.ETH.bid) + units(market.books.ETH.ask)) / 2n,
    LINK: (units(market.books.LINK.bid) + units(market.books.LINK.ask)) / 2n };
}
async function history(): Promise<HistoryDataset> {
  const result = await getHistory(); const dataset = await result.json();
  if (!result.ok) throw new ApiError('Real historical prices are unavailable.', 503);
  if (!Array.isArray(dataset.points) || dataset.points.length < 575) throw new ApiError('Insufficient real history for the strategy study.');
  if (!Number.isFinite(Date.parse(dataset.coverageEnd)) || Date.now() - Date.parse(dataset.coverageEnd) > 3 * 86_400_000) throw new ApiError('Historical prices are stale. Refresh data before computing a recommendation.', 503);
  return dataset as HistoryDataset;
}
export async function loadStrategyTrial(user: RotationUser, id: unknown): Promise<StrategyTrial> {
  const rows = await dbRequest<StrategyTrial[]>(`wpr_trials?owner_id=eq.${user.id}&id=eq.${strategyId(id)}&data->>namespace=eq.strategy&select=id,created_at,kind,data`, {}, user.accessToken);
  if (rows.length !== 1) throw new ApiError('Strategy record not found in this workspace.', 404);
  if (rows[0].data.protocolVersion !== STRATEGY_STUDY_VERSION) throw new ApiError('This strategy needs its original evaluator version.', 409);
  return rows[0];
}
export async function getPlanState(user: RotationUser): Promise<StrategyPlanState> {
  const rows = await dbRequest<{active_plan_id: string | null; plan_revision: number}[]>(`wpr_portfolios?owner_id=eq.${user.id}&select=active_plan_id,plan_revision`, {}, user.accessToken);
  if (!rows.length) return { activePlanId: null, planRevision: 0, study: null };
  const state = rows[0];
  const study = state.active_plan_id ? await loadStrategyTrial(user, state.active_plan_id) : null;
  if (study && (study.kind !== 'development' || study.data.purpose !== 'study')) throw new ApiError('The adopted strategy record is inconsistent.', 503);
  return { activePlanId: state.active_plan_id, planRevision: state.plan_revision, study: study as StrategyPlanState['study'] };
}
function checkPlanRevision(state: StrategyPlanState, expected: unknown): void {
  if (!Number.isSafeInteger(expected) || (expected as number) < 0) throw new ApiError('Valid expected plan revision required.');
  if (state.planRevision !== expected) throw new ApiError('Adopted plan changed. Refresh before continuing.', 409);
}
async function saveTrial(user: RotationUser, id: string, kind: StrategyTrial['kind'], data: StrategyTrial['data']): Promise<StrategyTrial> {
  const rows = await dbRequest<StrategyTrial[]>('wpr_trials', { method: 'POST', body: JSON.stringify({id, owner_id: user.id, kind, data}) });
  if (rows.length !== 1) throw new ApiError('Strategy record was not confirmed saved.', 503);
  return rows[0];
}
function verifyProtocol(protocol: StrategyProtocolData): void {
  if (protocol.evaluatorHash !== fingerprint()) throw new ApiError('Strategy evaluator changed. Run and adopt a fresh study.', 409);
  if (protocol.sourceHash !== strategyHash({source: protocol.dataset.source, points: protocol.dataset.points})) throw new ApiError('Archived strategy source integrity check failed.', 409);
}
async function protocolData(portfolio: Portfolio, risk: unknown, slippage: unknown, adoptedStudyId?: string, frozen?: StrategyProtocolData): Promise<{data: StrategyProtocolData; market: MarketSnapshot}> {
  if (typeof risk !== 'number' || !Number.isFinite(risk) || risk < 0 || risk > 100) throw new ApiError('Enter target crypto allocation from 0 to 100 percent.');
  if (typeof slippage !== 'number' || !Number.isFinite(slippage) || slippage < 0 || slippage > 1000) throw new ApiError('Enter adverse slippage from 0 to 1000 basis points.');
  const [latest, market] = await Promise.all([history(), freshMarket()]); const prices = marks(market);
  let dataset = latest;
  if (frozen) {
    const merged = new Map(frozen.dataset.points.map(point => [point.date, point]));
    for (const point of latest.points) {
      const archived = merged.get(point.date);
      if (archived && CRYPTO_ASSETS.some(asset => archived.prices[asset] !== point.prices[asset])) throw new ApiError('Source revisions differ from the adopted archive. Register a new study after provenance review.', 409);
      merged.set(point.date, point);
    }
    const points = [...merged.values()].sort((a, b) => a.date.localeCompare(b.date));
    dataset = {...latest, points, coverageStart: points[0].date, coverageEnd: points.at(-1)!.date};
  }
  const capital = ASSETS.reduce((sum, asset) => sum + units(portfolio.balances[asset]) * prices[asset] / SCALE, 0n);
  if (capital <= 0n || capital > 1_000_000_000_000n * SCALE) throw new ApiError('Portfolio must have positive study capital at most CAD 1 trillion.');
  const config: StrategyStudyConfig = frozen ? {...frozen.config} : { capitalCad: Number(capital) / Number(SCALE), cadence: portfolio.cadence, feeBps: portfolio.feeBps, riskPercent: risk, slippageBps: slippage };
  const scenario = {balances: {...portfolio.balances}, marks: {BTC: Number(prices.BTC) / Number(SCALE), ETH: Number(prices.ETH) / Number(SCALE), LINK: Number(prices.LINK) / Number(SCALE)}, asOf: market.fetchedAt, basis: 'entered-portfolio' as const};
  return { market, data: {namespace: 'strategy', protocolVersion: STRATEGY_STUDY_VERSION, config, dataset, scenario,
    portfolioId: portfolio.id, portfolioRevision: portfolio.revision, holdingsHash: strategyHash(portfolio.balances),
    sourceHash: strategyHash({source: dataset.source, points: dataset.points}), evaluatorHash: fingerprint(),
    buildCommit: process.env.VERCEL_GIT_COMMIT_SHA ?? process.env.GITHUB_SHA ?? null, ...(adoptedStudyId ? {adoptedStudyId} : {})} };
}
type Decision = Pick<StrategyDevelopmentData, 'decision' | 'nextShift' | 'executionNote' | 'rebalance'>;
type PriorRebalance = StrategyRebalance & {completed: boolean};
const ceil = (n: bigint, d: bigint) => (n + d - 1n) / d;
function quantityBudget(market: MarketSnapshot, asset: Exclude<(typeof ASSETS)[number], 'CAD'>, quantity: bigint, feeBps: number): bigint {
  let remaining = quantity; let numerator = 0n;
  for (const level of market.books[asset].asks) {
    const take = remaining < units(level.quantity) ? remaining : units(level.quantity);
    numerator += take * units(level.price); remaining -= take;
    if (remaining === 0n) break;
  }
  if (remaining > 0n) throw new ApiError('Insufficient current book depth for target sizing.', 409);
  const gross = ceil(numerator, SCALE);
  return gross + ceil(gross * BigInt(feeBps), 10_000n);
}
function targetStep(portfolio: Portfolio, market: MarketSnapshot, target: Exclude<(typeof ASSETS)[number], 'CAD'>, weights: StrategyRebalance['targetWeights']): {quote: ShiftPreview | null; dust: string[]; blocked?: string} {
  const price = marks(market); const risk = BigInt(Math.round(weights[target] * Number(SCALE)));
  const gap = (balances: Portfolio['balances']) => {
    const total = ASSETS.reduce((sum, asset) => sum + units(balances[asset]) * price[asset] / SCALE, 0n);
    return units(balances[target]) * price[target] / SCALE * SCALE - risk * total;
  };
  const initial = gap(portfolio.balances);
  if (initial === 0n) return {quote: null, dust: []};
  const book = market.books[target]; const increment = units(book.increment); const minimum = ceil(units(book.minimum), increment);
  const buy = initial < 0n; const side = buy ? book.asks : book.bids;
  const depth = side.reduce((sum, level) => sum + units(level.quantity), 0n) / increment;
  let maximum = buy ? depth : units(portfolio.balances[target]) / increment;
  const depthLimited = maximum > depth || buy;
  if (maximum > depth) maximum = depth;
  if (buy) {
    let low = 0n; let high = maximum;
    while (low < high) {
      const mid = (low + high + 1n) / 2n;
      if (quantityBudget(market, target, mid * increment, portfolio.feeBps) <= units(portfolio.balances.CAD)) low = mid;
      else high = mid - 1n;
    }
    maximum = low;
  }
  if (maximum < minimum) {
    if (depth < minimum) return {quote: null, dust: [], blocked: 'Captured book depth is below the venue minimum.'};
    return {quote: null, dust: [`Remaining ${target} adjustment cannot reach minimum ${book.minimum} with available owned funds.`]};
  }
  const quote = (count: bigint) => previewShift(portfolio, market, buy ? 'CAD' : target, buy ? target : 'CAD', decimal(buy ? quantityBudget(market, target, count * increment, portfolio.feeBps) : count * increment));
  const first = quote(minimum); const firstGap = gap(first.after);
  if (buy ? firstGap > 0n : firstGap < 0n) return {quote: null, dust: [`Needed ${target} adjustment is below venue minimum ${book.minimum}; current units retained.`]};
  const last = quote(maximum); const lastGap = gap(last.after);
  const shortAtDepth = maximum === depth && depthLimited && (buy ? lastGap < 0n : lastGap > 0n);
  // A full book may stop within one quantity increment of the desired weight.
  // Anything larger is a depth failure, never relabelled as dust.
  const incrementValue = increment * price[target] / SCALE;
  if (shortAtDepth && (lastGap < 0n ? -lastGap : lastGap) > incrementValue * SCALE) return {quote: null, dust: [], blocked: 'Current book depth cannot reach the target allocation.'};
  let low = minimum; let high = maximum;
  while (low < high) {
    const mid = (low + high + 1n) / 2n; const value = gap(quote(mid).after);
    if (buy ? value <= 0n : value >= 0n) low = mid; else high = mid - 1n;
  }
  const chosen = quote(low);
  return {quote: chosen, dust: [`Final target sizing rounds down to ${target} increment ${book.increment}; residual CAD/units remain owned.`]};
}
export function sizeStrategyStep(portfolio: Portfolio, market: MarketSnapshot, original: StrategyRebalance): Decision {
  const rebalance = {...original, dust: [] as string[], completesAfterNext: false};
  const weights = rebalance.targetWeights;
  if (ASSETS.some(asset => !Number.isFinite(weights[asset]) || weights[asset] < 0 || weights[asset] > 1) || Math.abs(ASSETS.reduce((sum, asset) => sum + weights[asset], 0) - 1) > 1e-8) throw new ApiError('Strategy target allocation is invalid.', 503);
  const transferable = (balances: Portfolio['balances']) => CRYPTO_ASSETS.filter(asset => asset !== rebalance.target && units(balances[asset]) / units(market.books[asset].increment) * units(market.books[asset].increment) >= units(market.books[asset].minimum));
  for (const asset of CRYPTO_ASSETS) {
    if (asset !== rebalance.target && units(portfolio.balances[asset]) > 0n && !transferable(portfolio.balances).includes(asset)) rebalance.dust.push(`${portfolio.balances[asset]} ${asset} remains below minimum/increment ${market.books[asset].minimum}/${market.books[asset].increment}.`);
  }
  let proposed: ShiftPreview | null = null;
  try {
    const liquidation = transferable(portfolio.balances)[0];
    if (liquidation) {
      const increment = units(market.books[liquidation].increment);
      const quantity = units(portfolio.balances[liquidation]) / increment * increment;
      proposed = previewShift(portfolio, market, liquidation, 'CAD', decimal(quantity));
      if (!transferable(proposed.after).length) {
        if (rebalance.target === 'CAD') rebalance.completesAfterNext = true;
        else {
          const remaining = targetStep(approveShift(portfolio, proposed), market, rebalance.target, weights);
          rebalance.completesAfterNext = !remaining.quote && !remaining.blocked;
          if (rebalance.completesAfterNext) rebalance.dust.push(...remaining.dust);
        }
      }
    } else if (rebalance.target !== 'CAD') {
      const adjustment = targetStep(portfolio, market, rebalance.target, weights);
      if (adjustment.blocked) return {decision: 'blocked', nextShift: null, executionNote: adjustment.blocked, rebalance};
      proposed = adjustment.quote; rebalance.dust.push(...adjustment.dust); rebalance.completesAfterNext = true;
    } else rebalance.completesAfterNext = true;
  } catch (error) {
    if (!(error instanceof RotationValidationError)) throw error;
    return {decision: 'blocked', nextShift: null, executionNote: `Target shift is not currently feasible: ${error.message}`, rebalance};
  }
  if (!proposed) return {decision: 'hold', nextShift: null, executionNote: `Target reached at venue precision. Record HOLD to finish this reviewed rebalance. ${rebalance.dust.join(' ')}`, rebalance};
  if (rebalance.stepsCompleted >= 3) return {decision: 'blocked', nextShift: null, executionNote: 'This reviewed rebalance reached its three-step limit. Run and adopt a new study before more strategy shifts.', rebalance};
  return {decision: 'shift', nextShift: {from: proposed.from, to: proposed.to, amount: proposed.amount}, executionNote: `Step ${rebalance.stepsCompleted + 1} of at most 3 for the frozen ${rebalance.reviewDate} target. ${rebalance.completesAfterNext ? 'This completes the reviewed target; later unchanged targets preserve units.' : 'Recalculate the next step after approval.'} ${rebalance.dust.join(' ')}`, rebalance};
}
async function lastRebalance(user: RotationUser, state: StrategyPlanState): Promise<PriorRebalance | null> {
  const rows = await dbRequest<{detail: {recommendationId: string; previewId: string | null}}[]>(`wpr_audit?owner_id=eq.${user.id}&kind=eq.trial&detail->>action=eq.recommendationDecision&detail->>planId=eq.${state.activePlanId}&detail->>planRevision=eq.${state.planRevision}&select=detail&order=created_at.desc,id.desc&limit=1`, {}, user.accessToken);
  if (!rows.length) return null;
  const previous = await loadStrategyTrial(user, rows[0].detail.recommendationId);
  if (previous.kind !== 'development') throw new ApiError('Recorded strategy decision is inconsistent.', 503);
  let rebalance = previous.data.rebalance;
  if (rows[0].detail.previewId) {
    const quotes = await dbRequest<{data: {rebalance?: StrategyRebalance}}[]>(`wpr_previews?owner_id=eq.${user.id}&id=eq.${strategyId(rows[0].detail.previewId)}&consumed_at=not.is.null&select=data`, {}, user.accessToken);
    rebalance = quotes[0]?.data.rebalance;
  }
  return rebalance ? {...rebalance, stepsCompleted: rebalance.stepsCompleted + (rows[0].detail.previewId ? 1 : 0), completed: rebalance.completesAfterNext} : null;
}
function recommendationDecision(portfolio: Portfolio, market: MarketSnapshot, report: StrategyStudyReport, id: string, prior: PriorRebalance | null): Decision {
  if (prior && !prior.completed) {
    if (prior.reviewExpiresAt && Date.parse(prior.reviewExpiresAt) > Date.now()) return sizeStrategyStep(portfolio, market, prior);
    // An interrupted prior review is superseded, not completed. Current policy
    // now governs the remaining holdings; retain the original immutable audit.
    prior = null;
  }
  if (report.plan.status === 'hold') return {decision: 'hold', nextShift: null, executionNote: 'Retain current units. No conversion or fee is proposed.', ...(prior ? {rebalance: {...prior, completesAfterNext: true}} : {})};
  if (prior?.completed && prior.target === report.plan.target) return {decision: 'hold', nextShift: null, executionNote: 'The last completed target is unchanged. Retain units and their natural weight drift; no rebalance fee.', rebalance: {...prior, completesAfterNext: true}};
  if (!report.plan.reviewDue || !report.plan.target || !report.plan.targetWeights) return {decision: 'hold', nextShift: null, executionNote: `Next scheduled review: ${report.plan.nextReviewDate}.`};
  const cutoff = report.plan.horizonEnd;
  // Eastern DST changes at 02:00 local. UTC midnight still has the offset
  // applicable at local midnight; sampling noon is wrong on transition dates.
  const offset = new Intl.DateTimeFormat('en-US', {timeZone: 'America/New_York', timeZoneName: 'longOffset'}).formatToParts(new Date(`${cutoff}T00:00:00Z`)).find(part => part.type === 'timeZoneName')!.value.replace('GMT', '');
  const reviewExpiresAt = new Date(`${cutoff}T00:00:00${offset}`).toISOString();
  return sizeStrategyStep(portfolio, market, {id, target: report.plan.target, targetWeights: report.plan.targetWeights, reviewDate: report.plan.horizonStart, reviewExpiresAt, stepsCompleted: 0, completesAfterNext: false, dust: []});
}
export async function createStrategyTrial(user: RotationUser, body: Record<string, unknown>): Promise<StrategyTrial> {
  const id = strategyId(body.id); const input = object(body.data);
  if (input.namespace !== 'strategy') throw new ApiError('Strategy namespace required.');
  if (body.kind === 'protocol') {
    if (input.protocolVersion !== STRATEGY_STUDY_VERSION) throw new ApiError('Unknown strategy version.');
    const portfolio = await requirePortfolio(user, input.expectedRevision); const config = object(input.config);
    const {data} = await protocolData(portfolio, config.riskPercent, config.slippageBps);
    return saveTrial(user, id, 'protocol', data);
  }
  if (body.kind !== 'development') throw new ApiError('Strategy supports protocol and development records.');
  if (input.purpose === 'study') {
    const registered = await loadStrategyTrial(user, input.protocolId);
    if (registered.kind !== 'protocol') throw new ApiError('A strategy protocol is required.');
    verifyProtocol(registered.data);
    const report = runStrategyStudy(registered.data.dataset, registered.data.config, registered.data.scenario);
    const {namespace, protocolVersion, portfolioId, portfolioRevision, holdingsHash, sourceHash, evaluatorHash} = registered.data;
    return saveTrial(user, id, 'development', {namespace, protocolVersion, portfolioId, portfolioRevision, holdingsHash, sourceHash, evaluatorHash, purpose: 'study', protocolId: registered.id, report});
  }
  if (input.purpose !== 'recommendation') throw new ApiError('Choose study or recommendation.');
  const portfolio = await requirePortfolio(user, input.expectedRevision); const state = await getPlanState(user); checkPlanRevision(state, input.expectedPlanRevision);
  if (!state.study) throw new ApiError('Run and adopt a strategy study first.', 409);
  const adopted = await loadStrategyTrial(user, state.study.data.protocolId);
  if (adopted.kind !== 'protocol') throw new ApiError('Adopted strategy protocol is inconsistent.', 503);
  verifyProtocol(adopted.data);
  const archives = await dbRequest<StrategyTrial[]>(`wpr_trials?owner_id=eq.${user.id}&kind=eq.protocol&data->>namespace=eq.strategy&data->>adoptedStudyId=eq.${state.study.id}&select=id,created_at,kind,data&order=created_at.desc,id.desc&limit=1`, {}, user.accessToken);
  const cumulative = archives[0]?.kind === 'protocol' ? archives[0].data : adopted.data;
  verifyProtocol(cumulative);
  if (strategyHash(cumulative.config) !== strategyHash(adopted.data.config) || cumulative.dataset.coverageStart !== adopted.data.dataset.coverageStart) throw new ApiError('Adopted strategy archive anchor or configuration changed.', 409);
  const {data, market} = await protocolData(portfolio, adopted.data.config.riskPercent, adopted.data.config.slippageBps, state.study.id, cumulative);
  const registered = await saveTrial(user, crypto.randomUUID(), 'protocol', data);
  const report = runStrategyStudy(data.dataset, data.config, data.scenario);
  const after = await getPlanState(user); checkPlanRevision(after, state.planRevision); await requirePortfolio(user, portfolio.revision);
  const {namespace, protocolVersion, portfolioId, portfolioRevision, holdingsHash, sourceHash, evaluatorHash} = data;
  const decision = recommendationDecision(portfolio, market, report, id, await lastRebalance(user, state));
  const cutoff = Date.parse(decision.rebalance?.reviewExpiresAt ?? '');
  // The existing SQL expiry check also enforces the review boundary while the
  // portfolio row is locked. Completed targets may persist as HOLD provenance.
  const expiry = Number.isFinite(cutoff) && cutoff > Date.parse(market.fetchedAt) ? Math.min(Date.now() + 15 * 60_000, cutoff) : Date.now() + 15 * 60_000;
  return saveTrial(user, id, 'development', {namespace, protocolVersion, portfolioId, portfolioRevision, holdingsHash, sourceHash, evaluatorHash, purpose: 'recommendation', protocolId: registered.id,
    report, planId: state.study.id, planRevision: state.planRevision, expiresAt: new Date(expiry).toISOString(), ...decision});
}
export async function adoptPlan(user: RotationUser, body: Record<string, unknown>, portfolio: Portfolio): Promise<StrategyPlanState> {
  const study = await loadStrategyTrial(user, body.studyId); const state = await getPlanState(user); checkPlanRevision(state, body.expectedPlanRevision);
  if (study.kind !== 'development' || study.data.purpose !== 'study' || study.data.portfolioId !== portfolio.id) throw new ApiError('Choose a study for this portfolio.');
  if (study.data.portfolioRevision !== portfolio.revision || study.data.holdingsHash !== strategyHash(portfolio.balances)) throw new ApiError('Holdings changed since this study. Run a fresh study before adoption.', 409);
  const registered = await loadStrategyTrial(user, study.data.protocolId);
  if (registered.kind !== 'protocol') throw new ApiError('Study protocol is inconsistent.', 503);
  verifyProtocol(registered.data);
  if (study.data.evaluatorHash !== fingerprint() || study.data.sourceHash !== registered.data.sourceHash) throw new ApiError('Study provenance changed. Run a fresh study.', 409);
  await dbRequest('rpc/wpr_adopt_plan', {method: 'POST', body: JSON.stringify({p_owner: user.id, p_study: study.id, p_expected: portfolio.revision, p_plan_expected: state.planRevision})});
  return getPlanState(user);
}
export async function requireRecommendation(user: RotationUser, id: unknown, portfolio: Portfolio, expectedPlan: unknown): Promise<Extract<StrategyTrial, {kind: 'development'}>> {
  const trial = await loadStrategyTrial(user, id); const state = await getPlanState(user); checkPlanRevision(state, expectedPlan);
  if (trial.kind !== 'development' || trial.data.purpose !== 'recommendation') throw new ApiError('A current strategy recommendation is required.');
  const data = trial.data;
  if (data.decision === 'shift' && (!data.rebalance?.reviewExpiresAt || !Number.isFinite(Date.parse(data.rebalance.reviewExpiresAt)) || Date.parse(data.rebalance.reviewExpiresAt) <= Date.now())) throw new ApiError('This reviewed target expired at the next scheduled review. Refresh the recommendation.', 409);
  if (data.planId !== state.activePlanId || data.planRevision !== state.planRevision || data.portfolioId !== portfolio.id || data.portfolioRevision !== portfolio.revision || data.holdingsHash !== strategyHash(portfolio.balances) || !data.expiresAt || !Number.isFinite(Date.parse(data.expiresAt)) || Date.parse(data.expiresAt) <= Date.now() || data.evaluatorHash !== fingerprint()) throw new ApiError('Recommendation expired or its plan or holdings changed. Refresh it first.', 409);
  const source = await loadStrategyTrial(user, data.protocolId);
  if (source.kind !== 'protocol' || source.data.sourceHash !== data.sourceHash || source.data.holdingsHash !== data.holdingsHash) throw new ApiError('Recommendation source binding is inconsistent.', 409);
  verifyProtocol(source.data);
  return trial;
}
