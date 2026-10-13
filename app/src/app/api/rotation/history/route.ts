import { NextResponse } from "next/server";
import type { HistoryDataset } from "@/lib/rotation/contract";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DAY_SECONDS = 86_400;
const CACHE_MS = 15 * 60 * 1_000;
const COMPLETED_LIMIT = 719;
// Verified through Kraken AssetPairs. XBT is native BTC, not wrapped BTC.
const PAIRS = [
  { request: "XBTCAD", response: "XXBTZCAD" },
  { request: "ETHCAD", response: "XETHZCAD" },
  { request: "LINKETH", response: "LINKETH" },
] as const;

let cached: { until: number; dataset: HistoryDataset } | undefined;
let pending: Promise<HistoryDataset> | undefined;

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function positivePrice(value: unknown): number {
  if (typeof value !== "string" && typeof value !== "number") {
    throw new Error("Kraken returned a malformed close price.");
  }
  const number = Number(value);
  if (!Number.isFinite(number) || number < 1e-12 || number > 1e12) {
    throw new Error("Kraken returned an invalid close price.");
  }
  return number;
}

async function loadPair(pair: (typeof PAIRS)[number], now: number): Promise<Map<number, number>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(
      `https://api.kraken.com/0/public/OHLC?pair=${pair.request}&interval=1440`,
      { signal: controller.signal, cache: "no-store" },
    );
    if (!response.ok) throw new Error(`Kraken ${pair.request} returned HTTP ${response.status}.`);
    const payload: unknown = await response.json();
    if (!object(payload) || !Array.isArray(payload.error) || payload.error.length !== 0 || !object(payload.result)) {
      throw new Error(`Kraken ${pair.request} returned an API error or incomplete response.`);
    }
    const rows = payload.result[pair.response];
    if (!Array.isArray(rows) || rows.length < 2 || rows.length > 1_000) {
      throw new Error(`Kraken ${pair.request} returned insufficient or unexpected history.`);
    }
    const today = Math.floor(now / 1_000 / DAY_SECONDS) * DAY_SECONDS;
    const firstPlausibleDay = Date.UTC(2009, 0, 1) / 1_000;
    let previous = 0;
    const completed: [number, number][] = [];
    for (let i = 0; i < rows.length; i += 1) {
      const row: unknown = rows[i];
      if (!Array.isArray(row) || row.length !== 8) throw new Error(`Kraken ${pair.request} returned a malformed candle.`);
      const timestamp: unknown = row[0];
      if (typeof timestamp !== "number" || !Number.isSafeInteger(timestamp) || timestamp % DAY_SECONDS !== 0 ||
          timestamp < firstPlausibleDay || timestamp > today || timestamp <= previous) {
        throw new Error(`Kraken ${pair.request} returned invalid or unordered daily timestamps.`);
      }
      const close = positivePrice(row[4]);
      // Kraken always includes the unfinished final candle. Never use it, even
      // if a stale upstream response makes its timestamp look completed.
      if (i < rows.length - 1 && timestamp < today) completed.push([timestamp, close]);
      previous = timestamp;
    }
    if (previous !== today || completed.at(-1)?.[0] !== today - DAY_SECONDS) {
      throw new Error(`Kraken ${pair.request} history is stale or incomplete.`);
    }
    return new Map(completed.slice(-COMPLETED_LIMIT));
  } catch (error) {
    if (controller.signal.aborted) throw new Error(`Kraken ${pair.request} timed out after 10 seconds.`);
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function loadDataset(): Promise<HistoryDataset> {
  const now = Date.now();
  const [btc, eth, linkEth] = await Promise.all(PAIRS.map((pair) => loadPair(pair, now)));
  const timestamps = [...btc.keys()].filter((timestamp) => eth.has(timestamp) && linkEth.has(timestamp));
  if (timestamps.length < 183) throw new Error("Kraken has fewer than 183 matching completed daily observations.");
  for (let i = 1; i < timestamps.length; i += 1) {
    if (timestamps[i] - timestamps[i - 1] !== DAY_SECONDS) {
      throw new Error("Kraken's matching daily history has a gap; research requires continuous observed dates.");
    }
  }
  const points = timestamps.map((timestamp) => ({
    // Calendar candle labels stay strings. They must not be rendered as local
    // midnight timestamps, which would move the displayed date backward.
    date: new Date(timestamp * 1_000).toISOString().slice(0, 10),
    prices: {
      BTC: btc.get(timestamp)!,
      ETH: eth.get(timestamp)!,
      LINK: positivePrice(linkEth.get(timestamp)! * eth.get(timestamp)!),
    },
  }));
  return {
    source: "Kraken public spot daily OHLC: XBT/CAD, ETH/CAD and LINK/ETH",
    fetchedAt: new Date(now).toISOString(),
    coverageStart: points[0].date,
    coverageEnd: points[points.length - 1].date,
    points,
    note: "Native BTC is Kraken XBT. LINK/CAD is derived as LINK/ETH close × ETH/CAD close on the exact same daily candle timestamp; those separate markets' last trades need not be simultaneous. These are spot reference closes, not Ndax fills or historical order books. Kraken documents a 720-entry recent-history limit including an unfinished bar; this loader conservatively retains at most 719 completed matching dates. No backward pagination, filled gaps, synthetic prices or invented high/low prices. Dates label the exchange's daily candles; they are calendar labels, not Eastern midnight timestamps. Coverage is too short for the proposed multi-year untouched walk-forward study.",
  };
}

export async function GET() {
  try {
    if (!cached || cached.until <= Date.now()) {
      if (!pending) {
        pending = loadDataset().then((dataset) => {
          cached = { until: Date.now() + CACHE_MS, dataset };
          return dataset;
        }).finally(() => { pending = undefined; });
      }
      await pending;
    }
    if (!cached) throw new Error("Historical data was not loaded.");
    const remainingSeconds = Math.max(0, Math.floor((cached.until - Date.now()) / 1_000));
    return NextResponse.json(cached.dataset, {
      headers: { "Cache-Control": `public, max-age=0, s-maxage=${remainingSeconds}, must-revalidate` },
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Kraken history is unavailable." },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
