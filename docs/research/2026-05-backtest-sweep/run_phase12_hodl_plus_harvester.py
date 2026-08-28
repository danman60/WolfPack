"""Phase 12: HODL + Drawdown Harvester portfolio.

Stop fighting HODL. Pair HODL with a small sleeve running ONLY Leg 1
(funding-z low → long), which Phase 6 + Phase 8 validated as positive in
SIDEWAYS and BEAR regimes (the periods when HODL is flat or losing).

Test:
  - 100% HODL baseline
  - 100% Leg 1 standalone
  - 80/20 split: 80% HODL + 20% Leg 1
  - 90/10 split: 90% HODL + 10% Leg 1
  - 70/30 split: 70% HODL + 30% Leg 1

Last 90 days, 7 symbols. Report per-symbol total return AND realized max
drawdown for each portfolio variant.
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
TEST_BARS = 540

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase12_hodl_plus.json"
OUT_SUMMARY = OUT_DIR / "phase12_hodl_plus.md"


async def fetch_funding(client, coin, start_ms):
    all_records = []
    cursor = start_ms; backoff = 0.5
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
    aligned = np.full(len(candles), np.nan)
    times = np.array([c.timestamp for c in candles])
    for i, t in enumerate(times):
        idx = np.searchsorted(f_t, t, side="right") - 1
        if idx >= 0: aligned[i] = f_v[idx]
    return closes, highs, lows, aligned


def rolling_zscore(arr, window):
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        w = arr[i - window : i]
        w = w[~np.isnan(w)]
        if len(w) < window // 2: continue
        mu, sigma = np.mean(w), np.std(w, ddof=1)
        if sigma > 0: out[i] = (arr[i] - mu) / sigma
    return out


def hodl_equity_curve(closes, test_start, test_end):
    """Equity curve for $1 invested at test_start. Returns array of equity values."""
    n = test_end - test_start
    eq = np.zeros(n)
    base = closes[test_start]
    for i in range(n):
        eq[i] = closes[test_start + i] / base
    return eq


def leg1_equity_curve(closes, highs, lows, funding_z, test_start, test_end,
                      sl_pct=3.0, tp_pct=2.0, max_hold=12, threshold=-2.0, trade_pct=0.10):
    """Equity curve of pure Leg 1 strategy starting at $1.
       Position size = trade_pct of CURRENT equity per trade (compounding)."""
    n_total = len(closes)
    eq = np.full(n_total, 1.0)
    in_pos_until = -1
    entry_price = None; entry_idx = None; size_used = 0
    for i in range(test_start, test_end):
        if i > test_start:
            eq[i] = eq[i - 1]
        # Check exit if in position
        if in_pos_until > i:
            if entry_price is not None:
                # Mark to market for visualization (but realized P&L applied at exit)
                pass
            continue
        # Apply realized P&L if just exited
        if i == in_pos_until and entry_price is not None:
            # exit already applied below; reset
            entry_price = None; entry_idx = None; size_used = 0
        # New entry
        if i + max_hold >= n_total: continue
        if np.isnan(funding_z[i]) or funding_z[i] >= threshold: continue
        entry = closes[i]
        sl = entry * (1 - sl_pct/100); tp = entry * (1 + tp_pct/100)
        ex_idx, ex_p = None, None
        for j in range(1, max_hold + 1):
            b = i + j
            if b >= n_total: break
            if lows[b] <= sl: ex_idx, ex_p = b, sl; break
            if highs[b] >= tp: ex_idx, ex_p = b, tp; break
        if ex_idx is None:
            ex_idx = min(i + max_hold, n_total - 1); ex_p = closes[ex_idx]
        net = ((ex_p - entry) / entry) - COST_PCT
        # Apply to equity at exit bar
        eq_at_entry = eq[i]
        new_eq = eq_at_entry * (1 + trade_pct * net)
        # Forward-fill from entry to exit with mark-to-market unrealized pnl
        for k in range(i, min(ex_idx + 1, test_end)):
            bar_close = closes[k]
            if k == ex_idx:
                eq[k] = new_eq
            else:
                # mark-to-market unrealized
                unrealized = (bar_close - entry) / entry
                eq[k] = eq_at_entry * (1 + trade_pct * unrealized)
        in_pos_until = ex_idx
        entry_price = entry; entry_idx = i; size_used = trade_pct
    return eq[test_start:test_end]


def blended_curve(hodl_eq, leg_eq, hodl_weight):
    """Blend two equity curves with constant weights (no rebalancing)."""
    return hodl_weight * hodl_eq + (1 - hodl_weight) * leg_eq


def metrics(eq):
    """Total return, max drawdown, simple Sharpe (4h-bar log returns annualized)."""
    if len(eq) < 2:
        return {"total_ret_pct": 0, "max_dd_pct": 0, "sharpe": 0}
    total_ret = (eq[-1] - eq[0]) / eq[0]
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    max_dd = float(np.max(dd))
    log_rets = np.diff(np.log(np.maximum(eq, 1e-9)))
    if len(log_rets) > 1 and np.std(log_rets) > 0:
        sharpe = (np.mean(log_rets) / np.std(log_rets, ddof=1)) * math.sqrt(2190)  # 6 4h-bars × 365
    else:
        sharpe = 0.0
    return {"total_ret_pct": float(total_ret * 100), "max_dd_pct": float(max_dd * 100), "sharpe": float(sharpe)}


async def main():
    t0 = time.time()
    print("Phase 12 — HODL + Drawdown Harvester, last 90 days\n")

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
        if not funding_cache.get(sym) or not candles_cache.get(sym): continue
        closes, highs, lows, funding = align(funding_cache[sym], candles_cache[sym])
        n = len(closes)
        if n < 250: continue
        funding_z = rolling_zscore(funding, 180)
        test_start = max(0, n - TEST_BARS); test_end = n

        hodl_eq = hodl_equity_curve(closes, test_start, test_end)
        leg1_eq = leg1_equity_curve(closes, highs, lows, funding_z, test_start, test_end)

        portfolios = {
            "100% HODL": hodl_eq,
            "100% Leg1": leg1_eq,
            "90/10": blended_curve(hodl_eq, leg1_eq, 0.9),
            "80/20": blended_curve(hodl_eq, leg1_eq, 0.8),
            "70/30": blended_curve(hodl_eq, leg1_eq, 0.7),
        }

        print(f"\n=== {sym} ===")
        results[sym] = {}
        for name, eq in portfolios.items():
            m = metrics(eq)
            results[sym][name] = m
            print(f"  {name:12} ret={m['total_ret_pct']:+7.2f}%  maxDD={m['max_dd_pct']:5.2f}%  Sharpe={m['sharpe']:+.2f}")

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))

    lines = ["# Phase 12: HODL + Drawdown Harvester — last 90 days"]
    lines.append(f"\n**Window**: last 540 4h-bars (90 days). **Cost**: {ROUND_TRIP_BPS} bps round-trip.\n")
    lines.append("**Architecture**: HODL captures bull moves; Leg 1 (funding-z<-2 → long, 3% SL / 2% TP / 48h) harvests during sideways/drawdowns.\n")
    lines.append("**Hypothesis**: 80/20 (or 90/10) blend matches HODL return with lower drawdown.\n")

    lines.append("## Per-symbol total return")
    lines.append("| sym | 100% HODL | 100% Leg1 | 90/10 | 80/20 | 70/30 |")
    lines.append("|---|---|---|---|---|---|")
    for sym, r in results.items():
        lines.append(f"| {sym} | {r['100% HODL']['total_ret_pct']:+.2f}% | {r['100% Leg1']['total_ret_pct']:+.2f}% | {r['90/10']['total_ret_pct']:+.2f}% | {r['80/20']['total_ret_pct']:+.2f}% | {r['70/30']['total_ret_pct']:+.2f}% |")

    lines.append("\n## Per-symbol max drawdown")
    lines.append("| sym | 100% HODL | 100% Leg1 | 90/10 | 80/20 | 70/30 |")
    lines.append("|---|---|---|---|---|---|")
    for sym, r in results.items():
        lines.append(f"| {sym} | {r['100% HODL']['max_dd_pct']:.2f}% | {r['100% Leg1']['max_dd_pct']:.2f}% | {r['90/10']['max_dd_pct']:.2f}% | {r['80/20']['max_dd_pct']:.2f}% | {r['70/30']['max_dd_pct']:.2f}% |")

    lines.append("\n## Per-symbol Sharpe (annualized)")
    lines.append("| sym | 100% HODL | 100% Leg1 | 90/10 | 80/20 | 70/30 |")
    lines.append("|---|---|---|---|---|---|")
    for sym, r in results.items():
        lines.append(f"| {sym} | {r['100% HODL']['sharpe']:+.2f} | {r['100% Leg1']['sharpe']:+.2f} | {r['90/10']['sharpe']:+.2f} | {r['80/20']['sharpe']:+.2f} | {r['70/30']['sharpe']:+.2f} |")

    # Aggregate
    n = len(results)
    for portfolio in ["100% HODL", "100% Leg1", "90/10", "80/20", "70/30"]:
        avg_ret = sum(r[portfolio]["total_ret_pct"] for r in results.values()) / n
        avg_dd = sum(r[portfolio]["max_dd_pct"] for r in results.values()) / n
        avg_sharpe = sum(r[portfolio]["sharpe"] for r in results.values()) / n
        lines.append(f"- {portfolio}: avg ret={avg_ret:+.2f}%, avg maxDD={avg_dd:.2f}%, avg Sharpe={avg_sharpe:+.2f}")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"\nwrote {OUT_RESULTS}")
    print(f"wrote {OUT_SUMMARY}")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
