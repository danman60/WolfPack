import { createHash } from 'node:crypto';
import { GET as getHistory } from '@/app/api/rotation/history/route';
import type { HistoryDataset } from './contract';
import { ANALYSIS_VERSION, type AnalysisSnapshot, type PairAnalysis, type SentimentSnapshot } from './analysis-contract';
import { buildTechnicalPairs } from './technical-analysis';
import { fetchSentiment } from './sentiment';

function pairSentiment(pair: PairAnalysis, news: SentimentSnapshot): PairAnalysis['sentiment'] {
  const base = news.assets[pair.base];
  if (pair.quote === 'CAD') return {status: base.status, score: base.score, label: base.label, asOf: base.asOf, articles: base.articles};
  const quote = news.assets[pair.quote];
  const articles = [...new Map([...base.articles, ...quote.articles].map(article => [article.id, article])).values()].sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));
  if (base.score === null || quote.score === null) return {status: 'unavailable', score: null, label: 'Relative headline context requires current coverage for both assets', asOf: null, articles};
  const score = (base.score - quote.score) / 2;
  return {status: 'available', score, label: Math.abs(score) <= .15 ? 'Similar or mixed headline language across both assets' : `More positive headline language for ${score > 0 ? pair.base : pair.quote}`,
    asOf: [base.asOf!, quote.asOf!].sort()[0], articles};
}

let cached: {until: number; value: AnalysisSnapshot} | undefined;
let pending: Promise<AnalysisSnapshot> | undefined;

/** Server-owned immutable content; callers persist the full snapshot with any frozen decision. */
export async function getCurrentAnalysis(): Promise<AnalysisSnapshot> {
  if (cached && cached.until > Date.now()) return cached.value;
  if (pending) return pending;
  pending = (async () => {
    const [history, sentiment] = await Promise.all([
      (async () => {
        try {
          const response = await getHistory(); const dataset = await response.json();
          if (!response.ok) throw new Error(typeof dataset.error === 'string' ? dataset.error : 'Observed chart history unavailable.');
          return {dataset: dataset as HistoryDataset, error: null};
        } catch (error) { return {dataset: null, error: error instanceof Error ? error.message : 'Observed chart history unavailable.'}; }
      })(),
      fetchSentiment(),
    ]);
    const warnings: string[] = []; let pairs: PairAnalysis[] = []; let technicalAsOf: string | null = null;
    if (history.dataset) {
      try { const technical = buildTechnicalPairs(history.dataset); pairs = technical.pairs.map(pair => ({...pair, sentiment: pairSentiment(pair, sentiment)})); technicalAsOf = technical.technicalAsOf; }
      catch (error) { warnings.push(error instanceof Error ? error.message : 'Technical analysis unavailable.'); }
    } else warnings.push(history.error ?? 'Observed chart history unavailable.');
    if (sentiment.sources.some(source => source.status === 'unavailable')) warnings.push('One or more news publishers are unavailable; remaining source coverage is incomplete.');
    if (Object.values(sentiment.assets).some(asset => asset.status === 'unavailable')) warnings.push('Some assets have no current asset-specific headline coverage. Missing coverage is not a neutral observation.');
    const payload: Omit<AnalysisSnapshot, 'id'> = {version: ANALYSIS_VERSION, asOf: new Date().toISOString(), technicalAsOf,
      status: pairs.length ? warnings.length ? 'partial' : 'available' : 'unavailable', source: history.dataset?.source ?? 'Observed chart history unavailable', pairs, sentiment,
      warnings: [...warnings, 'Pair charts use aligned daily reference closes and derived ratios, not executable cross-market candles. Support and resistance are prior closing ranges, not intraday highs or lows.', 'Technical and headline confluence is descriptive context, not a calibrated change to the return forecast.']};
    const value: AnalysisSnapshot = {...payload, id: createHash('sha256').update(JSON.stringify(payload)).digest('hex')};
    cached = {until: Date.now() + (pairs.length ? 300_000 : 60_000), value};
    return value;
  })().finally(() => { pending = undefined; });
  return pending;
}
