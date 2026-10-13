import type { Amounts, Asset, CryptoAsset, HistoryDataset, ResearchConfig, ResearchResult } from "./contract";

export const RESEARCH_VERSION = "cad-momentum-empirical-v1" as const;
export type ResearchScenario = {
  balances: Amounts;
  marks: Record<CryptoAsset, number>;
  asOf: string;
  basis: "entered-portfolio";
};
export type OutcomeSummary = { meanCad: number; downside10Cad: number; upper90Cad: number };
export type PairedForecast = {
  status: "unvalidated";
  target: Asset;
  start: string;
  horizonEnd: string;
  signalThrough: string;
  trainingThrough: string;
  observations: number;
  startingValueCad: number;
  basis: "entered-portfolio" | "equal-basket-scenario";
  shift: OutcomeSummary;
  hold: OutcomeSummary;
  advantage: OutcomeSummary;
  note: string;
};
export type EvaluationDecision = {
  review: string;
  end: string;
  target: Asset;
  trainingThrough: string;
  trainingObservations: number;
  predictedAdvantageCad: number;
  downside10Cad: number;
  upper90Cad: number;
  observedAdvantageCad: number;
  observedShiftCad: number;
  observedHoldCad: number;
  covered: boolean;
};
export type ChronologicalFold = {
  start: string;
  end: string;
  kind: "walk-forward" | "exposed-tail" | "prospective-holdout";
  decisions: number;
  meanAdvantageCad: number | null;
  meanAbsoluteErrorCad: number | null;
  intervalCoveragePercent: number | null;
};
export type ValidationReport = {
  protocolVersion: typeof RESEARCH_VERSION;
  status: "unvalidated";
  trainingStart: string;
  firstTestDate: string;
  exposedTailStart: string;
  folds: ChronologicalFold[];
  decisions: EvaluationDecision[];
  forecast: PairedForecast;
  replay: ResearchResult;
  note: string;
};
export type ResearchProtocol = {
  protocolVersion: typeof RESEARCH_VERSION;
  config: ResearchConfig;
  sourceHash: string;
  evaluatorHash: string;
  buildCommit: string | null;
  dataset: HistoryDataset;
  scenario?: ResearchScenario;
  historicalExposure: "already-exposed";
  forwardHoldoutStart: string;
  forwardHoldoutEnd: string;
};
export type ResearchTrial = {
  id: string;
  created_at: string;
  kind: "protocol" | "development" | "holdout";
  data: ResearchProtocol | { protocolId: string; report: ValidationReport } | { protocolId: string; folds: ChronologicalFold[]; decisions: EvaluationDecision[]; note: string };
};
export type ResearchTrialSummary = {
  id: string;
  created_at: string;
  kind: ResearchTrial["kind"];
  protocolId?: string;
  forwardHoldoutStart?: string;
  forwardHoldoutEnd?: string;
};
