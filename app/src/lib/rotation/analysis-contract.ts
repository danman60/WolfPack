import type { Asset, CryptoAsset } from './contract';

export const ANALYSIS_VERSION = 'cad-rotation-analysis-v1' as const;
export type AnalysisPairId = 'BTC/CAD' | 'ETH/CAD' | 'LINK/CAD' | 'ETH/BTC' | 'LINK/BTC' | 'LINK/ETH';
export type NewsArticle = {
  id: string; title: string; url: string; source: string; publishedAt: string;
  assets: CryptoAsset[]; score: number; positiveTerms: string[]; negativeTerms: string[];
};
export type AssetSentiment = {
  status: 'available' | 'unavailable'; score: number | null; label: string;
  headlineCount: number; asOf: string | null; articles: NewsArticle[];
};
export type SentimentSnapshot = {
  fetchedAt: string; method: string; windowHours: number;
  assets: Record<CryptoAsset, AssetSentiment>;
  sources: { name: string; url: string; status: 'available' | 'unavailable'; itemCount: number; error?: string }[];
  bitcoinFearGreed: { status: 'available' | 'unavailable'; value: number | null; label: string; asOf: string | null; sourceUrl: string; scope: 'Bitcoin only' };
  limitations: string[];
};
export type PairTechnical = {
  trend: 'uptrend' | 'downtrend' | 'mixed'; rsi: number;
  macd: { line: number; signal: number; histogram: number };
  movingAverages: { sma20: number; sma50: number; sma200: number };
  supportZone: { low: number; high: number; basis: string };
  resistanceZone: { low: number; high: number; basis: string };
  confluence: string[];
};
export type PairAnalysis = {
  id: AnalysisPairId; label: string; base: CryptoAsset; quote: Asset;
  series: { date: string; value: number }[];
  latest: number; changePercent: number; technical: PairTechnical;
  sentiment: { status: 'available' | 'unavailable'; score: number | null; label: string; asOf: string | null; articles: NewsArticle[] };
};
export type AnalysisSnapshot = {
  id: string; version: typeof ANALYSIS_VERSION; asOf: string; technicalAsOf: string | null;
  status: 'available' | 'partial' | 'unavailable'; source: string;
  pairs: PairAnalysis[]; sentiment: SentimentSnapshot; warnings: string[];
};
