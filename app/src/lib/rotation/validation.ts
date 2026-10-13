import { CRYPTO_ASSETS, type Asset, type CryptoAsset, type DailyPoint, type HistoryDataset, type ResearchConfig } from "./contract";
import { replayFingerprintSource, runResearch } from "./replay";
import { RESEARCH_VERSION, type ChronologicalFold, type EvaluationDecision, type OutcomeSummary, type PairedForecast, type ResearchProtocol, type ResearchScenario, type ValidationReport } from "./research-contract";

const DAY_MS = 86_400_000;
type Holdings = Record<Asset, number>;
type Marks = Record<CryptoAsset, number>;
type Path = { review: number; entry: number; end: number };

export function calendarDay(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) throw new Error("Invalid scenario timestamp.");
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Toronto", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  return ["year", "month", "day"].map((name) => parts.find((part) => part.type === name)!.value).join("-");
}

export function shiftDay(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

export function shiftMonth(date: string, months: number): string {
  const source = new Date(`${date}T00:00:00Z`);
  const target = new Date(Date.UTC(source.getUTCFullYear(), source.getUTCMonth() + months, 1));
  const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(source.getUTCDate(), lastDay));
  return target.toISOString().slice(0, 10);
}

function checked(value: number): number {
  if (!Number.isFinite(value)) throw new Error("Research arithmetic exceeded its finite range.");
  return value;
}

function value(holdings: Holdings, prices: Marks): number {
  return checked(CRYPTO_ASSETS.reduce((sum, asset) => sum + holdings[asset] * prices[asset], holdings.CAD));
}

function endowment(config: ResearchConfig, prices: Marks): Holdings {
  const risk = config.riskPercent / 100;
  const holdings: Holdings = { CAD: config.capitalCad * (1 - risk), BTC: 0, ETH: 0, LINK: 0 };
  for (const asset of CRYPTO_ASSETS) holdings[asset] = config.capitalCad * risk / 3 / prices[asset];
  return holdings;
}

function selected(history: DailyPoint[], through: number, config: ResearchConfig): Asset {
  if (config.riskPercent === 0) return "CAD";
  const ranked = CRYPTO_ASSETS.map((asset) => ({ asset, change: history[through].prices[asset] / history[through - config.lookbackDays].prices[asset] - 1 }))
    .sort((a, b) => b.change - a.change || CRYPTO_ASSETS.indexOf(a.asset) - CRYPTO_ASSETS.indexOf(b.asset));
  return ranked[0].change > 0 ? ranked[0].asset : "CAD";
}

// One recommendation: compare changing a copy of these units against leaving
// these same units untouched for one horizon. Never add overlapping comparisons.
function paired(initial: Holdings, marks: Marks, path: Path, history: DailyPoint[], target: Asset, config: ResearchConfig) {
  const entry = {} as Marks;
  const end = {} as Marks;
  for (const asset of CRYPTO_ASSETS) {
    entry[asset] = checked(marks[asset] * history[path.entry].prices[asset] / history[path.review].prices[asset]);
    end[asset] = checked(marks[asset] * history[path.end].prices[asset] / history[path.review].prices[asset]);
  }
  const shifted = { ...initial };
  const risk = config.riskPercent / 100;
  const buyFactor = (1 + config.slippageBps / 10_000) * (1 + config.feeBps / 10_000);
  const sellFactor = (1 - config.slippageBps / 10_000) * (1 - config.feeBps / 10_000);
  for (const asset of CRYPTO_ASSETS) {
    if (asset !== target && shifted[asset] * entry[asset] >= 0.01) {
      shifted.CAD += shifted[asset] * entry[asset] * sellFactor;
      shifted[asset] = 0;
    }
  }
  if (target !== "CAD") {
    const total = value(shifted, entry);
    const held = shifted[target] * entry[target];
    const buy = (risk * total - held) / (1 + risk * (buyFactor - 1));
    if (buy >= 0.01) {
      const spentAtMid = Math.min(buy, shifted.CAD / buyFactor);
      shifted[target] += spentAtMid / entry[target];
      shifted.CAD = Math.max(0, shifted.CAD - spentAtMid * buyFactor);
    } else if (buy < 0) {
      const sell = Math.min(held, (held - risk * total) / (1 - risk * (1 - sellFactor)));
      if (sell >= 0.01) {
        shifted[target] = Math.max(0, shifted[target] - sell / entry[target]);
        shifted.CAD += sell * sellFactor;
      }
    }
  }
  const opening = value(initial, marks);
  const shift = checked(value(shifted, end) - opening);
  const hold = checked(value(initial, end) - opening);
  return { shift, hold, advantage: checked(shift - hold) };
}

function quantile(sorted: number[], fraction: number): number {
  const at = (sorted.length - 1) * fraction;
  const low = Math.floor(at);
  return checked(sorted[low] + (sorted[Math.ceil(at)] - sorted[low]) * (at - low));
}

function summary(values: number[]): OutcomeSummary {
  if (!values.length) throw new Error("There are no completed earlier horizons to estimate outcomes.");
  const sorted = [...values].sort((a, b) => a - b);
  return { meanCad: checked(values.reduce((sum, item) => sum + item / values.length, 0)), downside10Cad: quantile(sorted, 0.1), upper90Cad: quantile(sorted, 0.9) };
}

function paths(dataset: HistoryDataset, config: ResearchConfig): Path[] {
  const history = dataset.points;
  const start = config.lookbackDays + 1;
  const reviews = history.map((point, i) => i >= start && (i === start || (config.cadence === "weekly"
    ? (i - start) % 7 === 0 : point.date.slice(0, 7) !== history[i - 1].date.slice(0, 7))) ? i : -1).filter((i) => i >= 0);
  return reviews.slice(0, -1).map((review, i) => ({ review, entry: review + 1, end: reviews[i + 1] }))
    .filter((path) => path.end > path.entry);
}

function evaluate(dataset: HistoryDataset, config: ResearchConfig, from: string, through: string): EvaluationDecision[] {
  const history = dataset.points;
  const allPaths = paths(dataset, config);
  const decisions: EvaluationDecision[] = [];
  for (const path of allPaths) {
    const review = history[path.review].date;
    if (review < from || history[path.end].date > through) continue;
    // Purge labels whose horizon is still running at the review; a label ending
    // on the review's own close also cannot enter this prior-day model.
    const training = allPaths.filter((past) => past.end < path.review);
    if (training.length < 3) continue;
    const target = selected(history, path.review - 1, config);
    const marks = history[path.review].prices;
    const initial = endowment(config, marks);
    const estimates = training.map((past) => paired(initial, marks, past, history, target, config));
    const predicted = summary(estimates.map((outcome) => outcome.advantage));
    const observed = paired(initial, marks, path, history, target, config);
    decisions.push({ review, end: history[path.end].date, target,
      trainingThrough: history[training.at(-1)!.end].date, trainingObservations: training.length,
      predictedAdvantageCad: predicted.meanCad, downside10Cad: predicted.downside10Cad, upper90Cad: predicted.upper90Cad,
      observedAdvantageCad: observed.advantage, observedShiftCad: observed.shift, observedHoldCad: observed.hold,
      covered: observed.advantage >= predicted.downside10Cad && observed.advantage <= predicted.upper90Cad,
    });
  }
  return decisions;
}

function fold(decisions: EvaluationDecision[], start: string, end: string, kind: ChronologicalFold["kind"]): ChronologicalFold {
  const rows = decisions.filter((decision) => decision.review >= start && decision.end <= end);
  return { start, end, kind, decisions: rows.length,
    meanAdvantageCad: rows.length ? checked(rows.reduce((sum, row) => sum + row.observedAdvantageCad / rows.length, 0)) : null,
    meanAbsoluteErrorCad: rows.length ? checked(rows.reduce((sum, row) => sum + Math.abs(row.predictedAdvantageCad - row.observedAdvantageCad) / rows.length, 0)) : null,
    intervalCoveragePercent: rows.length ? rows.filter((row) => row.covered).length / rows.length * 100 : null,
  };
}

function forecast(dataset: HistoryDataset, config: ResearchConfig, scenario?: ResearchScenario): PairedForecast {
  const history = dataset.points;
  const start = scenario ? calendarDay(scenario.asOf) : history.at(-1)!.date;
  let through = history.length - 1;
  while (through >= 0 && history[through].date >= start) through -= 1;
  if (through < config.lookbackDays) throw new Error("Scenario date precedes the available signal history.");
  const target = selected(history, through, config);
  const training = paths(dataset, config).filter((path) => path.end <= through);
  if (!training.length) throw new Error("The scenario date has no completed earlier review horizons.");
  const marks = scenario?.marks ?? history.at(-1)!.prices;
  const initial = scenario ? { CAD: Number(scenario.balances.CAD), BTC: Number(scenario.balances.BTC), ETH: Number(scenario.balances.ETH), LINK: Number(scenario.balances.LINK) } : endowment(config, marks);
  for (const asset of ["CAD", ...CRYPTO_ASSETS] as const) {
    if (!Number.isFinite(initial[asset]) || initial[asset] < 0) throw new Error("Scenario holdings must be finite and nonnegative.");
  }
  for (const asset of CRYPTO_ASSETS) if (!Number.isFinite(marks[asset]) || marks[asset] <= 0) throw new Error("Scenario prices must be positive and finite.");
  const startingValueCad = value(initial, marks);
  if (startingValueCad <= 0) throw new Error("Scenario needs positive portfolio value.");
  const outcomes = training.map((path) => paired(initial, marks, path, history, target, config));
  return { status: "unvalidated", target, start,
    horizonEnd: config.cadence === "weekly" ? shiftDay(start, 7) : shiftMonth(start, 1),
    signalThrough: history[through].date, trainingThrough: history[training.at(-1)!.end].date,
    observations: training.length, startingValueCad, basis: scenario ? "entered-portfolio" : "equal-basket-scenario",
    shift: summary(outcomes.map((outcome) => outcome.shift)), hold: summary(outcomes.map((outcome) => outcome.hold)), advantage: summary(outcomes.map((outcome) => outcome.advantage)),
    note: "Unvalidated empirical scenarios, not a reliable profit forecast. Each earlier completed horizon contributes its joint BTC/ETH/LINK return path; no randomized split, return extrapolation, parameter search or advanced ML. Means are historical sample averages. The 10th percentile is an observed-sample downside scenario, not a loss bound or calibrated probability. Shift and HOLD copy exactly the same starting units. Shift waits one observed day, then changes to the configured allocation with adverse slippage and a fee per leg; HOLD leaves those units unchanged. Monthly samples use calendar-month reviews (28–31 days, with a possible shorter first sample); the stated future horizon uses one calendar month. These isolated recommendation comparisons are separate from the continual replay and must not be summed as portfolio profit.",
  };
}

export function runValidation(dataset: HistoryDataset, config: ResearchConfig, scenario?: ResearchScenario): ValidationReport {
  const replay = runResearch(dataset, config); // Shared strict input/gap validation.
  if (dataset.points.length < 575) throw new Error("Chronological validation requires at least 575 consecutive observed dates for a 365-day initial prefix, development folds and an exposed 180-day tail.");
  const firstTestDate = dataset.points[365].date;
  const exposedTailStart = dataset.points[dataset.points.length - 180].date;
  const decisions = evaluate(dataset, config, firstTestDate, dataset.coverageEnd);
  const folds: ChronologicalFold[] = [];
  for (let start = firstTestDate; start < exposedTailStart; start = shiftDay(start, 60)) {
    const end = [shiftDay(start, 59), shiftDay(exposedTailStart, -1)].sort()[0];
    folds.push(fold(decisions, start, end, "walk-forward"));
  }
  folds.push(fold(decisions, exposedTailStart, dataset.coverageEnd, "exposed-tail"));
  return { protocolVersion: RESEARCH_VERSION, status: "unvalidated", trainingStart: dataset.coverageStart,
    firstTestDate, exposedTailStart, folds, decisions, forecast: forecast(dataset, config, scenario), replay,
    note: "Frozen candidate and empirical estimator v1. The first 365 observed days precede evaluation; chronological 60-day development folds follow, then the final 180 historical days are reported separately. Training refits the empirical distribution at each review using only labels ending before that review. No hyperparameter optimization. Historical data was previously inspected by the application, so all these results are retrospective, including the final tail; none is an untouched final test. Each row compares a fresh identical equal-basket endowment for one non-overlapping review horizon; row profits cannot be added into a continuous portfolio return. The separate continual replay preserves its original HOLD units. Coverage is the observed fraction inside the prior-sample 10–90% incremental range, not a confidence score. Few monthly decisions and serial market dependence prevent a calibrated skill claim. A separate registered 12-calendar-month forward holdout must finish before its result can be opened. Actual holdings are used only in the latest scenario when supplied, never substituted into historical trial endowments.",
  };
}

export function evaluateHoldout(dataset: HistoryDataset, protocol: ResearchProtocol) {
  runResearch(dataset, protocol.config);
  if (dataset.coverageEnd < protocol.forwardHoldoutEnd) throw new Error(`Forward holdout is sealed until completed data reaches ${protocol.forwardHoldoutEnd}.`);
  if (dataset.coverageStart > protocol.dataset.coverageStart) throw new Error("The registered training archive must be included before holdout evaluation.");
  const decisions = evaluate(dataset, protocol.config, protocol.forwardHoldoutStart, protocol.forwardHoldoutEnd);
  return { decisions, folds: [fold(decisions, protocol.forwardHoldoutStart, protocol.forwardHoldoutEnd, "prospective-holdout")],
    note: "First opening of the registered future period. Configuration and training archive were frozen before this period; the predetermined estimator refits using earlier completed labels only. These are per-recommendation paired outcomes, not additive portfolio returns. This record consumes the holdout: any tuning based on it requires a newly registered future period. Sample coverage and performance do not establish reliable future profit.",
  };
}

/** Conservative executable fingerprint: compile transformations can invalidate a
 * protocol too. Never silently substitute revised logic into an old holdout.
 * Add every new implementation helper here and bump RESEARCH_VERSION on changes. */
export function evaluatorFingerprintSource(): string {
  return JSON.stringify({ version: RESEARCH_VERSION, dayMs: DAY_MS, assets: CRYPTO_ASSETS }) + replayFingerprintSource() +
    [calendarDay, shiftDay, shiftMonth, checked, value, endowment, selected, paired, quantile, summary, paths, evaluate, fold, forecast, runValidation, evaluateHoldout].map((fn) => fn.toString()).join("\n");
}
