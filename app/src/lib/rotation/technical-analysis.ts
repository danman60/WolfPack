import { CRYPTO_ASSETS, type HistoryDataset } from './contract';
import type { PairAnalysis, PairTechnical } from './analysis-contract';

const DAY = 86_400_000;
const PAIRS = [['BTC', 'CAD'], ['ETH', 'CAD'], ['LINK', 'CAD'], ['ETH', 'BTC'], ['LINK', 'BTC'], ['LINK', 'ETH']] as const;
const mean = (values: number[]) => values.reduce((sum, value) => sum + value, 0) / values.length;

/** Close-only adaptation of the chart EMA convention: seed with a full-period SMA. */
function ema(values: number[], period: number): number[] {
  const result = Array<number>(period - 1).fill(NaN);
  let current = mean(values.slice(0, period)); result.push(current);
  for (let i = period; i < values.length; i++) {
    current += 2 / (period + 1) * (values[i] - current); result.push(current);
  }
  return result;
}

export function closeIndicators(closes: number[]): PairTechnical {
  if (closes.length < 200 || closes.some(value => !Number.isFinite(value) || value <= 0)) throw new Error('Technical analysis requires 200 positive observed closes.');
  let gain = 0; let loss = 0;
  for (let i = 1; i <= 14; i++) { const change = closes[i] - closes[i - 1]; gain += Math.max(change, 0) / 14; loss += Math.max(-change, 0) / 14; }
  for (let i = 15; i < closes.length; i++) { const change = closes[i] - closes[i - 1]; gain = (gain * 13 + Math.max(change, 0)) / 14; loss = (loss * 13 + Math.max(-change, 0)) / 14; }
  const rsi = gain === 0 && loss === 0 ? 50 : loss === 0 ? 100 : gain === 0 ? 0 : 100 - 100 / (1 + gain / loss);
  const fast = ema(closes, 12); const slow = ema(closes, 26);
  const macdValues = closes.slice(25).map((_, i) => fast[i + 25] - slow[i + 25]);
  const line = macdValues.at(-1)!; const signal = ema(macdValues, 9).at(-1)!;
  const movingAverages = {sma20: mean(closes.slice(-20)), sma50: mean(closes.slice(-50)), sma200: mean(closes.slice(-200))};
  const latest = closes.at(-1)!; const previous20 = closes.slice(-21, -1); const previous60 = closes.slice(-61, -1);
  const supportZone = {low: Math.min(...previous60), high: Math.min(...previous20), basis: 'Prior 60-day and 20-day closing lows; excludes the latest close'};
  const resistanceZone = {low: Math.max(...previous20), high: Math.max(...previous60), basis: 'Prior 20-day and 60-day closing highs; excludes the latest close'};
  const above = Object.values(movingAverages).filter(value => latest > value).length;
  const below = Object.values(movingAverages).filter(value => latest < value).length;
  const trend = above === 3 ? 'uptrend' : below === 3 ? 'downtrend' : 'mixed';
  const confluence = [
    `Close is above ${above} and below ${below} of the 20, 50 and 200-day moving averages.`,
    `RSI14 is ${rsi.toFixed(1)}: ${rsi >= 70 ? 'above the conventional overbought threshold; this alone is not a sell signal' : rsi <= 30 ? 'below the conventional oversold threshold; this alone is not a buy signal' : 'between the conventional 30 and 70 thresholds'}.`,
    `MACD is ${line > signal ? 'above' : line < signal ? 'below' : 'equal to'} its signal line.`,
    latest > resistanceZone.high ? 'Close exceeds the previous 60-day closing high.' : latest < supportZone.low ? 'Close is below the previous 60-day closing low.' : 'Close remains within the previous 60-day closing range.',
  ];
  return {trend, rsi, macd: {line, signal, histogram: line - signal}, movingAverages, supportZone, resistanceZone, confluence};
}

export function buildTechnicalPairs(dataset: HistoryDataset, now = new Date()): {pairs: PairAnalysis[]; technicalAsOf: string} {
  const rows = dataset.points;
  if (!Array.isArray(rows) || rows.length < 200) throw new Error('At least 200 consecutive completed daily observations are required.');
  if (!Number.isFinite(now.getTime())) throw new Error('Analysis time is invalid.');
  let previous = 0;
  for (const row of rows) {
    const completed = Date.parse(`${row.date}T00:00:00.000Z`) + DAY;
    if (!Number.isFinite(completed) || new Date(completed - DAY).toISOString().slice(0, 10) !== row.date || (previous && completed - previous !== DAY)) throw new Error('Chart dates must be valid, consecutive and aligned.');
    if (completed > now.getTime() || CRYPTO_ASSETS.some(asset => !Number.isFinite(row.prices[asset]) || row.prices[asset] <= 0)) throw new Error('Chart inputs contain unfinished candles or invalid prices.');
    previous = completed;
  }
  if (now.getTime() - previous > 36 * 3_600_000) throw new Error('Completed chart history is stale.');
  const pairs = PAIRS.map(([base, quote]): PairAnalysis => {
    const series = rows.map(row => ({date: row.date, value: row.prices[base] / (quote === 'CAD' ? 1 : row.prices[quote])}));
    const closes = series.map(point => point.value); const latest = closes.at(-1)!;
    return {id: `${base}/${quote}` as PairAnalysis['id'], label: `${base} / ${quote}`, base, quote, series, latest,
      changePercent: (latest / closes.at(-2)! - 1) * 100, technical: closeIndicators(closes),
      sentiment: {status: 'unavailable', score: null, label: 'Headline context not loaded', asOf: null, articles: []}};
  });
  return {pairs, technicalAsOf: new Date(previous).toISOString()};
}
