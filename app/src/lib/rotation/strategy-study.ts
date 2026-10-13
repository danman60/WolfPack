import { CRYPTO_ASSETS, type Asset, type DailyPoint, type HistoryDataset } from "./contract";
import { runResearch } from "./replay";
import type { OutcomeSummary, ResearchScenario } from "./research-contract";
import { calendarDay, evaluatorFingerprintSource, shiftDay, shiftMonth } from "./validation";
import { STRATEGY_STUDY_VERSION, type CandidateScore, type StrategyCandidateId, type StrategyChoice, type StrategyPlan, type StrategyStudyConfig, type StrategyStudyReport, type StudyBlock, type StudyMetric, type StudyPoint, type StudyReview } from "./strategy-contract";

const WINDOWS = [14, 30, 60, 90, 180] as const;
const COMMON_START = 181;
const OUTER_START = 365;
const BLOCK_DAYS = 60;
const MIN_BLOCKS = 3;
const MIN_HORIZONS = 12;
type Units = Record<Asset, number>;
type Marks = DailyPoint["prices"];
type Account = { units: Units; fees: number; turnover: number; trades: number; lastTarget: Asset | "mix" };
type Replay = { metrics: StudyMetric; points: StudyPoint[]; reviews: StudyReview[] };

function finite(value: number): number {
  if (!Number.isFinite(value)) throw new Error("Strategy study arithmetic must remain finite.");
  return value;
}

function value(units: Units, marks: Marks): number {
  return finite(CRYPTO_ASSETS.reduce((total, asset) => total + units[asset] * marks[asset], units.CAD));
}

function endowment(config: StrategyStudyConfig, marks: Marks): Units {
  const units: Units = { CAD: config.capitalCad * (1 - config.riskPercent / 100), BTC: 0, ETH: 0, LINK: 0 };
  for (const asset of CRYPTO_ASSETS) units[asset] = config.capitalCad * config.riskPercent / 300 / marks[asset];
  return units;
}

function account(units: Units): Account {
  return { units: { ...units }, fees: 0, turnover: 0, trades: 0, lastTarget: "mix" };
}

function sell(state: Account, asset: typeof CRYPTO_ASSETS[number], notional: number, marks: Marks, config: StrategyStudyConfig): void {
  if (notional < 0.01) return;
  const quantity = Math.min(state.units[asset], notional / marks[asset]);
  const gross = quantity * marks[asset] * (1 - config.slippageBps / 10_000);
  const fee = gross * config.feeBps / 10_000;
  state.units[asset] = Math.max(0, state.units[asset] - quantity);
  state.units.CAD += gross - fee;
  state.fees += fee; state.turnover += gross; state.trades += 1;
}

/** Same cost convention as v1 replay: post-cost target, fee per leg, no debt. */
function shift(state: Account, target: Asset, marks: Marks, config: StrategyStudyConfig): void {
  if (state.lastTarget === target) return;
  for (const asset of CRYPTO_ASSETS) if (asset !== target) sell(state, asset, state.units[asset] * marks[asset], marks, config);
  if (target !== "CAD") {
    const risk = config.riskPercent / 100;
    const total = value(state.units, marks);
    const held = state.units[target] * marks[target];
    const cost = (1 + config.slippageBps / 10_000) * (1 + config.feeBps / 10_000);
    const buy = (risk * total - held) / (1 + risk * (cost - 1));
    if (buy >= 0.01) {
      const notional = Math.min(buy, state.units.CAD / cost);
      if (notional >= 0.01) {
        const gross = notional * (1 + config.slippageBps / 10_000);
        const fee = gross * config.feeBps / 10_000;
        state.units[target] += notional / marks[target];
        state.units.CAD = Math.max(0, state.units.CAD - gross - fee);
        state.fees += fee; state.turnover += gross; state.trades += 1;
      }
    } else if (buy < 0) {
      const proceeds = (1 - config.slippageBps / 10_000) * (1 - config.feeBps / 10_000);
      sell(state, target, (held - risk * total) / (1 - risk * (1 - proceeds)), marks, config);
    }
  }
  state.lastTarget = target;
  for (const units of Object.values(state.units)) if (!Number.isFinite(units) || units < 0) throw new Error("Strategy study produced invalid inventory.");
}

function candidateId(window: number): StrategyCandidateId {
  return `momentum-${window}` as StrategyCandidateId;
}

function windowFor(choice: StrategyCandidateId): number {
  const window = Number(choice.slice("momentum-".length));
  if (!WINDOWS.some((item) => item === window)) throw new Error("Unknown strategy candidate.");
  return window;
}

function target(history: DailyPoint[], through: number, choice: StrategyCandidateId, config: StrategyStudyConfig): Asset {
  if (config.riskPercent === 0) return "CAD";
  const window = windowFor(choice);
  const ranked = CRYPTO_ASSETS.map((asset) => ({ asset, change: history[through].prices[asset] / history[through - window].prices[asset] - 1 }))
    .sort((a, b) => b.change - a.change || CRYPTO_ASSETS.indexOf(a.asset) - CRYPTO_ASSETS.indexOf(b.asset));
  return ranked[0].change > 0 ? ranked[0].asset : "CAD";
}

function isReview(history: DailyPoint[], index: number, start: number, config: StrategyStudyConfig): boolean {
  return index === start || (config.cadence === "weekly" ? (index - start) % 7 === 0 : history[index].date.slice(0, 7) !== history[index - 1].date.slice(0, 7));
}

function horizon(date: string, config: StrategyStudyConfig): string {
  return config.cadence === "weekly" ? shiftDay(date, 7) : shiftMonth(date, 1);
}

function nextReview(date: string, anchor: string, config: StrategyStudyConfig): string {
  if (config.cadence === "monthly") return date.endsWith("-01") ? date : shiftMonth(`${date.slice(0, 7)}-01`, 1);
  const days = (Date.parse(`${date}T00:00:00Z`) - Date.parse(`${anchor}T00:00:00Z`)) / 86_400_000;
  return shiftDay(date, (7 - days % 7) % 7);
}

function completeReview(review: StudyReview, end: string, config: StrategyStudyConfig): boolean {
  // Skip an initial partial calendar month: count only non-overlapping complete
  // monthly reviews on the first day, or complete seven-day weekly horizons.
  return review.horizonEnd <= end && (config.cadence === "weekly" || review.date.endsWith("-01"));
}

function replay(history: DailyPoint[], start: number, end: number, config: StrategyStudyConfig, choose: (index: number) => StrategyChoice): Replay {
  const initial = endowment(config, history[start].prices);
  const state = account(initial);
  const cash = account(initial);
  const points: StudyPoint[] = [];
  const reviews: StudyReview[] = [];
  let pending: { at: number; asset: Asset } | undefined;
  let peak = config.capitalCad;
  let drawdown = 0;
  for (let index = start; index <= end; index += 1) {
    const day = history[index];
    // Execution of a previously reviewed decision survives a block boundary.
    // A newly selected policy only produces orders on the agreed cadence.
    if (pending?.at === index) { shift(state, pending.asset, day.prices, config); pending = undefined; }
    if (index === start + 1) shift(cash, "CAD", day.prices, config);
    const marked = value(state.units, day.prices);
    peak = Math.max(peak, marked);
    drawdown = Math.max(drawdown, (peak - marked) / peak * 100);
    points.push({ date: day.date, strategyCad: marked, holdCad: value(initial, day.prices), cashCad: value(cash.units, day.prices) });
    if (isReview(history, index, start, config)) {
      const selected = choose(index);
      const asset = selected === "hold" ? null : target(history, index - 1, selected, config);
      const review: StudyReview = { date: day.date, signalThrough: history[index - 1].date, selected, target: asset,
        executeDate: shiftDay(day.date, 1), horizonEnd: horizon(day.date, config), completed: false };
      review.completed = completeReview(review, history[end].date, config);
      reviews.push(review);
      if (asset !== null) pending = { at: index + 1, asset };
    }
  }
  const final = points.at(-1)!;
  const metrics: StudyMetric = { finalCad: final.strategyCad, holdCad: final.holdCad, cashCad: final.cashCad,
    excessHoldCad: final.strategyCad - final.holdCad, excessCashCad: final.strategyCad - final.cashCad,
    feesCad: state.fees, turnoverCad: state.turnover, trades: state.trades,
    maxDrawdownPercent: drawdown, completedReviews: reviews.filter((review) => review.completed).length };
  for (const metric of Object.values(metrics)) finite(metric);
  return { metrics, points, reviews };
}

function scores(history: DailyPoint[], end: number, config: StrategyStudyConfig): CandidateScore[] {
  return WINDOWS.map((window) => {
    const id = candidateId(window);
    const { metrics } = replay(history, COMMON_START, end, config, () => id);
    return { candidateId: id, lookbackDays: window, metrics, scoreCad: Math.min(metrics.excessHoldCad, metrics.excessCashCad) };
  });
}

function select(rows: CandidateScore[]): StrategyChoice {
  const ranked = [...rows].sort((a, b) => b.scoreCad - a.scoreCad || a.lookbackDays - b.lookbackDays);
  return ranked[0].scoreCad > 0 ? ranked[0].candidateId : "hold";
}

function summarize(values: number[]): OutcomeSummary {
  const sorted = [...values].sort((a, b) => a - b);
  const quantile = (fraction: number) => {
    const at = (sorted.length - 1) * fraction;
    const low = Math.floor(at);
    return finite(sorted[low] + (sorted[Math.ceil(at)] - sorted[low]) * (at - low));
  };
  return { meanCad: finite(values.reduce((sum, number) => sum + number / values.length, 0)), downside10Cad: quantile(0.1), upper90Cad: quantile(0.9) };
}

function paired(history: DailyPoint[], through: number, initial: Units, marks: Marks, asset: Asset, config: StrategyStudyConfig): StrategyPlan["paired"] {
  const shifts: number[] = [], holds: number[] = [], differences: number[] = [];
  const indices = new Map(history.map((day, index) => [day.date, index]));
  const opening = value(initial, marks);
  for (let review = COMMON_START; review < through; review += 1) {
    if (!isReview(history, review, COMMON_START, config)) continue;
    if (config.cadence === "monthly" && !history[review].date.endsWith("-01")) continue;
    const end = indices.get(horizon(history[review].date, config));
    if (end === undefined || end > through || end <= review + 1) continue;
    const entryMarks = { ...marks }, finalMarks = { ...marks };
    for (const coin of CRYPTO_ASSETS) {
      entryMarks[coin] *= history[review + 1].prices[coin] / history[review].prices[coin];
      finalMarks[coin] *= history[end].prices[coin] / history[review].prices[coin];
    }
    const shifted = account(initial);
    shift(shifted, asset, entryMarks, config);
    const shiftProfit = value(shifted.units, finalMarks) - opening;
    const holdProfit = value(initial, finalMarks) - opening;
    shifts.push(shiftProfit); holds.push(holdProfit); differences.push(shiftProfit - holdProfit);
  }
  return shifts.length ? { target: asset, observations: shifts.length, shift: summarize(shifts), hold: summarize(holds), advantage: summarize(differences) } : null;
}

/** Frozen adaptive selector. Engineering gates are NOT statistical validation. */
export function runStrategyStudy(dataset: HistoryDataset, config: StrategyStudyConfig, scenario?: ResearchScenario): StrategyStudyReport {
  // Reuse v1's strict finite-input, real-calendar and gap checks without changing
  // that saved evaluator. Its arithmetic remains part of our source fingerprint.
  runResearch(dataset, { ...config, lookbackDays: 180 });
  // UTC-labeled daily bars can be completed during the same Eastern calendar
  // day. Exclude that label from a prior-day review instead of failing nightly
  // or allowing today's label into its signal/evidence.
  const scenarioDay = scenario ? calendarDay(scenario.asOf) : null;
  const history = scenarioDay ? dataset.points.filter((day) => day.date < scenarioDay) : dataset.points;
  if (history.length < OUTER_START + 2) throw new Error("Strategy comparison needs at least 367 consecutive observed daily dates before the scenario day.");
  const end = history.length - 1;
  const candidates = WINDOWS.map((window) => {
    const id = candidateId(window);
    const result = replay(history, COMMON_START, end, config, () => id);
    return { candidateId: id, lookbackDays: window, metrics: result.metrics, scoreCad: Math.min(result.metrics.excessHoldCad, result.metrics.excessCashCad), points: result.points };
  });
  const blocks: StudyBlock[] = [];
  for (let start = OUTER_START; start <= end; start += BLOCK_DAYS) {
    const ranked = scores(history, start - 1, config);
    const blockEnd = shiftDay(history[start].date, BLOCK_DAYS - 1);
    blocks.push({ start: history[start].date, end: blockEnd, trainingThrough: history[start - 1].date,
      selected: select(ranked), scores: ranked, completed: blockEnd <= history[end].date });
  }
  const outer = replay(history, OUTER_START, end, config, (index) => blocks[Math.floor((index - OUTER_START) / BLOCK_DAYS)].selected);
  const start = scenarioDay ?? shiftDay(history[end].date, 1);
  if (start !== shiftDay(history[end].date, 1)) throw new Error("Completed history must reach the day before the current scenario; stale data cannot generate a plan.");
  const nextReviewDate = nextReview(start, history[OUTER_START].date, config);
  const reviewDue = nextReviewDate === start;
  const marks = scenario ? { ...scenario.marks } : { ...history[end].prices };
  const initial = scenario ? { CAD: Number(scenario.balances.CAD), BTC: Number(scenario.balances.BTC), ETH: Number(scenario.balances.ETH), LINK: Number(scenario.balances.LINK) } : endowment(config, marks);
  for (const units of Object.values(initial)) if (!Number.isFinite(units) || units < 0) throw new Error("Scenario holdings must be finite and nonnegative.");
  for (const mark of Object.values(marks)) if (!Number.isFinite(mark) || mark <= 0) throw new Error("Scenario prices must be positive and finite.");
  const startingValueCad = value(initial, marks);
  if (startingValueCad <= 0) throw new Error("Scenario needs positive value.");
  // Preserve the adopted selector's block schedule. Tomorrow at a block boundary
  // may start a new selection; otherwise use the current block's frozen prefix.
  const nextIndex = history.length;
  const selectionStart = OUTER_START + Math.floor((nextIndex - OUTER_START) / BLOCK_DAYS) * BLOCK_DAYS;
  const selectionThrough = selectionStart - 1;
  const latestScores = scores(history, selectionThrough, config);
  const latestChoice = select(latestScores);
  const asset = latestChoice === "hold" ? null : target(history, end, latestChoice, config);
  const outcomes = asset === null ? null : paired(history, end, initial, marks, asset, config);
  const completedBlocks = blocks.filter((block) => block.completed).length;
  const reasons: string[] = [];
  if (!reviewDue) reasons.push("not-scheduled-review");
  if (completedBlocks < MIN_BLOCKS) reasons.push("insufficient-completed-outer-blocks");
  if (outer.metrics.completedReviews < MIN_HORIZONS) reasons.push("insufficient-completed-outer-horizons");
  if (outer.metrics.excessHoldCad <= 0) reasons.push("outer-selector-did-not-beat-hold");
  if (outer.metrics.excessCashCad <= 0) reasons.push("outer-selector-did-not-beat-costed-cad");
  if (latestChoice === "hold") reasons.push("no-positive-inner-edge-over-both-baselines");
  if (!outcomes || outcomes.advantage.meanCad <= 0) reasons.push("no-positive-current-paired-mean-advantage");
  const permitted = reasons.length === 0 && asset !== null;
  const weights: Units = { CAD: 1, BTC: 0, ETH: 0, LINK: 0 };
  if (permitted && asset !== "CAD") { weights.CAD = 1 - config.riskPercent / 100; weights[asset] = config.riskPercent / 100; }
  const plan: StrategyPlan = { status: permitted ? "experimental-shift" : "hold", validation: "retrospective-unvalidated",
    candidateId: latestChoice, target: permitted ? asset : null, targetWeights: permitted ? weights : null,
    reasons: permitted ? ["engineering-evidence-gates-passed-still-unvalidated"] : reasons,
    signalThrough: history[end].date, reviewDue, nextReviewDate, horizonStart: start, horizonEnd: horizon(start, config),
    basis: scenario ? "entered-portfolio" : "equal-basket-scenario", startingValueCad,
    outerCompletedBlocks: completedBlocks, outerCompletedReviews: outer.metrics.completedReviews, paired: outcomes };
  return { version: STRATEGY_STUDY_VERSION, exposure: "already-exposed", status: "retrospective-unvalidated", config: { ...config }, candidateCount: 5,
    coverageStart: history[0].date, coverageEnd: history[end].date, comparisonStart: history[COMMON_START].date, outerStart: history[OUTER_START].date,
    candidates, blocks, outer, latestSelection: { trainingThrough: history[selectionThrough].date, selected: latestChoice, scores: latestScores }, plan,
    notes: [
      "All supplied history was already exposed. This is retrospective development, not an untouched test, calibrated forecast or proof of profit. Exactly five momentum windows (14/30/60/90/180 days) were tried; no other family or parameters were searched. Risk allocation, cadence and costs are explicit scenario inputs.",
      "The adaptive policy, not its last winning window, is the adopted rule. Each 60-day outer block chooses the largest minimum after-cost advantage over HOLD and costed CAD on the common earlier inner prefix. Nonpositive scores choose HOLD; ties prefer the shorter window. The latest plan keeps its current block's choice; only a block boundary chooses again. Refresh must append data to the registered archive so calendar anchors stay fixed. The 365-day initial prefix precedes outer evaluation. Candidate leaderboards use common 181-day warm-up/start and must not be substituted for outer selector performance.",
      "All three paths start with identical already-owned units: entered scenario capital times target crypto allocation equally split among BTC/ETH/LINK, remaining CAD. No opening fee. HOLD keeps those units forever. Costed CAD sells the opening crypto at the next close and stays cash, without interest. Outer evaluation begins with a separate matched endowment and carries one continuous portfolio across all blocks; block changes do not reset wealth.",
      "Review signals use only prior-day closes. Trades execute at the following observed close, with adverse assumed slippage and fees on each leg; no historical orderbook or venue size/precision simulation. Weekly reviews are seven days apart; monthly reviews follow calendar months, after an initial review. A pending prior-block trade executes as previously reviewed; new block policy waits for the scheduled review. Same selected target means retain drifting weights; HOLD also retains units. Allocation is a target when shifting, not a hard exposure or loss cap. Legs under CAD 0.01 are skipped.",
      "Current recommendations also obey the outer review calendar: weekly anchored to the original outer start, monthly on day one. Between scheduled dates the instruction is HOLD; a refresh cannot create a daily shift. Existing approved/reviewed multi-step plans remain a separate server-bound execution workflow. Same-Eastern-day historical labels are excluded from current evidence and signals. Hypothetical paired estimates shown between reviews describe a rejected off-schedule candidate, not executable advice.",
      `Engineering evidence gates require ${MIN_BLOCKS} complete ${BLOCK_DAYS}-day outer blocks, ${MIN_HORIZONS} complete non-overlapping outer horizons, outer net advantage over both comparators, positive latest inner score and positive paired current historical mean advantage. These thresholds are not statistical significance, confidence or calibrated loss protection. An initial partial monthly interval does not count; the short archive can leave monthly evidence insufficient.`,
      "Paired scenarios apply each completed historical joint return path to the same current units and marks. The shift waits one observed day, then targets the candidate allocation; HOLD preserves units. Means and p10/p90 are empirical sample summaries, not dependable expected profit or loss bounds. Samples are not additive portfolio returns. A withheld shift's paired rows describe only that candidate, not the HOLD instruction. Fresh public books and explicit approval are required for every actual paper step.",
      dataset.note,
    ] };
}

export function strategyStudyFingerprintSource(): string {
  return JSON.stringify({ version: STRATEGY_STUDY_VERSION, WINDOWS, COMMON_START, OUTER_START, BLOCK_DAYS, MIN_BLOCKS, MIN_HORIZONS, assets: CRYPTO_ASSETS }) + evaluatorFingerprintSource() +
    [calendarDay, shiftDay, shiftMonth, finite, value, endowment, account, sell, shift, candidateId, windowFor, target, isReview, horizon, nextReview, completeReview, replay, scores, select, summarize, paired, runStrategyStudy].map((fn) => fn.toString()).join("\n");
}
