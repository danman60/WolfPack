import { CRYPTO_ASSETS, type Cadence, type CryptoAsset, type HistoryDataset } from './contract';

const DAY = 86_400_000;
export function forecastHorizon(date: string, cadence: Cadence): string {
  const d = new Date(date);
  if (cadence === 'weekly') d.setUTCDate(d.getUTCDate() + 7);
  else {
    const day = d.getUTCDate(); d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() + 1);
    const last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
    d.setUTCDate(Math.min(day, last));
  }
  return d.toISOString();
}
function solve(matrix: number[][], rhs: number[]): number[] {
  const a = matrix.map((row, i) => [...row, rhs[i]]);
  for (let col = 0; col < rhs.length; col++) {
    let pivot = col;
    for (let r = col + 1; r < rhs.length; r++) if (Math.abs(a[r][col]) > Math.abs(a[pivot][col])) pivot = r;
    [a[col], a[pivot]] = [a[pivot], a[col]];
    if (Math.abs(a[col][col]) < 1e-15) throw new Error('Forecast regression is singular.');
    const divisor = a[col][col]; a[col] = a[col].map(v => v / divisor);
    for (let r = 0; r < rhs.length; r++) if (r !== col) {
      const factor = a[r][col]; a[r] = a[r].map((v, j) => v - factor * a[col][j]);
    }
  }
  return a.map(row => row[rhs.length]);
}
export type ForecastFit = {forecastReturns: Record<CryptoAsset, number>; members: Record<string, Record<CryptoAsset, number>>; trainingOrigins: number; signalAt: string; latestTrainingEnd: string};
/** Source dates label candle START; every feature and maturity comparison uses its completed close. */
export function fitForecast(dataset: HistoryDataset, cadence: Cadence, now = new Date()): ForecastFit {
  const rows = dataset.points;
  if (rows.length < 460) throw new Error('At least 460 consecutive completed daily prices are required.');
  const times = rows.map(row => Date.parse(`${row.date}T00:00:00.000Z`) + DAY);
  rows.forEach((row, i) => {
    if (!Number.isFinite(times[i]) || new Date(times[i] - DAY).toISOString().slice(0, 10) !== row.date || (i > 0 && times[i] - times[i - 1] !== DAY)) throw new Error('Daily history must have consecutive valid candle dates.');
    if (times[i] > now.getTime() || CRYPTO_ASSETS.some(asset => !Number.isFinite(row.prices[asset]) || row.prices[asset] <= 0)) throw new Error('History contains unfinished candles or invalid prices.');
  });
  const through = rows.length - 1;
  if (now.getTime() - times[through] > 36 * 3_600_000) throw new Error('Completed daily history is stale.');
  function feature(i: number, asset: CryptoAsset): number[] {
    const price = rows[i].prices[asset];
    const daily = Array.from({length: 30}, (_, n) => Math.log(rows[i - n].prices[asset] / rows[i - n - 1].prices[asset]));
    const mean = daily.reduce((a, b) => a + b, 0) / 30;
    const vol = Math.sqrt(daily.reduce((a, b) => a + (b - mean) ** 2, 0) / 29);
    const sma = rows.slice(i - 199, i + 1).reduce((sum, row) => sum + row.prices[asset], 0) / 200;
    return [7, 30, 90].map(days => Math.log(price / rows[i - days].prices[asset])).concat(vol, Math.log(price / sma));
  }
  const indices = new Map(times.map((time, i) => [time, i]));
  const x: number[][] = []; const y: number[] = []; let trainingOrigins = 0; let latestEnd = 0;
  for (let i = Math.max(199, through - 730); i < through; i++) {
    const endTime = Date.parse(forecastHorizon(new Date(times[i]).toISOString(), cadence)) + DAY;
    const end = indices.get(endTime);
    if (end === undefined || end >= through) continue;
    trainingOrigins++; latestEnd = Math.max(latestEnd, endTime);
    for (const asset of CRYPTO_ASSETS) { x.push(feature(i, asset)); y.push(rows[end].prices[asset] / rows[i + 1].prices[asset] - 1); }
  }
  if (trainingOrigins < 252) throw new Error(`Only ${trainingOrigins} mature training dates; at least 252 are required.`);
  const means = Array.from({length: 5}, (_, j) => x.reduce((sum, row) => sum + row[j], 0) / x.length);
  const scales = means.map((mean, j) => Math.sqrt(x.reduce((sum, row) => sum + (row[j] - mean) ** 2, 0) / x.length)).map(sd => sd < 1e-12 ? 1 : sd);
  const z = x.map(row => row.map((v, j) => (v - means[j]) / scales[j]));
  const intercept = y.reduce((a, b) => a + b, 0) / y.length;
  const members: ForecastFit['members'] = {};
  for (const alpha of [1, 10]) {
    const gram = means.map((_, j) => means.map((__, k) => z.reduce((sum, row) => sum + row[j] * row[k], 0) / z.length + (j === k ? alpha : 0)));
    const rhs = means.map((_, j) => z.reduce((sum, row, i) => sum + row[j] * (y[i] - intercept), 0) / z.length);
    const beta = solve(gram, rhs);
    members[String(alpha)] = Object.fromEntries(CRYPTO_ASSETS.map(asset => [asset, Math.max(-1, intercept + feature(through, asset).reduce((sum, v, j) => sum + (v - means[j]) / scales[j] * beta[j], 0))])) as Record<CryptoAsset, number>;
  }
  const forecastReturns = Object.fromEntries(CRYPTO_ASSETS.map(asset => [asset, (members['1'][asset] + members['10'][asset]) / 2])) as Record<CryptoAsset, number>;
  if (Object.values(forecastReturns).some(v => !Number.isFinite(v))) throw new Error('Forecast produced a non-finite estimate.');
  return {forecastReturns, members, trainingOrigins, signalAt: new Date(times[through]).toISOString(), latestTrainingEnd: new Date(latestEnd).toISOString()};
}

export function forecastFingerprintSource(): string { return [fitForecast, forecastHorizon, solve].map(fn => fn.toString()).join("\n"); }
