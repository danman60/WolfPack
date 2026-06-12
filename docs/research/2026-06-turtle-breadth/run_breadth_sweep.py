"""Turtle breadth study — step 2: per-symbol Donchian long-only sweep.

RESEARCH ONLY. Real BacktestEngine + real TurtleDonchianStrategy, same mechanics
as docs/research/2026-06-turtle-regime/run_turtle_sweep.py:
  - 4h candles, ATR(20)x2.0 stop, SMA(200) trend filter, size_pct=15, equity $25k
  - long-only: static macro_regime="TRENDING_UP" (longs allowed, shorts gated off;
    structural close signals still fire)
  - periods p in {20, 30, 40, 55}
Costs (per side, commission+slippage; engine vol-scales slippage at entry):
  - majors (BTC/ETH/SOL/XRP): 10 bps total (5 comm + 5 slip)
  - other alts:               20 bps total (10 + 10)
  - stress variant:          +10 bps on top of each
Outputs:
  - breadth_results.json  (per symbol x period x cost: metrics + trade fracs)
  - equity_curves.npz     (base-cost equity curve per symbol x period, + timestamps)
"""

import asyncio
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

INTEL_PATH = Path(__file__).resolve().parents[3] / "intel"
sys.path.insert(0, str(INTEL_PATH))

OUT_DIR = Path(__file__).parent
CANDLE_DIR = OUT_DIR / "candles"

PERIODS = [20, 30, 40, 55]
MAJORS = {"BTC", "ETH", "SOL", "XRP"}
START_EQUITY = 25000.0
ATR_PERIOD = 20
ATR_STOP_MULT = 2.0
SMA_TREND = 200
SIZE_PCT = 15.0
MAX_POS_PCT = 25.0
INTERVAL = "4h"


def load_candles(sym):
    from wolfpack.exchanges.base import Candle
    rows = json.loads((CANDLE_DIR / f"{sym}.json").read_text())
    return [Candle(timestamp=r[0], open=r[1], high=r[2], low=r[3],
                   close=r[4], volume=r[5]) for r in rows]


async def run_cell(sym, candles, period, half_cost_bps):
    from wolfpack.models.backtest_models import BacktestConfig
    from wolfpack.backtest_engine import BacktestEngine
    params = {
        "breakout_period": period,
        "atr_period": ATR_PERIOD,
        "atr_stop_mult": ATR_STOP_MULT,
        "sma_trend_period": SMA_TREND,
        "size_pct": SIZE_PCT,
        "macro_regime": "TRENDING_UP",  # long-only
    }
    cfg = BacktestConfig(
        symbol=sym, exchange="hyperliquid", interval=INTERVAL,
        start_time=candles[0].timestamp, end_time=candles[-1].timestamp,
        starting_equity=START_EQUITY,
        commission_bps=half_cost_bps, slippage_bps=half_cost_bps,
        strategy="turtle_donchian", strategy_params=params,
        max_position_pct=MAX_POS_PCT,
    )
    return await BacktestEngine(cfg).run(candles)


def cell_metrics(res):
    m = res.metrics
    trades = res.trades
    n = len(trades)
    wins = [t for t in trades if t.pnl_usd > 0]
    losers = [t for t in trades if t.pnl_usd <= 0]
    expectancy_usd = sum(t.pnl_usd for t in trades) / n if n else 0.0
    return {
        "n_trades": n,
        "total_return_pct": round(m.total_return_pct, 2),
        "expectancy_usd": round(expectancy_usd, 2),
        "expectancy_bps_of_equity": round(expectancy_usd / START_EQUITY * 1e4, 1),
        "win_rate": round(m.win_rate * 100, 1),
        "profit_factor": round(m.profit_factor, 2),
        "max_dd_pct": round(m.max_drawdown_pct, 2),
        "avg_holding_bars": round(sum(t.holding_bars for t in trades) / n, 1) if n else 0,
        "trade_returns_frac": [t.pnl_usd / START_EQUITY for t in trades],
    }


def run_symbol(sym):
    """Worker: full sweep for one symbol. Returns (sym, cells, curves)."""
    candles = load_candles(sym)
    half_base = 5.0 if sym in MAJORS else 10.0
    out_cells = {}
    curves = {"t": [c.timestamp for c in candles]}
    for period in PERIODS:
        for tag, half in (("base", half_base), ("stress", half_base + 5.0)):
            res = asyncio.run(run_cell(sym, candles, period, half))
            out_cells[f"p{period}_{tag}"] = cell_metrics(res)
            if tag == "base":
                # equity curve starts at warmup; pad front with start equity
                eq = {p["time"]: p["equity"] for p in res.equity_curve}
                curves[f"p{period}"] = [eq.get(c.timestamp, None) for c in candles]
    return sym, {
        "cost_bps_per_side": half_base * 2,
        "n_candles": len(candles),
        "start": candles[0].timestamp, "end": candles[-1].timestamp,
        "cells": out_cells,
    }, curves


def main():
    t0 = time.time()
    uni = json.loads((OUT_DIR / "universe.json").read_text())
    symbols = [r["symbol"] for r in uni["universe"]]
    print(f"sweep: {len(symbols)} symbols x {len(PERIODS)} periods x 2 cost levels")

    results = {"meta": {
        "interval": INTERVAL, "periods": PERIODS, "start_equity": START_EQUITY,
        "atr": f"ATR({ATR_PERIOD})x{ATR_STOP_MULT}", "sma_trend": SMA_TREND,
        "size_pct": SIZE_PCT, "direction": "long-only (macro_regime=TRENDING_UP)",
        "majors_cost_bps_side": 10, "alt_cost_bps_side": 20, "stress_extra_bps_side": 10,
        "majors": sorted(MAJORS),
    }, "symbols": {}}

    import numpy as np
    npz = {}
    with ProcessPoolExecutor(max_workers=8) as ex:
        for sym, data, curves in ex.map(run_symbol, symbols):
            results["symbols"][sym] = data
            npz[f"{sym}__t"] = np.array(curves["t"], dtype=np.int64)
            for p in PERIODS:
                arr = np.array([x if x is not None else np.nan
                                for x in curves[f"p{p}"]], dtype=np.float64)
                npz[f"{sym}__p{p}"] = arr
            c30 = data["cells"]["p30_base"]
            c40 = data["cells"]["p40_base"]
            print(f"  {sym}: p30 ret={c30['total_return_pct']:+.1f}% exp={c30['expectancy_bps_of_equity']:+.1f}bps "
                  f"PF={c30['profit_factor']} | p40 ret={c40['total_return_pct']:+.1f}% "
                  f"exp={c40['expectancy_bps_of_equity']:+.1f}bps PF={c40['profit_factor']}", flush=True)

    np.savez_compressed(OUT_DIR / "equity_curves.npz", **npz)
    # strip trade arrays into separate compact storage inside json (keep for MC/portfolio)
    (OUT_DIR / "breadth_results.json").write_text(json.dumps(results, indent=1))
    print(f"wrote breadth_results.json + equity_curves.npz in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
