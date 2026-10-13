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
