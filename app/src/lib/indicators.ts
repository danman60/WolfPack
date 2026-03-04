/** Pure math indicator functions for trading charts. */

export interface OHLCData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface LinePoint {
  time: number;
  value: number;
}

/** Simple Moving Average */
export function sma(data: OHLCData[], period: number): LinePoint[] {
  const result: LinePoint[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close;
    }
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}

/** Exponential Moving Average */
export function ema(data: OHLCData[], period: number): LinePoint[] {
  const result: LinePoint[] = [];
  const k = 2 / (period + 1);

  if (data.length === 0) return result;

  // Seed with SMA of first `period` items
  let sum = 0;
  for (let i = 0; i < Math.min(period, data.length); i++) {
    sum += data[i].close;
  }
  let prev = sum / Math.min(period, data.length);
  result.push({ time: data[Math.min(period - 1, data.length - 1)].time, value: prev });

  for (let i = period; i < data.length; i++) {
    prev = data[i].close * k + prev * (1 - k);
    result.push({ time: data[i].time, value: prev });
  }
  return result;
}

/** Bollinger Bands */
export function bollingerBands(
  data: OHLCData[],
  period: number = 20,
  mult: number = 2,
): { upper: LinePoint[]; middle: LinePoint[]; lower: LinePoint[] } {
  const upper: LinePoint[] = [];
  const middle: LinePoint[] = [];
  const lower: LinePoint[] = [];

  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    const avg = sum / period;

    let variance = 0;
    for (let j = 0; j < period; j++) variance += (data[i - j].close - avg) ** 2;
    const std = Math.sqrt(variance / period);

    const t = data[i].time;
    upper.push({ time: t, value: avg + mult * std });
    middle.push({ time: t, value: avg });
    lower.push({ time: t, value: avg - mult * std });
  }

  return { upper, middle, lower };
}

/** RSI (Relative Strength Index) */
export function rsi(data: OHLCData[], period: number = 14): LinePoint[] {
  const result: LinePoint[] = [];
  if (data.length < period + 1) return result;

  let avgGain = 0;
  let avgLoss = 0;

  // Initial average
  for (let i = 1; i <= period; i++) {
    const diff = data[i].close - data[i - 1].close;
    if (diff >= 0) avgGain += diff;
    else avgLoss -= diff;
  }
  avgGain /= period;
  avgLoss /= period;

  const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  result.push({ time: data[period].time, value: 100 - 100 / (1 + rs) });

  // Subsequent values
  for (let i = period + 1; i < data.length; i++) {
    const diff = data[i].close - data[i - 1].close;
    const gain = diff >= 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    const rsVal = avgLoss === 0 ? 100 : avgGain / avgLoss;
    result.push({ time: data[i].time, value: 100 - 100 / (1 + rsVal) });
  }

  return result;
}

/** MACD (Moving Average Convergence Divergence) */
export function macd(
  data: OHLCData[],
  fast: number = 12,
  slow: number = 26,
  signal: number = 9,
): { macdLine: LinePoint[]; signalLine: LinePoint[]; histogram: LinePoint[] } {
  const fastEma = ema(data, fast);
  const slowEma = ema(data, slow);

  // Align by time
  const slowMap = new Map(slowEma.map((p) => [p.time, p.value]));
  const macdRaw: LinePoint[] = [];
  for (const fp of fastEma) {
    const sv = slowMap.get(fp.time);
    if (sv !== undefined) {
      macdRaw.push({ time: fp.time, value: fp.value - sv });
    }
  }

  // Signal line = EMA of MACD
  const signalLine: LinePoint[] = [];
  if (macdRaw.length >= signal) {
    const k = 2 / (signal + 1);
    let sum = 0;
    for (let i = 0; i < signal; i++) sum += macdRaw[i].value;
    let prev = sum / signal;
    signalLine.push({ time: macdRaw[signal - 1].time, value: prev });

    for (let i = signal; i < macdRaw.length; i++) {
      prev = macdRaw[i].value * k + prev * (1 - k);
      signalLine.push({ time: macdRaw[i].time, value: prev });
    }
  }

  // Histogram
  const sigMap = new Map(signalLine.map((p) => [p.time, p.value]));
  const histogram: LinePoint[] = [];
  for (const mp of macdRaw) {
    const sv = sigMap.get(mp.time);
    if (sv !== undefined) {
      histogram.push({ time: mp.time, value: mp.value - sv });
    }
  }

  return { macdLine: macdRaw, signalLine, histogram };
}
