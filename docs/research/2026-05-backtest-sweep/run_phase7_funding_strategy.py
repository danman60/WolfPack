"""Phase 7: Funding-squeeze-long STRATEGY validation.

Phase 6 confirmed signal: funding-z < -2 → forward 24h return positive on BTC + DOGE.
Phase 5 taught us: signal != strategy. Stops/TPs can eat the edge.

This script runs a real strategy simulation:
  - Entry: when 30d funding z-score < threshold
  - Exit: first of {stop hit, take-profit hit, max-hold bars}
  - Realistic 5+5 bps round-trip cost
  - Per-symbol equity curve with max DD, Sharpe, beat-HODL

Sweeps stop_pct, tp_pct, max_hold_bars, threshold to find the geometry
that actually captures the signal. Reports best configuration per symbol.
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
OUT_RESULTS = OUT_DIR / "phase7_funding_strategy.json"
OUT_SUMMARY = OUT_DIR / "phase7_funding_strategy.md"


async def fetch_funding_history(client, coin, start_ms):
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


def align_funding_to_candles(funding_records, candles):
    funding_records.sort(key=lambda x: x["time"])
    f_times = np.array([r["time"] for r in funding_records])
    f_vals = np.array([float(r["fundingRate"]) for r in funding_records])
    closes = np.array([c.close for c in candles], dtype=np.float64)
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows = np.array([c.low for c in candles], dtype=np.float64)
    times = np.array([c.timestamp for c in candles])
    aligned = np.full(len(candles), np.nan)
    for i, t in enumerate(times):
        idx = np.searchsorted(f_times, t, side="right") - 1
        if idx >= 0: aligned[i] = f_vals[idx]
    return closes, highs, lows, aligned


def rolling_zscore(arr, window=180):
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        w = arr[i - window : i]
        w = w[~np.isnan(w)]
        if len(w) < window // 2: continue
        mu, sigma = np.mean(w), np.std(w, ddof=1)
        if sigma > 0: out[i] = (arr[i] - mu) / sigma
    return out


def simulate_strategy(closes, highs, lows, fired, threshold, sl_pct, tp_pct, max_hold):
    """Walk forward bar-by-bar; for each fire enter at close, exit at first of SL/TP/max_hold.

    Returns list of trade dicts and equity curve (1-indexed by bar).
    Position sizing: fixed 10% of equity per trade, no compounding leverage.
    """
    n = len(closes)
    trades = []
    equity = 1.0  # normalized
    equity_curve = np.zeros(n)
    equity_curve[0] = equity
    in_position_until = -1  # bar index when current trade exits
    pending_exit = None  # exit price of current trade

    for i in range(n):
        # Apply pending exit at this bar
        if i == in_position_until and pending_exit is not None:
            equity_curve[i] = equity
            pending_exit = None
            in_position_until = -1
        elif equity_curve[i] == 0:
            equity_curve[i] = equity_curve[i - 1] if i > 0 else 1.0

        # Already in a position; skip new entry
        if in_position_until > i:
            equity_curve[i] = equity
            continue

        if not fired[i] or i + max_hold >= n:
            continue

        entry = closes[i]
        sl_price = entry * (1 - sl_pct / 100.0)
        tp_price = entry * (1 + tp_pct / 100.0)

        exit_idx, exit_price, exit_reason = None, None, None
        for j in range(1, max_hold + 1):
            bar = i + j
            # SL/TP intrabar check
            if lows[bar] <= sl_price:
                exit_idx, exit_price, exit_reason = bar, sl_price, "stop"
                break
            if highs[bar] >= tp_price:
                exit_idx, exit_price, exit_reason = bar, tp_price, "tp"
                break
        if exit_idx is None:
            exit_idx = i + max_hold
            exit_price = closes[exit_idx]
            exit_reason = "time"

        gross_ret = (exit_price - entry) / entry
        net_ret = gross_ret - COST_PCT
        # Position sizing: 10% of equity
        equity_change = equity * 0.10 * net_ret
        equity += equity_change

        trades.append({
            "entry_idx": i, "exit_idx": exit_idx,
            "entry_price": entry, "exit_price": exit_price,
            "gross_ret_pct": gross_ret * 100,
            "net_ret_pct": net_ret * 100,
            "equity_after": equity,
            "exit_reason": exit_reason,
            "hold_bars": exit_idx - i,
        })
        in_position_until = exit_idx
        equity_curve[i] = equity

    # forward-fill equity_curve
    for i in range(1, n):
        if equity_curve[i] == 0:
            equity_curve[i] = equity_curve[i - 1]
    return trades, equity_curve


def compute_metrics(trades, equity_curve, closes):
    if not trades:
        return None
    rets = np.array([t["net_ret_pct"] / 100 for t in trades])
    wins = sum(1 for t in trades if t["net_ret_pct"] > 0)
    n = len(trades)
    cum_pct = (equity_curve[-1] - 1) * 100
    # Max drawdown on equity curve
    peak = np.maximum.accumulate(equity_curve)
    dd = (peak - equity_curve) / peak
    max_dd_pct = float(np.max(dd)) * 100
    # Sharpe — using bar-level equity-curve daily-resampled returns
    # Resample to ~6 bars/day (4h)
    daily_eq = equity_curve[::6]
    if len(daily_eq) > 5:
        daily_rets = np.diff(np.log(np.maximum(daily_eq, 1e-9)))
        daily_rets = daily_rets[~np.isnan(daily_rets)]
        if len(daily_rets) > 1 and np.std(daily_rets) > 0:
            sharpe = (np.mean(daily_rets) / np.std(daily_rets, ddof=1)) * math.sqrt(365)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0
    hodl_pct = (closes[-1] / closes[0] - 1) * 100
    return {
        "trades": n, "wins": wins, "wr": wins / n if n else 0,
        "cum_pct": float(cum_pct), "max_dd_pct": max_dd_pct,
        "sharpe": float(sharpe), "hodl_pct": hodl_pct,
        "beats_hodl": cum_pct > hodl_pct,
        "avg_hold_bars": float(np.mean([t["hold_bars"] for t in trades])),
        "tp_exits": sum(1 for t in trades if t["exit_reason"] == "tp"),
        "sl_exits": sum(1 for t in trades if t["exit_reason"] == "stop"),
        "time_exits": sum(1 for t in trades if t["exit_reason"] == "time"),
    }


async def main():
    t0 = time.time()
    print("Phase 7 — funding-squeeze-long STRATEGY validation\n")

    funding_cache, candles_cache = {}, {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            print(f"fetching {sym}...")
            funding_cache[sym] = await fetch_funding_history(client, sym, 1704067200000)
            await asyncio.sleep(2)
            candles_cache[sym] = await fetch_candles(client, sym)
            print(f"  funding={len(funding_cache[sym])} candles={len(candles_cache[sym])}")
    print(f"fetch took {time.time()-t0:.0f}s\n")

    # Per-symbol pre-compute
    by_sym = {}
    for sym in SYMBOLS:
        closes, highs, lows, funding = align_funding_to_candles(funding_cache[sym], candles_cache[sym])
        if np.sum(~np.isnan(funding)) < 200:
            print(f"{sym}: not enough data"); continue
        z = rolling_zscore(funding, window=180)
        by_sym[sym] = (closes, highs, lows, z)

    results = []

    # PASS 1: default params on all 7 symbols
    print("=== PASS 1: default params (threshold=-2.0, sl=3%, tp=2%, hold=12 bars=48h) ===")
    default = {"threshold": -2.0, "sl_pct": 3.0, "tp_pct": 2.0, "max_hold": 12}
    for sym in SYMBOLS:
        if sym not in by_sym: continue
        closes, highs, lows, z = by_sym[sym]
        fired = z < default["threshold"]
        trades, eq = simulate_strategy(closes, highs, lows, fired, default["threshold"], default["sl_pct"], default["tp_pct"], default["max_hold"])
        m = compute_metrics(trades, eq, closes)
        if m:
            print(f"  {sym:5} trades={m['trades']:3} WR={m['wr']*100:.1f}% cum={m['cum_pct']:+.2f}% Sharpe={m['sharpe']:+.2f} maxDD={m['max_dd_pct']:.1f}% HODL={m['hodl_pct']:+.1f}% beats={m['beats_hodl']} (TP={m['tp_exits']} SL={m['sl_exits']} time={m['time_exits']})")
            results.append({"symbol": sym, "params": default, "pass": "default", **m})

    # PASS 2: param sweep on BTC + DOGE (Phase 6 survivors)
    print("\n=== PASS 2: param sweep on BTC + DOGE ===")
    grid = []
    for thresh in [-1.5, -2.0, -2.5]:
        for sl in [2.0, 3.0, 5.0]:
            for tp in [1.5, 2.0, 3.0, 5.0]:
                for hold in [6, 12, 18, 24]:
                    grid.append({"threshold": thresh, "sl_pct": sl, "tp_pct": tp, "max_hold": hold})
    print(f"  {len(grid)} param combos × 2 symbols = {len(grid)*2} cells")
    for sym in ["BTC", "DOGE"]:
        if sym not in by_sym: continue
        closes, highs, lows, z = by_sym[sym]
        for params in grid:
            fired = z < params["threshold"]
            trades, eq = simulate_strategy(closes, highs, lows, fired, params["threshold"], params["sl_pct"], params["tp_pct"], params["max_hold"])
            m = compute_metrics(trades, eq, closes)
            if m and m["trades"] >= 20:
                results.append({"symbol": sym, "params": params, "pass": "sweep", **m})

    # Best per symbol
    print("\n=== best params per symbol (Sharpe ranked, min 20 trades) ===")
    for sym in ["BTC", "DOGE"]:
        sym_runs = [r for r in results if r["symbol"] == sym and r["pass"] == "sweep" and r["trades"] >= 20]
        sym_runs.sort(key=lambda x: -x["sharpe"])
        if sym_runs:
            top = sym_runs[0]
            p = top["params"]
            print(f"  {sym}: thresh={p['threshold']} sl={p['sl_pct']}% tp={p['tp_pct']}% hold={p['max_hold']} → "
                  f"trades={top['trades']} cum={top['cum_pct']:+.2f}% Sharpe={top['sharpe']:+.2f} maxDD={top['max_dd_pct']:.1f}% HODL={top['hodl_pct']:+.1f}% beats={top['beats_hodl']}")

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))

    # Summary md
    lines = ["# Phase 7: funding-squeeze-long strategy validation"]
    lines.append("\nReal strategy simulation: enter on funding-z-low, exit at first of {stop, take-profit, max-hold}.")
    lines.append(f"\n**Round-trip cost**: {ROUND_TRIP_BPS} bps. **Position size**: 10% of equity per trade. **Equity curve**: compounded.\n")

    lines.append("## Pass 1 — default params (thresh=-2.0, SL=3%, TP=2%, hold=48h)")
    lines.append("| sym | trades | WR% | cum% | Sharpe | maxDD% | HODL% | beats | TP/SL/time |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in [r for r in results if r["pass"] == "default"]:
        beats = "✓" if r["beats_hodl"] else "✗"
        lines.append(f"| {r['symbol']} | {r['trades']} | {r['wr']*100:.1f} | {r['cum_pct']:+.2f} | {r['sharpe']:+.2f} | {r['max_dd_pct']:.1f} | {r['hodl_pct']:+.1f} | {beats} | {r['tp_exits']}/{r['sl_exits']}/{r['time_exits']} |")

    lines.append("\n## Pass 2 — best params per symbol (sweep top 10 by Sharpe)")
    for sym in ["BTC", "DOGE"]:
        sym_runs = [r for r in results if r["symbol"] == sym and r["pass"] == "sweep" and r["trades"] >= 20]
        sym_runs.sort(key=lambda x: -x["sharpe"])
        if not sym_runs: continue
        lines.append(f"\n### {sym}")
        lines.append(f"\n*HODL over same window: {sym_runs[0]['hodl_pct']:+.1f}%*\n")
        lines.append("| thresh | SL% | TP% | hold | trades | WR% | cum% | Sharpe | maxDD% | beats |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in sym_runs[:10]:
            p = r["params"]; beats = "✓" if r["beats_hodl"] else "✗"
            lines.append(f"| {p['threshold']} | {p['sl_pct']} | {p['tp_pct']} | {p['max_hold']} | {r['trades']} | {r['wr']*100:.1f} | {r['cum_pct']:+.2f} | {r['sharpe']:+.2f} | {r['max_dd_pct']:.1f} | {beats} |")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"\nwrote {OUT_RESULTS}")
    print(f"wrote {OUT_SUMMARY}")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
