"""Phase 8: Segment the funding-squeeze-long strategy by market regime.

The 28-month window included a massive bull run. Long-only strategies are
structurally disadvantaged vs HODL in that case. Real test: how does the
strategy perform during BULL / SIDEWAYS / BEAR sub-periods?

Method:
  1. Compute rolling 30-day BTC return on every bar
  2. Classify each bar's regime: BULL (>+10%/30d), BEAR (<-10%/30d), SIDEWAYS (else)
  3. For each strategy trade, tag with the regime that prevailed at entry
  4. Aggregate strategy returns vs HODL returns within each regime
  5. Report: does the strategy beat HODL in SIDEWAYS / BEAR specifically?
"""

import asyncio
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

INTEL_PATH = Path(__file__).resolve().parents[3] / "intel"
sys.path.insert(0, str(INTEL_PATH))

import httpx
import numpy as np
from wolfpack.exchanges.base import Candle

INTEL_API = "http://159.89.115.95:8000"
HL_API = "https://api.hyperliquid.xyz/info"
SYMBOLS = ["BTC", "ETH", "SOL", "LINK", "AVAX", "ARB", "DOGE"]
ROUND_TRIP_BPS = 10.0
COST_PCT = ROUND_TRIP_BPS / 10000.0

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase8_regime_segmented.json"
OUT_SUMMARY = OUT_DIR / "phase8_regime_segmented.md"


async def fetch_funding(client, coin, start_ms):
    all_records = []
    cursor = start_ms
    backoff = 0.5
    while True:
        try:
            r = await client.post(HL_API, json={"type": "fundingHistory", "coin": coin, "startTime": cursor}, timeout=60)
            if r.status_code == 429:
                await asyncio.sleep(backoff); backoff = min(backoff * 2, 30); continue
            r.raise_for_status(); backoff = 0.5
        except Exception:
            await asyncio.sleep(backoff); backoff = min(backoff * 2, 30)
            if backoff >= 30: raise
            continue
        batch = r.json()
        if not batch: break
        all_records.extend(batch)
        last = batch[-1]["time"]
        if last <= cursor: break
        cursor = last + 1
        if len(batch) < 100: break
        if len(all_records) > 50000: break
        await asyncio.sleep(0.3)
    seen = set(); out = []
    for r in all_records:
        if r["time"] in seen: continue
        seen.add(r["time"]); out.append(r)
    out.sort(key=lambda x: x["time"])
    return out


async def fetch_candles(client, symbol):
    r = await client.get(f"{INTEL_API}/market/candles",
                         params={"symbol": symbol, "interval": "4h", "limit": 5000}, timeout=120)
    r.raise_for_status()
    return [Candle(**c) for c in r.json()["candles"]]


def align(funding_records, candles):
    funding_records.sort(key=lambda x: x["time"])
    f_t = np.array([r["time"] for r in funding_records])
    f_v = np.array([float(r["fundingRate"]) for r in funding_records])
    closes = np.array([c.close for c in candles], dtype=np.float64)
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows = np.array([c.low for c in candles], dtype=np.float64)
    times = np.array([c.timestamp for c in candles])
    aligned = np.full(len(candles), np.nan)
    for i, t in enumerate(times):
        idx = np.searchsorted(f_t, t, side="right") - 1
        if idx >= 0: aligned[i] = f_v[idx]
    return closes, highs, lows, aligned, times


def rolling_zscore(arr, window=180):
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        w = arr[i - window : i]
        w = w[~np.isnan(w)]
        if len(w) < window // 2: continue
        mu, sigma = np.mean(w), np.std(w, ddof=1)
        if sigma > 0: out[i] = (arr[i] - mu) / sigma
    return out


def classify_regime(closes, lookback_bars=180):
    """Classify each bar into BULL/SIDEWAYS/BEAR based on 30-day forward-looking-back return.
    180 4h-bars = 30 days. >+10% over 30d = BULL, <-10% = BEAR, else SIDEWAYS."""
    n = len(closes)
    regimes = ["UNKNOWN"] * n
    for i in range(lookback_bars, n):
        ret = (closes[i] - closes[i - lookback_bars]) / closes[i - lookback_bars]
        if ret > 0.10: regimes[i] = "BULL"
        elif ret < -0.10: regimes[i] = "BEAR"
        else: regimes[i] = "SIDEWAYS"
    return regimes


def simulate(closes, highs, lows, fired, sl_pct, tp_pct, max_hold):
    n = len(closes)
    trades = []
    in_position_until = -1

    for i in range(n):
        if in_position_until > i: continue
        if not fired[i] or i + max_hold >= n: continue
        entry = closes[i]
        sl_price = entry * (1 - sl_pct / 100.0)
        tp_price = entry * (1 + tp_pct / 100.0)
        exit_idx, exit_price, exit_reason = None, None, None
        for j in range(1, max_hold + 1):
            bar = i + j
            if lows[bar] <= sl_price:
                exit_idx, exit_price, exit_reason = bar, sl_price, "stop"; break
            if highs[bar] >= tp_price:
                exit_idx, exit_price, exit_reason = bar, tp_price, "tp"; break
        if exit_idx is None:
            exit_idx = i + max_hold
            exit_price = closes[exit_idx]
            exit_reason = "time"
        gross = (exit_price - entry) / entry
        net = gross - COST_PCT
        trades.append({
            "entry_idx": i, "exit_idx": exit_idx,
            "gross_ret_pct": gross * 100, "net_ret_pct": net * 100,
            "exit_reason": exit_reason, "hold_bars": exit_idx - i,
        })
        in_position_until = exit_idx
    return trades


def aggregate_by_regime(trades, regimes, closes, max_hold):
    """Group trades by regime at entry. Compare strategy mean return vs HODL mean return
    over an equivalent random window in the same regime."""
    by_regime = defaultdict(lambda: {"trades": [], "hodl_returns": []})
    n = len(closes)
    for t in trades:
        reg = regimes[t["entry_idx"]]
        by_regime[reg]["trades"].append(t)

    # Compute baseline HODL return: for each regime bar, the forward `max_hold` bar return
    # if you were holding from that bar. Compare to strategy mean.
    for i in range(n - max_hold):
        reg = regimes[i]
        if reg == "UNKNOWN": continue
        hodl_ret = (closes[i + max_hold] - closes[i]) / closes[i]
        by_regime[reg]["hodl_returns"].append(hodl_ret * 100)

    summary = {}
    for reg, data in by_regime.items():
        ts = data["trades"]
        if len(ts) < 5:
            continue
        net_rets = [t["net_ret_pct"] for t in ts]
        wins = sum(1 for r in net_rets if r > 0)
        strat_mean = float(np.mean(net_rets))
        strat_total = float(np.sum(net_rets))
        hodl_arr = np.array(data["hodl_returns"])
        hodl_mean = float(np.mean(hodl_arr)) if len(hodl_arr) else 0.0
        # If we'd held for the same duration as the strategy across regime bars
        # this approximates "HODL during this regime".
        summary[reg] = {
            "n_trades": len(ts),
            "wins": wins,
            "wr": wins / len(ts),
            "strat_mean_pct": strat_mean,
            "strat_total_pct": strat_total,
            "hodl_mean_pct_per_window": hodl_mean,
            "edge_vs_hodl_per_trade": strat_mean - hodl_mean,
            "regime_bars": int(np.sum(np.array(regimes) == reg)),
        }
    return summary


async def main():
    t0 = time.time()
    print("Phase 8 — regime-segmented funding-squeeze-long\n")

    funding_cache, candles_cache = {}, {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            print(f"fetching {sym}...")
            funding_cache[sym] = await fetch_funding(client, sym, 1704067200000)
            await asyncio.sleep(2)
            candles_cache[sym] = await fetch_candles(client, sym)
            print(f"  funding={len(funding_cache[sym])} candles={len(candles_cache[sym])}")
    print(f"fetch took {time.time()-t0:.0f}s\n")

    results = {}
    for sym in SYMBOLS:
        if not funding_cache.get(sym) or not candles_cache.get(sym):
            continue
        closes, highs, lows, funding, times = align(funding_cache[sym], candles_cache[sym])
        if np.sum(~np.isnan(funding)) < 200: continue
        z = rolling_zscore(funding, window=180)
        # Use BTC close to classify regime — symbol-correlation test (alts move with BTC)
        # For per-symbol fairness, use each symbol's own price for classification too
        regimes = classify_regime(closes, lookback_bars=180)
        regime_counts = {r: regimes.count(r) for r in set(regimes)}

        # Default params from Phase 7 best
        params = {"sl_pct": 3.0, "tp_pct": 2.0, "max_hold": 12}
        fired = z < -2.0
        trades = simulate(closes, highs, lows, fired, params["sl_pct"], params["tp_pct"], params["max_hold"])
        if not trades:
            continue

        regime_summary = aggregate_by_regime(trades, regimes, closes, params["max_hold"])
        results[sym] = {
            "regime_counts": regime_counts,
            "total_trades": len(trades),
            "params": params,
            "by_regime": regime_summary,
        }

        print(f"\n=== {sym} ===")
        print(f"  regime distribution: {regime_counts}")
        print(f"  total trades: {len(trades)}")
        for reg in ["BULL", "SIDEWAYS", "BEAR"]:
            if reg not in regime_summary: continue
            r = regime_summary[reg]
            print(f"  {reg:9} n={r['n_trades']:3} WR={r['wr']*100:.1f}% strat_avg={r['strat_mean_pct']:+.2f}% per trade  HODL_avg(48h)={r['hodl_mean_pct_per_window']:+.2f}%  edge={r['edge_vs_hodl_per_trade']:+.2f}%")

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))

    # Markdown summary
    lines = ["# Phase 8: regime-segmented funding-squeeze-long"]
    lines.append("\nDoes funding-z-low-long beat HODL in SIDEWAYS / BEAR markets, even though it loses to BULL HODL?\n")
    lines.append("**Regime classification:** rolling 30d return on the symbol itself. BULL > +10%, BEAR < -10%, else SIDEWAYS.\n")
    lines.append("**Strategy:** enter when 30d funding z < -2.0; exit at first of {3% SL, 2% TP, 48h time-stop}.\n")
    lines.append("**HODL_avg_48h:** mean 48h forward return on bars within the same regime — the proper apples-to-apples HODL baseline.\n")

    for sym, data in results.items():
        lines.append(f"\n## {sym}")
        lines.append(f"\nRegime distribution across 28 months: {data['regime_counts']}\n")
        lines.append(f"Total strategy trades: {data['total_trades']}\n")
        lines.append("| regime | trades | WR% | strat avg/trade | HODL avg 48h | edge vs HODL |")
        lines.append("|---|---|---|---|---|---|")
        for reg in ["BULL", "SIDEWAYS", "BEAR"]:
            if reg not in data["by_regime"]: continue
            r = data["by_regime"][reg]
            lines.append(f"| {reg} | {r['n_trades']} | {r['wr']*100:.1f} | {r['strat_mean_pct']:+.2f}% | {r['hodl_mean_pct_per_window']:+.2f}% | **{r['edge_vs_hodl_per_trade']:+.2f}%** |")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"\nwrote {OUT_RESULTS}")
    print(f"wrote {OUT_SUMMARY}")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
