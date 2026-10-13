import type { Asset, HistoryDataset } from './contract';
import type { ResearchScenario } from './research-contract';
import type { StrategyStudyConfig, StrategyStudyReport } from './strategy-contract';

export type StrategyProvenance = {
  namespace: 'strategy'; protocolVersion: 'cad-rotation-selector-v1';
  portfolioId: string; portfolioRevision: number; holdingsHash: string;
  sourceHash: string; evaluatorHash: string;
};
export type StrategyProtocolData = StrategyProvenance & {
  config: StrategyStudyConfig; dataset: HistoryDataset; scenario: ResearchScenario;
  buildCommit: string | null; adoptedStudyId?: string;
};
export type StrategyDevelopmentData = StrategyProvenance & {
  purpose: 'study' | 'recommendation'; protocolId: string; report: StrategyStudyReport;
  planId?: string; planRevision?: number; expiresAt?: string;
  decision?: 'hold' | 'shift' | 'blocked';
  nextShift?: { from: Asset; to: Asset; amount: string } | null;
  executionNote?: string;
  rebalance?: StrategyRebalance;
};
export type StrategyRebalance = {
  id: string; target: Asset; targetWeights: Record<Asset, number>;
  reviewDate: string; reviewExpiresAt?: string; stepsCompleted: number; completesAfterNext: boolean; dust: string[];
};
export type StrategyTrial = {
  id: string; created_at: string;
} & ({ kind: 'protocol'; data: StrategyProtocolData } | { kind: 'development'; data: StrategyDevelopmentData });
export type StrategyTrialSummary = { id: string; created_at: string; kind: 'protocol' | 'development'; purpose?: string; protocolId?: string };
export type StrategyPlanState = { activePlanId: string | null; planRevision: number; study: Extract<StrategyTrial, {kind: 'development'}> | null };

export const FORECAST_ADVICE_VERSION = 'cad-forecast-advice-v1' as const;
export type ForecastAdviceReport = {
  decision: 'hold' | 'shift' | 'unavailable';
  asOf: string; expiresAt: string; nextReviewAt: string;
  forecastReturns: Record<import('./contract').CryptoAsset, number>;
  targetWeights: Record<Asset, number>; targetValuesCad: Record<Asset, number>; deltaCad: Record<Asset, number>;
  feesCad: number; slippageCad: number; expectedAdvantageCad: number;
  currentValueCad: number; expectedHoldValueCad: number; expectedTargetValueCad: number;
  reasons: string[]; notes: string[]; confidence: 'low'; trainingOrigins: number; source: string;
  nextShift: {from: Asset; to: Asset; amount: string} | null;
  candidates: {target: Asset | 'HOLD'; feasible: boolean; feesCad: number; slippageCad: number; expectedValueCad: number | null; balances: import('./contract').Amounts; reason?: string}[];
};
export type ForecastAdviceTrial = {
  id: string; created_at: string; kind: 'development';
  data: {
    namespace: 'forecast-advice'; protocolVersion: typeof FORECAST_ADVICE_VERSION;
    config: {riskPercent: number; slippageBps: number; cadence: import('./contract').Cadence; feeBps: number};
    portfolioId: string; portfolioRevision: number; holdingsHash: string; sourceHash: string;
    dataset: HistoryDataset; market: import('./contract').MarketSnapshot; startingBalances: import('./contract').Amounts;
    memberForecasts: Record<string, Record<import('./contract').CryptoAsset, number>>;
    modelHash: string; trainedThrough: string; latestTrainingEnd: string; labelConvention: string;
    report: ForecastAdviceReport;
  };
};
