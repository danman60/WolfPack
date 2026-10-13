import { CRYPTO_ASSETS, type Asset, type CryptoAsset, type DailyPoint, type HistoryDataset, type ResearchConfig, type ResearchResult } from "./contract";

const DAY_MS = 86_400_000;
type Inventory = Record<Asset, number>;

function finite(value: number, label: string): number {
  if (!Number.isFinite(value)) throw new Error(`${label} must be finite.`);
  return value;
}

function validateConfig(config: ResearchConfig): void {
  if (finite(config.capitalCad, "Starting capital") <= 0) throw new Error("Starting capital must be positive.");
  if (config.cadence !== "weekly" && config.cadence !== "monthly") throw new Error("Choose weekly or monthly reviews.");
  if (!Number.isInteger(config.lookbackDays) || config.lookbackDays < 14 || config.lookbackDays > 180) {
    throw new Error("Lookback must be a whole number from 14 to 180 calendar days.");
  }
  for (const [label, value, maximum] of [
    ["Risk allocation", config.riskPercent, 100],
    ["Fee basis points", config.feeBps, 1_000],
    ["Slippage basis points", config.slippageBps, 1_000],
  ] as const) {
    if (finite(value, label) < 0 || value > maximum) throw new Error(`${label} must be between 0 and ${maximum}.`);
  }
}

function validateHistory(dataset: HistoryDataset, lookback: number): void {
  if (!Array.isArray(dataset.points) || dataset.points.length < lookback + 3) {
    throw new Error("History needs the lookback plus at least three daily observations.");
  }
  let previous: number | undefined;
  for (const point of dataset.points) {
    const timestamp = Date.parse(`${point.date}T00:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(point.date) || !Number.isFinite(timestamp) ||
        new Date(timestamp).toISOString().slice(0, 10) !== point.date) throw new Error("History contains an invalid calendar date.");
    if (previous !== undefined && timestamp - previous !== DAY_MS) {
      throw new Error("History must contain sorted, unique, consecutive observed daily dates; gaps cannot be treated as daily returns.");
    }
    for (const asset of CRYPTO_ASSETS) {
      const price = point.prices?.[asset];
      if (!Number.isFinite(price) || price < 1e-12 || price > 1e12) throw new Error(`History contains an invalid ${asset} price.`);
    }
    previous = timestamp;
  }
  if (dataset.coverageStart !== dataset.points[0].date || dataset.coverageEnd !== dataset.points.at(-1)!.date) {
    throw new Error("History coverage labels do not match its observations.");
  }
}

function equity(inventory: Inventory, day: DailyPoint): number {
  return finite(CRYPTO_ASSETS.reduce((sum, asset) => sum + inventory[asset] * day.prices[asset], inventory.CAD), "Portfolio value");
}

function ranking(points: DailyPoint[], through: number, lookback: number): ResearchResult["latestRanking"] {
  return CRYPTO_ASSETS.map((asset) => ({
    asset,
    trailingReturnPercent: finite((points[through].prices[asset] / points[through - lookback].prices[asset] - 1) * 100, "Trailing return"),
  })).sort((a, b) => b.trailingReturnPercent - a.trailingReturnPercent || CRYPTO_ASSETS.indexOf(a.asset) - CRYPTO_ASSETS.indexOf(b.asset));
}

/**
 * Frozen candidate v1: positive trailing-return winner, otherwise CAD.
 * Pure scenario comparison, not an optimizer, learned model or live signal.
 */
export function runResearch(dataset: HistoryDataset, config: ResearchConfig): ResearchResult {
  validateConfig(config);
  validateHistory(dataset, config.lookbackDays);
  const history = dataset.points;
  const startIndex = config.lookbackDays + 1;
  const first = history[startIndex];
  const risk = config.riskPercent / 100;
  const fee = config.feeBps / 10_000;
  const slip = config.slippageBps / 10_000;
  const holdings: Inventory = { CAD: config.capitalCad * (1 - risk), BTC: 0, ETH: 0, LINK: 0 };
  for (const asset of CRYPTO_ASSETS) holdings[asset] = finite(config.capitalCad * risk / 3 / first.prices[asset], "Opening units");
  const baseline = { ...holdings };
  let feesCad = 0;
  let trades = 0;
  let turnoverCad = 0;
  let reviews = 0;
  let pending: { target: Asset; executeIndex: number } | undefined;
  let lastTarget: Asset | "initial mix" = risk === 0 ? "CAD" : "initial mix";
  let peak = config.capitalCad;
  let maxDrawdownPercent = 0;
  const points: ResearchResult["points"] = [];

  function sell(asset: CryptoAsset, midNotional: number, day: DailyPoint) {
    if (midNotional < 0.01) return;
    const quantity = Math.min(holdings[asset], midNotional / day.prices[asset]);
    const gross = quantity * day.prices[asset] * (1 - slip);
    const charge = gross * fee;
    holdings[asset] = Math.max(0, holdings[asset] - quantity);
    holdings.CAD += gross - charge;
    feesCad += charge;
    turnoverCad += gross;
    trades += 1;
  }

  function rebalance(target: Asset, day: DailyPoint) {
    if (target === lastTarget) return; // Deliberately allow weight drift while the winner stays unchanged.
    for (const asset of CRYPTO_ASSETS) {
      if (asset !== target) sell(asset, holdings[asset] * day.prices[asset], day);
    }
    if (target !== "CAD") {
      const value = equity(holdings, day);
      const heldValue = holdings[target] * day.prices[target];
      const buyCost = (1 + slip) * (1 + fee);
      // Solve for the risk share of POST-COST equity, rather than spend the
      // target notional and then discover that fees made cash negative.
      const desiredBuy = (risk * value - heldValue) / (1 + risk * (buyCost - 1));
      if (desiredBuy >= 0.01) {
        const midNotional = Math.min(desiredBuy, holdings.CAD / buyCost);
        if (midNotional >= 0.01) {
          const gross = midNotional * (1 + slip);
          const charge = gross * fee;
          holdings[target] += midNotional / day.prices[target];
          holdings.CAD = Math.max(0, holdings.CAD - gross - charge);
          feesCad += charge;
          turnoverCad += gross;
          trades += 1;
        }
      } else if (desiredBuy < 0) {
        const sellProceeds = (1 - slip) * (1 - fee);
        sell(target, (heldValue - risk * value) / (1 - risk * (1 - sellProceeds)), day);
      }
    }
    lastTarget = target;
  }

  for (let index = startIndex; index < history.length; index += 1) {
    const day = history[index];
    if (pending?.executeIndex === index) {
      rebalance(pending.target, day);
      pending = undefined;
    }
    const strategyCad = equity(holdings, day);
    const holdCad = equity(baseline, day);
    if (strategyCad < 0 || CRYPTO_ASSETS.some((asset) => holdings[asset] < 0) || holdings.CAD < 0) {
      throw new Error("Research accounting produced negative holdings.");
    }
    peak = Math.max(peak, strategyCad);
    maxDrawdownPercent = Math.max(maxDrawdownPercent, (peak - strategyCad) / peak * 100);
    points.push({ date: day.date, strategyCad, holdCad });

    const review = index === startIndex || (config.cadence === "weekly"
      ? (index - startIndex) % 7 === 0
      : day.date.slice(0, 7) !== history[index - 1].date.slice(0, 7));
    if (review) {
      reviews += 1;
      const ranked = ranking(history, index - 1, config.lookbackDays);
      const target: Asset = risk > 0 && ranked[0].trailingReturnPercent > 0 ? ranked[0].asset : "CAD";
      if (index + 1 < history.length) pending = { target, executeIndex: index + 1 };
    }
  }

  const final = points.at(-1)!;
  const latestRanking = ranking(history, history.length - 2, config.lookbackDays);
  const suggestedAsset: Asset = risk > 0 && latestRanking[0].trailingReturnPercent > 0 ? latestRanking[0].asset : "CAD";
  finite(feesCad, "Total fees");
  finite(turnoverCad, "Turnover");
  finite(maxDrawdownPercent, "Maximum drawdown");
  return {
    points,
    finalCad: final.strategyCad,
    holdCad: final.holdCad,
    incrementalCad: finite(final.strategyCad - final.holdCad, "Incremental value"),
    feesCad,
    trades,
    maxDrawdownPercent,
    start: first.date,
    end: final.date,
    latestRanking,
    suggestedAsset,
    note: `Experimental fixed momentum candidate v1. User inputs are scenario parameters, never optimized; this retrospective comparison is not an untouched test or validated forecast. Both paths start with identical already-owned units: ${config.riskPercent}% divided equally among BTC/ETH/LINK and the rest CAD, marked on ${first.date}; no artificial opening fees. HOLD never rebalances. ${config.cadence === "weekly" ? "Reviews every seven calendar days from the start" : "Review at the start, then on the first observed day of each calendar month"}; ${reviews} reviews. Rank ${config.lookbackDays}-calendar-day close returns using only data through the prior day. Positive winner receives the risk allocation and the rest stays CAD; otherwise CAD. Ties use BTC, ETH, LINK order. Execute at the NEXT observed daily close after review (delayed close proxy), with ${config.slippageBps} bps adverse slippage and ${config.feeBps} bps fee on each sell/buy leg. Trade only on a change of selected target; same target means HOLD with drifting weights, and legs below CAD 0.01 are skipped. Changed targets use post-cost equity for sizing. ${trades} executed legs; CAD ${turnoverCad.toFixed(2)} gross turnover. All curve points use identical reference marks after any execution costs, charged once. Drawdown uses those observed daily equity points, not intraday prices. Warm-up dates are excluded from both curves. Latest ranking uses history through ${history[history.length - 2].date}; it is an experimental historical ranking, not a live recommendation. Missing dates fail validation. No historical order books or size-dependent fill model: slippage is an assumption, minimum orders and venue precision are not simulated. Limited observations, especially monthly decisions; no calibrated confidence, expected profit, training or advanced-ML claim. ${dataset.note}`,
  };
}

/** A saved protocol must not silently execute changed arithmetic. Include every
 * module-level implementation helper here when extending this evaluator. */
export function replayFingerprintSource(): string {
  return JSON.stringify({ dayMs: DAY_MS, assets: CRYPTO_ASSETS }) +
    [finite, validateConfig, validateHistory, equity, ranking, runResearch].map((fn) => fn.toString()).join("\n");
}
