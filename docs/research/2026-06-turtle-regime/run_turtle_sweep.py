"""Turtle/Donchian breakout sweep: period 20 vs 30/40/55, regime-gated vs not.

Validates the prior agent's claim (turtle_donchian.py code comment) that
Turtle System 2 (55-period) beats System 1 (20-period) on crypto perps.

RESEARCH ONLY. No live trading logic or wallet config touched. New files only.

Harness: real BacktestEngine + real TurtleDonchianStrategy + real MonteCarloEngine.
Candles from intel API (4h, ~27 months Hyperliquid backfill).

Two variants per cell:
  (a) no regime gate  -> macro_regime=None (both directions; SMA trend filter
      is intrinsic to the Donchian-with-trend-filter module and stays on).
  (b) regime-gated    -> per-bar TRENDING gate (ADX proxy > 25) injected as
      macro_regime; SMA200 trend filter (sma_trend_period=200) + only take
      longs above SMA200 in TRENDING_UP, shorts below in TRENDING_DOWN.

The base TurtleDonchianStrategy reads a *static* macro_regime from params, but
the trending gate must be evaluated per-bar. So variant (b) uses a thin wrapper
strategy (TurtleRegimeGated) registered into STRATEGIES that computes the regime
at each bar then delegates to the real strategy's evaluate().
"""

import asyncio
import json
import sys
import time
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

INTEL_API = "http://159.89.115.95:8000"
SYMBOLS = ["BTC", "ETH", "LINK"]
INTERVAL = "4h"
CANDLES_NEEDED = 5000

PERIODS = [20, 30, 40, 55]
START_EQUITY = 25000.0
COMMISSION_BPS = 5.0
SLIPPAGE_BPS = 5.0
ATR_PERIOD = 20
ATR_STOP_MULT = 2.0
SMA_TREND = 200
ADX_TRENDING = 25.0  # ADX proxy above this = trending regime

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "turtle_results.json"
OUT_SUMMARY = OUT_DIR / "turtle_summary.md"


# ---------- per-bar regime-gated wrapper strategy ----------

class TurtleRegimeGated(TurtleDonchianStrategy):
    """Computes a per-bar TRENDING regime (ADX proxy + SMA200 direction) and
    injects it as macro_regime before delegating to the parent evaluate().

    TRENDING_UP   if ADX>thr and close>SMA200
    TRENDING_DOWN if ADX>thr and close<SMA200
    else RANGING  (parent disables breakouts)
    """
    name = "turtle_regime_gated"

    @property
    def warmup_bars(self) -> int:
        return SMA_TREND + 1

    def evaluate(self, candles, current_idx, **params):
        needed = SMA_TREND + 1
        if current_idx < needed:
            return None
        # ADX over last ~60 bars (regime detector default lookback)
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


# register the wrapper so BacktestEngine can construct it by name
STRATEGIES["turtle_regime_gated"] = TurtleRegimeGated


# ---------- data ----------

async def fetch_candles(client, symbol):
    r = await client.get(
        f"{INTEL_API}/market/candles",
        params={"symbol": symbol, "interval": INTERVAL, "limit": CANDLES_NEEDED},
        timeout=90,
    )
    r.raise_for_status()
    return [Candle(**c) for c in r.json()["candles"]]


# ---------- backtest cell ----------

async def run_cell(symbol, candles, period, gated):
    params = {
        "breakout_period": period,
        "atr_period": ATR_PERIOD,
        "atr_stop_mult": ATR_STOP_MULT,
        "sma_trend_period": SMA_TREND,
        "size_pct": 15.0,
    }
    if not gated:
        # variant (a): static macro_regime=None -> both directions, SMA filter intrinsic
        params["macro_regime"] = None
        strat = "turtle_donchian"
    else:
        strat = "turtle_regime_gated"
    cfg = BacktestConfig(
        symbol=symbol, exchange="hyperliquid", interval=INTERVAL,
        start_time=candles[0].timestamp, end_time=candles[-1].timestamp,
        starting_equity=START_EQUITY, commission_bps=COMMISSION_BPS,
        slippage_bps=SLIPPAGE_BPS, strategy=strat, strategy_params=params,
        max_position_pct=25.0,
    )
    res = await BacktestEngine(cfg).run(candles)
    return res


def cell_metrics(res):
    m = res.metrics
    trades = res.trades
    n = len(trades)
    wins = [t for t in trades if t.pnl_usd > 0]
    losers = [t for t in trades if t.pnl_usd <= 0]
    avg_win = sum(t.pnl_usd for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.pnl_usd for t in losers) / len(losers) if losers else 0.0
    expectancy_usd = sum(t.pnl_usd for t in trades) / n if n else 0.0
    rr = (avg_win / abs(avg_loss)) if avg_loss != 0 else float("inf")
    longs = sum(1 for t in trades if t.direction == "long")
    shorts = n - longs
    return {
        "n_trades": n,
        "total_return_pct": round(m.total_return_pct, 2),
        "expectancy_usd": round(expectancy_usd, 2),
        "win_rate": round(m.win_rate * 100, 1),
        "avg_win_usd": round(avg_win, 2),
        "avg_loss_usd": round(avg_loss, 2),
        "avg_rr": round(rr, 2) if rr != float("inf") else None,
        "max_dd_pct": round(m.max_drawdown_pct, 2),
        "profit_factor": round(m.profit_factor, 2),
        "longs": longs,
        "shorts": shorts,
        "trade_returns_frac": [t.pnl_usd / START_EQUITY for t in trades],
    }


def monte_carlo_cell(trade_returns_frac, seed=42):
    """MC on trade-order resample. Returns p5 return %, prob(profit), ruin prob."""
    if len(trade_returns_frac) < 10:
        return {"runnable": False, "n": len(trade_returns_frac)}
    mc = MonteCarloEngine(n_simulations=5000, block_size=5, seed=seed)
    r = mc.run(trade_returns_frac)
    # prob(profit): re-derive from a parallel resample distribution
    rng = np.random.default_rng(seed + 1)
    arr = np.array(trade_returns_frac, dtype=np.float64)
    n = len(arr)
    pos = 0
    sims = 5000
    for _ in range(sims):
        # block bootstrap, same block size, total compounded return
        block = min(5, n)
        seq = []
        while len(seq) < n:
            s = rng.integers(0, max(1, n - block + 1))
            seq.extend(arr[s:s + block].tolist())
        seq = np.array(seq[:n])
        eq = np.prod(1.0 + seq)
        if eq > 1.0:
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


async def main():
    t0 = time.time()
    print("Turtle/Donchian sweep: BTC ETH LINK, periods", PERIODS, "interval", INTERVAL)
    async with httpx.AsyncClient() as client:
        candles_by_sym = {}
        for sym in SYMBOLS:
            c = await fetch_candles(client, sym)
            candles_by_sym[sym] = c
            import datetime as _dt
            s = _dt.datetime.utcfromtimestamp(c[0].timestamp / 1000).date()
            e = _dt.datetime.utcfromtimestamp(c[-1].timestamp / 1000).date()
            print(f"  {sym}: {len(c)} candles  {s} -> {e}")

    results = {"meta": {"interval": INTERVAL, "periods": PERIODS,
                        "start_equity": START_EQUITY, "atr_stop_mult": ATR_STOP_MULT,
                        "sma_trend": SMA_TREND, "adx_trending": ADX_TRENDING,
                        "commission_bps": COMMISSION_BPS, "slippage_bps": SLIPPAGE_BPS},
               "coverage": {}, "cells": {}}

    for sym in SYMBOLS:
        candles = candles_by_sym[sym]
        import datetime as _dt
        results["coverage"][sym] = {
            "candles": len(candles),
            "start": _dt.datetime.utcfromtimestamp(candles[0].timestamp / 1000).isoformat(),
            "end": _dt.datetime.utcfromtimestamp(candles[-1].timestamp / 1000).isoformat(),
            "days": round((candles[-1].timestamp - candles[0].timestamp) / 86400000, 0),
        }
        results["cells"][sym] = {}
        print(f"\n=== {sym} ===")
        for gated in (False, True):
            tag = "gated" if gated else "nofilter"
            for period in PERIODS:
                res = await run_cell(sym, candles, period, gated)
                cm = cell_metrics(res)
                key = f"p{period}_{tag}"
                results["cells"][sym][key] = cm
                print(f"  {key}: n={cm['n_trades']} ret={cm['total_return_pct']:+.1f}% "
                      f"exp=${cm['expectancy_usd']:+.0f} WR={cm['win_rate']}% "
                      f"RR={cm['avg_rr']} PF={cm['profit_factor']} DD={cm['max_dd_pct']}%")

    # ---- pick best cell per symbol (by expectancy, require n>=10) and MC it ----
    best = {}
    for sym in SYMBOLS:
        cells = results["cells"][sym]
        cand = [(k, v) for k, v in cells.items() if v["n_trades"] >= 10]
        if not cand:
            cand = list(cells.items())
        bk, bv = max(cand, key=lambda kv: kv[1]["expectancy_usd"])
        mc = monte_carlo_cell(bv["trade_returns_frac"])
        best[sym] = {"cell": bk, "metrics": {k: v for k, v in bv.items()
                                              if k != "trade_returns_frac"}, "monte_carlo": mc}
        print(f"\n  BEST {sym}: {bk} -> MC p5={mc.get('p5_return_pct')}% "
              f"prob_profit={mc.get('prob_profit_pct')}% ruin={mc.get('ruin_probability_pct')}%")
    results["best_cell"] = best

    # strip heavy arrays from saved json
    for sym in results["cells"]:
        for k in results["cells"][sym]:
            results["cells"][sym][k].pop("trade_returns_frac", None)

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")

    write_summary(results)
    print(f"wrote {OUT_SUMMARY}")
    print(f"total {time.time() - t0:.1f}s")


def write_summary(results):
    L = []
    L.append("# Turtle/Donchian Breakout Sweep — period 20 vs 30/40/55, regime-gated vs not\n")
    L.append("Real BacktestEngine + real TurtleDonchianStrategy + real MonteCarloEngine. "
             "RESEARCH ONLY — no live logic touched.\n")
    meta = results["meta"]
    L.append(f"**Config:** interval={meta['interval']}, ATR({ATR_PERIOD})x{meta['atr_stop_mult']} stop, "
             f"SMA({meta['sma_trend']}) trend filter, ADX-proxy>{meta['adx_trending']} = trending, "
             f"start_equity=${meta['start_equity']:.0f}, fees {meta['commission_bps']}/{meta['slippage_bps']} bps.\n")
    L.append("Variant **nofilter** = macro_regime=None (both directions; SMA trend filter intrinsic to module). "
             "Variant **gated** = per-bar TRENDING gate injected (longs above SMA200 in uptrend, shorts below in downtrend).\n")

    L.append("## Coverage\n")
    L.append("| symbol | candles | start | end | days |")
    L.append("|---|---|---|---|---|")
    for sym, cov in results["coverage"].items():
        L.append(f"| {sym} | {cov['candles']} | {cov['start'][:10]} | {cov['end'][:10]} | {cov['days']:.0f} |")
    L.append("")

    cols = "| period | n | ret% | exp$/tr | WR% | avgWin$ | avgLoss$ | R:R | PF | maxDD% | L/S |"
    sep = "|---|---|---|---|---|---|---|---|---|---|---|"
    for sym in SYMBOLS:
        cells = results["cells"][sym]
        L.append(f"## {sym}\n")
        for tag in ("nofilter", "gated"):
            L.append(f"### {sym} — {tag}\n")
            L.append(cols)
            L.append(sep)
            for p in PERIODS:
                v = cells.get(f"p{p}_{tag}")
                if not v:
                    continue
                L.append(f"| {p} | {v['n_trades']} | {v['total_return_pct']:+.1f} | "
                         f"{v['expectancy_usd']:+.1f} | {v['win_rate']} | {v['avg_win_usd']:+.0f} | "
                         f"{v['avg_loss_usd']:+.0f} | {v['avg_rr']} | {v['profit_factor']} | "
                         f"{v['max_dd_pct']} | {v['longs']}/{v['shorts']} |")
            L.append("")

    L.append("## Best cell per symbol + Monte Carlo (5000 sims, block bootstrap)\n")
    L.append("| symbol | best cell | n | exp$/tr | ret% | MC p5 ret% | MC median% | prob(profit)% | ruin% | grade |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for sym in SYMBOLS:
        b = results["best_cell"][sym]
        m = b["metrics"]
        mc = b["monte_carlo"]
        if mc.get("runnable"):
            L.append(f"| {sym} | {b['cell']} | {m['n_trades']} | {m['expectancy_usd']:+.1f} | "
                     f"{m['total_return_pct']:+.1f} | {mc['p5_return_pct']:+.1f} | {mc['median_return_pct']:+.1f} | "
                     f"{mc['prob_profit_pct']} | {mc['ruin_probability_pct']} | {mc['robustness_grade']} |")
        else:
            L.append(f"| {sym} | {b['cell']} | {m['n_trades']} | {m['expectancy_usd']:+.1f} | "
                     f"{m['total_return_pct']:+.1f} | n/a (n<10) | - | - | - | - |")
    L.append("")

    # ---- verdict ----
    L.append("## VERDICT\n")
    verdict_lines = []
    for sym in SYMBOLS:
        cells = results["cells"][sym]
        for tag in ("nofilter", "gated"):
            e20 = cells.get(f"p20_{tag}", {}).get("expectancy_usd")
            e55 = cells.get(f"p55_{tag}", {}).get("expectancy_usd")
            n20 = cells.get(f"p20_{tag}", {}).get("n_trades")
            n55 = cells.get(f"p55_{tag}", {}).get("n_trades")
            if e20 is not None and e55 is not None:
                gap = e55 - e20
                won = "55 WINS" if gap > 0 else "20 wins"
                verdict_lines.append(
                    f"- {sym} {tag}: p20 exp=${e20:+.1f} (n={n20}) vs p55 exp=${e55:+.1f} (n={n55}) "
                    f"-> gap ${gap:+.1f}/trade [{won}]")
    L.extend(verdict_lines)
    L.append("")
    L.append("See report-back section in agent output for PASS/FAIL determination and sample-size caveats.\n")

    OUT_SUMMARY.write_text("\n".join(L))


if __name__ == "__main__":
    asyncio.run(main())
