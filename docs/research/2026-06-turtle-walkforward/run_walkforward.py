"""Turtle/Donchian walk-forward validation — BTC/ETH, 4h + 1d.

Kills or confirms the single-window regime-luck risk flagged by the
2026-06-turtle-regime sweep (best cells: ETH p30 nofilter, BTC p40 gated;
MC p5 negative on all best cells).

RESEARCH ONLY. No live trading logic, wallet config, or strategies/ touched.
New files under docs/research/2026-06-turtle-walkforward/ only.

Harness: same as 2026-06-turtle-regime/run_turtle_sweep.py — real
BacktestEngine + real TurtleDonchianStrategy + per-bar regime-gated wrapper +
real MonteCarloEngine. Candles direct from Hyperliquid API (intel API on
droplet refused connections on port 8000 at run time; same upstream source,
~5001-candle cap per (symbol, interval)).

Design:
1a. Anchored 60/40: optimize (period in {20..55 step 5}) x (nofilter, gated)
    on first 60% by expectancy (PF tiebreak, n>=10). Freeze best cell, run on
    last 40% (with exactly WARMUP=201 context bars prepended so first
    tradeable bar == split).
1b. Rolling: 4 expanding-window folds, test ~3 months (540 4h bars) each.
    Re-optimize per fold on train, test next window. Track IS-best drift.
1c. Neighborhood: OOS performance of p*±5, p*±10 (same variant).
2.  Same anchored 60/40 at 1d.
3.  Costs 10bps default (5 commission + 5 slippage, same as prior sweep);
    OOS best cells re-run at 15bps (7.5 + 7.5).
4.  MC (block bootstrap, same method as prior sweep) on OOS trade lists.
"""

import asyncio
import json
import sys
import time
import datetime as dt
from pathlib import Path

INTEL_PATH = Path(__file__).resolve().parents[3] / "intel"
sys.path.insert(0, str(INTEL_PATH))

import numpy as np
import httpx

from wolfpack.exchanges.base import Candle
from wolfpack.models.backtest_models import BacktestConfig
from wolfpack.backtest_engine import BacktestEngine
from wolfpack.strategies import STRATEGIES
from wolfpack.strategies.turtle_donchian import TurtleDonchianStrategy
from wolfpack.modules.regime import _adx_proxy
from wolfpack.modules.monte_carlo import MonteCarloEngine

HL_API = "https://api.hyperliquid.xyz/info"
SYMBOLS = ["BTC", "ETH"]
PERIODS = [20, 25, 30, 35, 40, 45, 50, 55]
VARIANTS = ["nofilter", "gated"]

START_EQUITY = 25000.0
COMMISSION_BPS = 5.0   # 10 bps total default — same as prior sweep
SLIPPAGE_BPS = 5.0
STRESS_COMMISSION_BPS = 7.5  # 15 bps total stress
STRESS_SLIPPAGE_BPS = 7.5
ATR_PERIOD = 20
ATR_STOP_MULT = 2.0
SMA_TREND = 200
ADX_TRENDING = 25.0
WARMUP = SMA_TREND + 1  # first bar evaluate() can fire on

N_FOLDS = 4
FOLD_TEST_BARS_4H = 540  # ~3 months of 4h bars (90d * 6)

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "walkforward_results.json"
CACHE = OUT_DIR / "candle_cache.json"


# ---------- per-bar regime-gated wrapper (copied from prior sweep) ----------

class TurtleRegimeGated(TurtleDonchianStrategy):
    name = "turtle_regime_gated"

    @property
    def warmup_bars(self) -> int:
        return WARMUP

    def evaluate(self, candles, current_idx, **params):
        if current_idx < WARMUP:
            return None
        lo = max(0, current_idx - 60)
        window = candles[lo: current_idx + 1]
        highs = np.array([c.high for c in window], dtype=np.float64)
        lows = np.array([c.low for c in window], dtype=np.float64)
        closes = np.array([c.close for c in window], dtype=np.float64)
        adx = _adx_proxy(highs, lows, closes, 14)
        sma200 = float(np.mean(np.array(
            [c.close for c in candles[current_idx - SMA_TREND + 1: current_idx + 1]],
            dtype=np.float64)))
        close = candles[current_idx].close
        if adx >= ADX_TRENDING:
            regime = "TRENDING_UP" if close > sma200 else "TRENDING_DOWN"
        else:
            regime = "RANGING"
        params = dict(params)
        params["macro_regime"] = regime
        return super().evaluate(candles, current_idx, **params)


STRATEGIES["turtle_regime_gated"] = TurtleRegimeGated


# ---------- data ----------

async def fetch_candles(client: httpx.AsyncClient, symbol: str, interval: str) -> list[Candle]:
    span_ms = {"4h": 5001 * 4 * 3600 * 1000, "1d": 5001 * 86400 * 1000}[interval]
    now = int(time.time() * 1000)
    r = await client.post(HL_API, json={
        "type": "candleSnapshot",
        "req": {"coin": symbol, "interval": interval,
                "startTime": now - span_ms, "endTime": now},
    }, timeout=90)
    r.raise_for_status()
    raw = r.json()
    return [Candle(timestamp=int(c["t"]), open=float(c["o"]), high=float(c["h"]),
                   low=float(c["l"]), close=float(c["c"]), volume=float(c["v"]))
            for c in raw]


def d(ts_ms) -> str:
    return dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc).date().isoformat()


# ---------- backtest cell ----------

async def run_cell(symbol, candles, interval, period, gated,
                   commission_bps=COMMISSION_BPS, slippage_bps=SLIPPAGE_BPS):
    params = {
        "breakout_period": period,
        "atr_period": ATR_PERIOD,
        "atr_stop_mult": ATR_STOP_MULT,
        "sma_trend_period": SMA_TREND,
        "size_pct": 15.0,
    }
    if not gated:
        params["macro_regime"] = None
        strat = "turtle_donchian"
    else:
        strat = "turtle_regime_gated"
    cfg = BacktestConfig(
        symbol=symbol, exchange="hyperliquid", interval=interval,
        start_time=candles[0].timestamp, end_time=candles[-1].timestamp,
        starting_equity=START_EQUITY, commission_bps=commission_bps,
        slippage_bps=slippage_bps, strategy=strat, strategy_params=params,
        max_position_pct=25.0,
    )
    return await BacktestEngine(cfg).run(candles)


def cell_metrics(res):
    m = res.metrics
    trades = res.trades
    n = len(trades)
    expectancy_usd = sum(t.pnl_usd for t in trades) / n if n else 0.0
    return {
        "n_trades": n,
        "total_return_pct": round(m.total_return_pct, 2),
        "expectancy_usd": round(expectancy_usd, 2),
        "win_rate": round(m.win_rate * 100, 1),
        "max_dd_pct": round(m.max_drawdown_pct, 2),
        "profit_factor": round(m.profit_factor, 2),
        "trade_returns_frac": [t.pnl_usd / START_EQUITY for t in trades],
    }


def strip(cm):
    return {k: v for k, v in cm.items() if k != "trade_returns_frac"}


def monte_carlo_cell(trade_returns_frac, seed=42):
    """Same MC method as prior sweep: block bootstrap, 5000 sims."""
    if len(trade_returns_frac) < 10:
        return {"runnable": False, "n": len(trade_returns_frac)}
    mc = MonteCarloEngine(n_simulations=5000, block_size=5, seed=seed)
    r = mc.run(trade_returns_frac)
    rng = np.random.default_rng(seed + 1)
    arr = np.array(trade_returns_frac, dtype=np.float64)
    n = len(arr)
    pos = 0
    sims = 5000
    for _ in range(sims):
        block = min(5, n)
        seq = []
        while len(seq) < n:
            s = rng.integers(0, max(1, n - block + 1))
            seq.extend(arr[s:s + block].tolist())
        seq = np.array(seq[:n])
        if np.prod(1.0 + seq) > 1.0:
            pos += 1
    return {
        "runnable": True,
        "n": n,
        "p5_return_pct": r.p5_return_pct,
        "median_return_pct": r.median_return_pct,
        "p95_return_pct": r.p95_return_pct,
        "ruin_probability_pct": r.ruin_probability,
        "prob_profit_pct": round(pos / sims * 100, 1),
        "robustness_grade": r.robustness_grade,
    }


# ---------- selection ----------

async def optimize_is(symbol, train, interval):
    """Run the full grid on train slice; return (cells dict, best key)."""
    cells = {}
    for variant in VARIANTS:
        gated = variant == "gated"
        for p in PERIODS:
            res = await run_cell(symbol, train, interval, p, gated)
            cells[f"p{p}_{variant}"] = cell_metrics(res)
    cand = [(k, v) for k, v in cells.items() if v["n_trades"] >= 10]
    if not cand:
        cand = list(cells.items())
    bk, _ = max(cand, key=lambda kv: (kv[1]["expectancy_usd"], kv[1]["profit_factor"]))
    return cells, bk


def parse_cell(key):
    p, variant = key.split("_", 1)
    return int(p[1:]), variant


async def oos_run(symbol, candles, split, end, interval, period, gated,
                  commission_bps=COMMISSION_BPS, slippage_bps=SLIPPAGE_BPS):
    """Run on candles[split:end] with exactly WARMUP context bars prepended,
    so the first bar a signal can fire on is candles[split]."""
    sl = candles[max(0, split - WARMUP): end]
    res = await run_cell(symbol, sl, interval, period, gated, commission_bps, slippage_bps)
    return cell_metrics(res)


# ---------- main ----------

async def main():
    t0 = time.time()
    results = {"meta": {
        "symbols": SYMBOLS, "periods": PERIODS, "variants": VARIANTS,
        "start_equity": START_EQUITY,
        "cost_default_bps": COMMISSION_BPS + SLIPPAGE_BPS,
        "cost_stress_bps": STRESS_COMMISSION_BPS + STRESS_SLIPPAGE_BPS,
        "atr_stop_mult": ATR_STOP_MULT, "sma_trend": SMA_TREND,
        "adx_trending": ADX_TRENDING, "warmup_bars": WARMUP,
        "n_folds": N_FOLDS, "fold_test_bars_4h": FOLD_TEST_BARS_4H,
        "candle_source": "hyperliquid candleSnapshot direct",
    }, "coverage": {}, "anchored": {}, "rolling": {}}

    # ---- fetch all candles ----
    candles_all = {}
    async with httpx.AsyncClient() as client:
        for interval in ("4h", "1d"):
            for sym in SYMBOLS:
                c = await fetch_candles(client, sym, interval)
                candles_all[(sym, interval)] = c
                results["coverage"][f"{sym}_{interval}"] = {
                    "candles": len(c), "start": d(c[0].timestamp), "end": d(c[-1].timestamp)}
                print(f"fetched {sym} {interval}: {len(c)} candles {d(c[0].timestamp)} -> {d(c[-1].timestamp)}",
                      flush=True)
                if len(c) < 1000:
                    print(f"WARNING: short history for {sym} {interval}: {len(c)} candles", flush=True)

    # ---- anchored 60/40 (both intervals) + neighborhood + stress + MC ----
    for interval in ("4h", "1d"):
        for sym in SYMBOLS:
            candles = candles_all[(sym, interval)]
            N = len(candles)
            split = int(N * 0.6)
            train, test_end = candles[:split], N
            print(f"\n=== anchored {sym} {interval}: N={N} split={split} "
                  f"IS {d(candles[0].timestamp)}->{d(candles[split-1].timestamp)} "
                  f"OOS {d(candles[split].timestamp)}->{d(candles[-1].timestamp)} ===", flush=True)

            is_cells, best_key = await optimize_is(sym, train, interval)
            p_star, variant = parse_cell(best_key)
            gated = variant == "gated"
            for k, v in is_cells.items():
                print(f"  IS {k}: n={v['n_trades']} exp=${v['expectancy_usd']:+.1f} "
                      f"PF={v['profit_factor']} ret={v['total_return_pct']:+.1f}%", flush=True)
            print(f"  IS BEST: {best_key}", flush=True)

            oos = await oos_run(sym, candles, split, N, interval, p_star, gated)
            print(f"  OOS {best_key}: n={oos['n_trades']} exp=${oos['expectancy_usd']:+.1f} "
                  f"ret={oos['total_return_pct']:+.1f}% PF={oos['profit_factor']} "
                  f"WR={oos['win_rate']}% DD={oos['max_dd_pct']}%", flush=True)

            # neighborhood p*±5, ±10 (same variant), OOS
            nbrs = {}
            for dp in (-10, -5, 5, 10):
                pn = p_star + dp
                if pn < 10:
                    nbrs[f"p{pn}"] = {"skipped": "period<10"}
                    continue
                nm = await oos_run(sym, candles, split, N, interval, pn, gated)
                nbrs[f"p{pn}"] = strip(nm)
                print(f"  OOS nbr p{pn}_{variant}: n={nm['n_trades']} exp=${nm['expectancy_usd']:+.1f} "
                      f"PF={nm['profit_factor']} ret={nm['total_return_pct']:+.1f}%", flush=True)

            # 15 bps stress on frozen cell, OOS
            stress = await oos_run(sym, candles, split, N, interval, p_star, gated,
                                   STRESS_COMMISSION_BPS, STRESS_SLIPPAGE_BPS)
            print(f"  OOS 15bps {best_key}: exp=${stress['expectancy_usd']:+.1f} "
                  f"PF={stress['profit_factor']} ret={stress['total_return_pct']:+.1f}%", flush=True)

            mc = monte_carlo_cell(oos["trade_returns_frac"])
            print(f"  OOS MC: {mc}", flush=True)

            results["anchored"][f"{sym}_{interval}"] = {
                "n_candles": N, "split_idx": split,
                "is_range": [d(candles[0].timestamp), d(candles[split - 1].timestamp)],
                "oos_range": [d(candles[split].timestamp), d(candles[-1].timestamp)],
                "is_cells": {k: strip(v) for k, v in is_cells.items()},
                "is_best": best_key,
                "oos_frozen": strip(oos),
                "oos_neighbors": nbrs,
                "oos_stress_15bps": strip(stress),
                "oos_monte_carlo": mc,
            }

    # ---- rolling expanding-window folds (4h only) ----
    for sym in SYMBOLS:
        candles = candles_all[(sym, "4h")]
        N = len(candles)
        first_test = N - N_FOLDS * FOLD_TEST_BARS_4H
        folds = []
        for k in range(N_FOLDS):
            b = first_test + k * FOLD_TEST_BARS_4H
            e = b + FOLD_TEST_BARS_4H
            train = candles[:b]
            print(f"\n=== rolling {sym} 4h fold {k+1}: train {d(candles[0].timestamp)}->"
                  f"{d(candles[b-1].timestamp)} ({b} bars), test {d(candles[b].timestamp)}->"
                  f"{d(candles[e-1].timestamp)} ===", flush=True)
            is_cells, best_key = await optimize_is(sym, train, "4h")
            p_star, variant = parse_cell(best_key)
            oos = await oos_run(sym, candles, b, e, "4h", p_star, variant == "gated")
            print(f"  fold {k+1} IS-best {best_key} -> OOS n={oos['n_trades']} "
                  f"exp=${oos['expectancy_usd']:+.1f} ret={oos['total_return_pct']:+.1f}% "
                  f"PF={oos['profit_factor']}", flush=True)
            folds.append({
                "fold": k + 1,
                "train_bars": b,
                "test_range": [d(candles[b].timestamp), d(candles[e - 1].timestamp)],
                "is_best": best_key,
                "is_best_metrics": strip(is_cells[best_key]),
                "is_top3": sorted(
                    ((kk, vv["expectancy_usd"], vv["profit_factor"], vv["n_trades"])
                     for kk, vv in is_cells.items() if vv["n_trades"] >= 10),
                    key=lambda x: (x[1], x[2]), reverse=True)[:3],
                "oos": strip(oos),
            })
        results["rolling"][sym] = folds

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")
    print(f"total {time.time() - t0:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
