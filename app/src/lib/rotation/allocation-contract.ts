import type { Amounts, Asset, CryptoAsset, FillLeg, HistoryDataset, MarketSnapshot, Portfolio } from './contract';
export const ALLOCATION_VERSION = 'cad-allocation-projection-v1' as const;
export type AllocationWeights = Record<Asset, number>;
export type AllocationForecast = { returns: Record<CryptoAsset, number>; members: Record<string, Record<CryptoAsset, number>>; signalAt: string; latestTrainingEnd: string; trainingOrigins: number; modelHash: string; confidence: 'low'; notes: string[] };
export type AllocationLeg = { id: string; from: Asset; to: Asset; amount: string; received: string; feeCad: number; grossCad: number; fills: FillLeg[] };
export type AllocationEstimate = {
  feasible: boolean; reason: string | null; weights: AllocationWeights; startingValueCad: number;
  expectedEndingValueCad: number; expectedProfitCad: number; expectedHoldProfitCad: number; expectedAdvantageCad: number;
  feesCad: number; slippageCad: number; spreadDepthCad: number; turnoverCad: number;
  plannedBalances: Amounts; legs: AllocationLeg[]; notes: string[];
};
export type AllocationProjection = {
  id: string; createdAt: string; version: typeof ALLOCATION_VERSION; portfolioId: string; startingRevision: number; preserveUnits?: boolean;
  asOf: string; dueAt: string; weights: AllocationWeights; slippageBps: number; feeBps: number;
  startingBalances: Amounts; startingPortfolio: Portfolio; market: MarketSnapshot; dataset: HistoryDataset;
  forecast: AllocationForecast; estimate: AllocationEstimate; sourceHash: string; evaluatorHash: string; buildCommit: string | null; analysisId: string | null; analysis: import('./analysis-contract').AnalysisSnapshot | null; rationale: string;
};
export type AllocationOutcome = {
  id: string; projectionId: string; observedAt: string; dueAt: string; priceAt: string;
  execution: 'fully-executed' | 'partly-executed' | 'not-executed';
  predictedProfitCad: number; predictedAdvantageCad: number; actualProfitCad: number; holdProfitCad: number;
  actualAdvantageCad: number; profitErrorCad: number; advantageErrorCad: number;
  hypotheticalProfitCad: number; hypotheticalAdvantageCad: number; netCashFlowsCad: number;
  prices: Record<CryptoAsset, number>; actualBalances: Amounts; notes: string[];
};
export type AllocationBatchOrder = { id: string; clientOrderId: string; index: number; status: 'queued' | 'intent' | 'filled' | 'partial' | 'unknown' | 'failed'; from: Asset; to: Asset; amount: string; filledAt?: string; fills?: FillLeg[]; feeCad?: number; error?: string };
export type AllocationBatch = {
  id: string; projectionId: string; portfolioId: string; revision: number; mode: 'paper' | 'live';
  status: 'running' | 'paused' | 'completed' | 'cancelled'; createdAt: string; updatedAt: string;
  expectedPortfolioRevision: number; orders: AllocationBatchOrder[]; pauseReason: string | null;
  maxCostCad: number; costsCad: number; targetWeights: AllocationWeights;
};
export type AllocationWorkspace = {
  forecast: AllocationForecast | null; forecastError: string | null; market: MarketSnapshot;
  recommendedWeights: AllocationWeights; recommendationDecision: 'hold' | 'shift' | 'unavailable'; recommendationReason: string; riskPercent: number | null; slippageBps: number | null;
  projections: AllocationProjection[]; outcomes: AllocationOutcome[]; batches: AllocationBatch[];
  connection: {mode: 'paper' | 'live'; provider: string; connected: boolean; supportedRoutes: string[]; note: string};
};
/** GET allocation -> AllocationWorkspace. POST projections {kind:'save',id,expectedRevision,weights,slippageBps,analysisId?} -> {projection}.
 * POST projections {kind:'checkin',projectionId} -> {outcome}. POST batches {kind:'apply',projectionId,expectedRevision,idempotencyKey,maxCostCad} -> {batch,portfolio}.
 * POST batches {kind:'advance'|'pause'|'resume'|'cancel',batchId,expectedBatchRevision} -> {batch,portfolio}. GET batches?id -> {batch,portfolio}.
 * Live dragging uses estimateAllocation(portfolio,market,weights,forecast.returns,slippageBps); save recomputes from authoritative inputs.
 */
