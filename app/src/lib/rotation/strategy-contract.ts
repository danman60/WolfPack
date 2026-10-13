import type { Asset, ResearchConfig } from "./contract";
import type { OutcomeSummary } from "./research-contract";

export const STRATEGY_STUDY_VERSION = "cad-rotation-selector-v1" as const;
export type StrategyStudyConfig = Omit<ResearchConfig, "lookbackDays">;
export type StrategyCandidateId = "momentum-14" | "momentum-30" | "momentum-60" | "momentum-90" | "momentum-180";
export type StrategyChoice = StrategyCandidateId | "hold";
export type StudyMetric = {
  finalCad: number; holdCad: number; cashCad: number;
  excessHoldCad: number; excessCashCad: number;
  feesCad: number; turnoverCad: number; trades: number;
  maxDrawdownPercent: number; completedReviews: number;
};
export type StudyPoint = { date: string; strategyCad: number; holdCad: number; cashCad: number };
export type CandidateScore = {
  candidateId: StrategyCandidateId; lookbackDays: number;
  scoreCad: number; metrics: StudyMetric;
};
export type StudyBlock = {
  start: string; end: string; trainingThrough: string;
  selected: StrategyChoice; scores: CandidateScore[]; completed: boolean;
};
export type StudyReview = {
  date: string; signalThrough: string; selected: StrategyChoice;
  target: Asset | null; executeDate: string; horizonEnd: string; completed: boolean;
};
export type StrategyPlan = {
  status: "hold" | "experimental-shift";
  validation: "retrospective-unvalidated";
  candidateId: StrategyChoice; target: Asset | null;
  targetWeights: Record<Asset, number> | null;
  reasons: string[]; signalThrough: string;
  reviewDue: boolean; nextReviewDate: string;
  horizonStart: string; horizonEnd: string;
  basis: "entered-portfolio" | "equal-basket-scenario";
  startingValueCad: number;
  outerCompletedBlocks: number; outerCompletedReviews: number;
  /** Hypothetical candidate, including when gates reject it and instruct HOLD. */
  paired: { target: Asset; observations: number; shift: OutcomeSummary; hold: OutcomeSummary; advantage: OutcomeSummary } | null;
};
export type StrategyStudyReport = {
  version: typeof STRATEGY_STUDY_VERSION;
  exposure: "already-exposed"; status: "retrospective-unvalidated";
  config: StrategyStudyConfig; candidateCount: 5;
  coverageStart: string; coverageEnd: string;
  comparisonStart: string; outerStart: string;
  candidates: (CandidateScore & { points: StudyPoint[] })[];
  blocks: StudyBlock[];
  outer: { metrics: StudyMetric; points: StudyPoint[]; reviews: StudyReview[] };
  latestSelection: { trainingThrough: string; selected: StrategyChoice; scores: CandidateScore[] };
  plan: StrategyPlan; notes: string[];
};
