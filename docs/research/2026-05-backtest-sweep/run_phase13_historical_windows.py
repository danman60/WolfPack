"""Phase 13: re-test HODL+Harvester on historical bear/sideways windows.

Phase 12 ran on the most recent 90 days, which was a bull window — Leg 1 didn't
fire. To test the architecture properly, identify historical 90-day windows
where the underlying was bear or sideways and re-run Phase 12 there.

Method:
  1. For each symbol, scan all 90-day windows in the 28-month data
  2. Identify "worst-drawdown" window (HODL most negative)
  3. Identify "most-sideways" window (HODL closest to zero)
  4. Run HODL / 100% Leg 1 / 90/10 / 80/20 / 70/30 portfolios on each
  5. Report whether Leg 1 actually fired AND whether blends beat HODL
"""

import asyncio
import json
import math
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
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
WINDOW_BARS = 540  # 90 days
WARMUP_BARS = 200  # need this much history before window for indicators

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase13_historical.json"
OUT_SUMMARY = OUT_DIR / "phase13_historical.md"


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
    times = np.array([c.timestamp for c in candles])
    aligned = np.full(len(candles), np.nan)
    for i, t in enumerate(times):
        idx = np.searchsorted(f_t, t, side="right") - 1
        if idx >= 0: aligned[i] = f_v[idx]
    return closes, highs, lows, aligned, times


def rolling_zscore(arr, window):
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        w = arr[i - window : i]
        w = w[~np.isnan(w)]
        if len(w) < window // 2: continue
        mu, sigma = np.mean(w), np.std(w, ddof=1)
        if sigma > 0: out[i] = (arr[i] - mu) / sigma
    return out


def find_worst_window(closes, window_bars=WINDOW_BARS, warmup=WARMUP_BARS):
    """Return start index of the 90-day window with the most negative HODL return."""
    n = len(closes)
    best_idx = -1
    best_ret = float("inf")
    for i in range(warmup, n - window_bars):
        ret = (closes[i + window_bars - 1] - closes[i]) / closes[i]
        if ret < best_ret:
            best_ret = ret; best_idx = i
    return best_idx, best_ret


def find_most_sideways_window(closes, window_bars=WINDOW_BARS, warmup=WARMUP_BARS):
    """Window with smallest |HODL return|, but require some intra-window volatility."""
    n = len(closes)
    best_idx = -1
    best_score = float("inf")
    for i in range(warmup, n - window_bars):
        ret = abs((closes[i + window_bars - 1] - closes[i]) / closes[i])
        # Prefer windows with low net return AND non-trivial intra-window range
        window = closes[i : i + window_bars]
        peak_to_trough = (np.max(window) - np.min(window)) / np.min(window)
        if peak_to_trough < 0.05: continue  # skip windows that are too flat (no opportunity)
        if ret < best_score:
            best_score = ret; best_idx = i
    return best_idx, best_score


def hodl_equity_curve(closes, test_start, test_end):
    n = test_end - test_start
    eq = np.zeros(n)
    base = closes[test_start]
    for i in range(n):
        eq[i] = closes[test_start + i] / base
    return eq


def leg1_equity_curve(closes, highs, lows, funding_z, test_start, test_end,
                      sl_pct=3.0, tp_pct=2.0, max_hold=12, threshold=-2.0, trade_pct=0.10):
    n_total = len(closes)
    eq = np.full(n_total, 1.0)
    in_pos_until = -1
    n_trades = 0
    for i in range(test_start, test_end):
        if i > test_start:
            eq[i] = eq[i - 1]
        if in_pos_until > i:
            continue
        if i + max_hold >= n_total: continue
        if np.isnan(funding_z[i]) or funding_z[i] >= threshold: continue
        entry = closes[i]; sl = entry*(1-sl_pct/100); tp = entry*(1+tp_pct/100)
        ex_idx, ex_p = None, None
        for j in range(1, max_hold + 1):
            b = i + j
            if b >= n_total: break
            if lows[b] <= sl: ex_idx, ex_p = b, sl; break
            if highs[b] >= tp: ex_idx, ex_p = b, tp; break
        if ex_idx is None:
            ex_idx = min(i + max_hold, n_total - 1); ex_p = closes[ex_idx]
        net = ((ex_p - entry)/entry) - COST_PCT
        eq_at_entry = eq[i]
        new_eq = eq_at_entry * (1 + trade_pct * net)
        for k in range(i, min(ex_idx + 1, test_end)):
            bar_close = closes[k]
            if k == ex_idx:
                eq[k] = new_eq
            else:
                unrealized = (bar_close - entry) / entry
                eq[k] = eq_at_entry * (1 + trade_pct * unrealized)
        in_pos_until = ex_idx
        n_trades += 1
    return eq[test_start:test_end], n_trades


def blended(hodl_eq, leg_eq, w_hodl):
    return w_hodl * hodl_eq + (1 - w_hodl) * leg_eq


def metrics(eq):
    if len(eq) < 2:
        return {"total_ret_pct": 0, "max_dd_pct": 0, "sharpe": 0}
    total_ret = (eq[-1] - eq[0]) / eq[0]
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    max_dd = float(np.max(dd))
    log_rets = np.diff(np.log(np.maximum(eq, 1e-9)))
    if len(log_rets) > 1 and np.std(log_rets) > 0:
        sharpe = (np.mean(log_rets) / np.std(log_rets, ddof=1)) * math.sqrt(2190)
    else:
        sharpe = 0.0
    return {"total_ret_pct": float(total_ret*100), "max_dd_pct": float(max_dd*100), "sharpe": float(sharpe)}


def fmt_date(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


async def main():
    t0 = time.time()
    print("Phase 13 — historical bear/sideways window test\n")

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
        closes, highs, lows, funding, times = align(funding_cache[sym], candles_cache[sym])
        n = len(closes)
        if n < 750: continue
        funding_z = rolling_zscore(funding, 180)

        worst_idx, worst_ret = find_worst_window(closes)
        side_idx, side_ret = find_most_sideways_window(closes)

        results[sym] = {}

        for label, idx, hodl_marker in [("WORST_DRAWDOWN", worst_idx, worst_ret),
                                         ("MOST_SIDEWAYS", side_idx, side_ret)]:
            if idx < 0:
                continue
            test_start = idx; test_end = min(n, idx + WINDOW_BARS)
            window_start_date = fmt_date(times[test_start])
            window_end_date = fmt_date(times[test_end - 1])

            hodl_eq = hodl_equity_curve(closes, test_start, test_end)
            leg1_eq, l1_n = leg1_equity_curve(closes, highs, lows, funding_z, test_start, test_end)

            portfolios = {
                "100% HODL": hodl_eq,
                "100% Leg1": leg1_eq,
                "90/10": blended(hodl_eq, leg1_eq, 0.9),
                "80/20": blended(hodl_eq, leg1_eq, 0.8),
                "70/30": blended(hodl_eq, leg1_eq, 0.7),
            }

            window_data = {"window_start": window_start_date, "window_end": window_end_date,
                           "hodl_marker": hodl_marker * 100, "leg1_trades": l1_n}
            for name, eq in portfolios.items():
                window_data[name] = metrics(eq)
            results[sym][label] = window_data

            print(f"\n=== {sym} {label} ({window_start_date} to {window_end_date}) ===")
            print(f"  Leg 1 fired {l1_n} times")
            for name, eq in portfolios.items():
                m = metrics(eq)
                print(f"  {name:12} ret={m['total_ret_pct']:+7.2f}% maxDD={m['max_dd_pct']:5.2f}% Sharpe={m['sharpe']:+.2f}")

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))

    lines = ["# Phase 13: HODL + Leg 1 Harvester on historical bear/sideways windows"]
    lines.append(f"\n**Method**: scan 28 months of 4h data, find each symbol's worst-90d-drawdown window AND most-sideways-90d window. Re-run HODL/Leg1 blends on each.\n")

    for window_type in ["WORST_DRAWDOWN", "MOST_SIDEWAYS"]:
        lines.append(f"\n## {window_type}")
        lines.append("| sym | window | L1 trades | 100% HODL ret/DD | 100% Leg1 ret/DD | 90/10 ret/DD | 80/20 ret/DD | 70/30 ret/DD |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for sym, data in results.items():
            if window_type not in data: continue
            d = data[window_type]
            def fmt(p):
                return f"{d[p]['total_ret_pct']:+.2f}% / {d[p]['max_dd_pct']:.1f}%"
            lines.append(f"| {sym} | {d['window_start']}→{d['window_end']} | {d['leg1_trades']} | {fmt('100% HODL')} | {fmt('100% Leg1')} | {fmt('90/10')} | {fmt('80/20')} | {fmt('70/30')} |")

        lines.append(f"\n### {window_type} — Sharpe comparison")
        lines.append("| sym | 100% HODL | 100% Leg1 | 90/10 | 80/20 | 70/30 |")
        lines.append("|---|---|---|---|---|---|")
        for sym, data in results.items():
            if window_type not in data: continue
            d = data[window_type]
            lines.append(f"| {sym} | {d['100% HODL']['sharpe']:+.2f} | {d['100% Leg1']['sharpe']:+.2f} | {d['90/10']['sharpe']:+.2f} | {d['80/20']['sharpe']:+.2f} | {d['70/30']['sharpe']:+.2f} |")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"\nwrote {OUT_RESULTS}")
    print(f"wrote {OUT_SUMMARY}")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
