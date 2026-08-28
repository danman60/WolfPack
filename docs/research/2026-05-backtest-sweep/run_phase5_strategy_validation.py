"""Phase 5: validate that capitulation_flush as a STRATEGY (with stops/TP/sizing)
matches the conditional expectancy found in Phase 4.

If P&L from full strategy backtest (with realistic 5+5 bps fees, ATR-based SL/TP,
production PaperTradingEngine) ≈ Phase 4 conditional, the signal translates.
If it's substantially worse, the SL/TP rules are eating the edge.

Tests survivor cells from Phase 4:
  - LINK 4h
  - AVAX 4h
  - DOGE 4h
Plus the failed cells (BTC, ETH, SOL, ARB) as control to verify the strategy
does NOT make money on symbols that failed Phase 4.

Also runs a parameter robustness sweep on the survivors:
  - stop_atr_mult ∈ {2, 3, 4}
  - tp_atr_mult ∈ {1.0, 1.5, 2.0, 3.0}
  - percentile ∈ {3, 5, 10}
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from collections import defaultdict

INTEL_PATH = Path(__file__).resolve().parents[3] / "intel"
sys.path.insert(0, str(INTEL_PATH))

import httpx
from wolfpack.exchanges.base import Candle
from wolfpack.models.backtest_models import BacktestConfig
from wolfpack.backtest_engine import BacktestEngine

INTEL_API = "http://159.89.115.95:8000"
SYMBOLS = ["BTC", "ETH", "SOL", "LINK", "AVAX", "ARB", "DOGE"]
INTERVAL = "4h"
LIMIT = 5000

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase5_strategy_validation.json"
OUT_SUMMARY = OUT_DIR / "phase5_strategy_validation.md"


async def fetch_candles(client, symbol):
    r = await client.get(
        f"{INTEL_API}/market/candles",
        params={"symbol": symbol, "interval": INTERVAL, "limit": LIMIT},
        timeout=120,
    )
    r.raise_for_status()
    return [Candle(**c) for c in r.json()["candles"]]


async def run_backtest(symbol, candles, params):
    cfg = BacktestConfig(
        symbol=symbol, exchange="hyperliquid", interval=INTERVAL,
        start_time=candles[0].timestamp, end_time=candles[-1].timestamp,
        starting_equity=25000.0, commission_bps=5.0, slippage_bps=5.0,
        strategy="capitulation_flush", strategy_params=params, max_position_pct=25.0,
    )
    engine = BacktestEngine(cfg)
    result = await engine.run(candles)
    return result


def summarize_result(result, label):
    m = result.metrics
    return {
        "label": label,
        "trades": m.total_trades,
        "ret_pct": m.total_return_pct,
        "wr": m.win_rate * 100,
        "sharpe": m.sharpe_ratio,
        "calmar": m.calmar_ratio,
        "max_dd_pct": m.max_drawdown_pct,
        "expectancy_pct": m.expectancy_pct,
        "profit_factor": m.profit_factor,
        "avg_holding_bars": m.avg_holding_bars,
    }


async def main():
    t0 = time.time()
    print("Phase 5 — capitulation_flush strategy validation")
    print()

    candles_cache = {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            print(f"fetching {sym} 4h...")
            candles_cache[sym] = await fetch_candles(client, sym)
    print(f"fetched in {time.time()-t0:.0f}s\n")

    results = []

    # PASS 1: default params on all 7 symbols
    print("=== PASS 1: default params, all 7 symbols ===")
    default_params = {"lookback": 120, "percentile": 5.0, "stop_atr_mult": 3.0, "tp_atr_mult": 1.5, "size_pct": 10.0}
    for sym in SYMBOLS:
        candles = candles_cache[sym]
        try:
            r = await run_backtest(sym, candles, default_params)
            s = summarize_result(r, f"default-{sym}")
            s["symbol"] = sym; s["params"] = default_params; s["pass"] = "default"
            print(f"  {sym:5} trades={s['trades']:3} ret={s['ret_pct']:+.2f}% WR={s['wr']:.1f}% Sharpe={s['sharpe']:+.2f} maxDD={s['max_dd_pct']:.1f}% PF={s['profit_factor']:.2f}")
            results.append(s)
        except Exception as e:
            print(f"  {sym:5} ERROR: {e}")
            results.append({"symbol": sym, "params": default_params, "pass": "default", "error": str(e)})

    # PASS 2: parameter robustness sweep on validated survivors only
    print("\n=== PASS 2: parameter sweep on Phase 4 survivors (LINK/AVAX/DOGE) ===")
    survivors = ["LINK", "AVAX", "DOGE"]
    sweep_grid = []
    for stop in [2.0, 3.0, 4.0]:
        for tp in [1.0, 1.5, 2.0, 3.0]:
            for pct in [3.0, 5.0, 10.0]:
                sweep_grid.append({
                    "lookback": 120, "percentile": pct,
                    "stop_atr_mult": stop, "tp_atr_mult": tp, "size_pct": 10.0,
                })

    print(f"  {len(sweep_grid)} param combos × {len(survivors)} survivors = {len(sweep_grid)*len(survivors)} cells")
    for sym in survivors:
        candles = candles_cache[sym]
        for params in sweep_grid:
            try:
                r = await run_backtest(sym, candles, params)
                s = summarize_result(r, f"sweep-{sym}-s{params['stop_atr_mult']}-tp{params['tp_atr_mult']}-p{params['percentile']}")
                s["symbol"] = sym; s["params"] = params; s["pass"] = "sweep"
                results.append(s)
            except Exception as e:
                results.append({"symbol": sym, "params": params, "pass": "sweep", "error": str(e)})

    # Find best param combo per survivor
    print("\n=== best parameter combos per survivor ===")
    for sym in survivors:
        sym_runs = [r for r in results if r.get("symbol") == sym and r.get("pass") == "sweep" and "error" not in r and r["trades"] >= 20]
        if not sym_runs:
            print(f"  {sym}: no runs")
            continue
        # rank by sharpe
        sym_runs.sort(key=lambda x: -x["sharpe"])
        top = sym_runs[0]
        p = top["params"]
        print(f"  {sym} best: stop={p['stop_atr_mult']} tp={p['tp_atr_mult']} pct={p['percentile']} -> ret={top['ret_pct']:+.2f}% Sharpe={top['sharpe']:+.2f} trades={top['trades']} maxDD={top['max_dd_pct']:.1f}%")

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")

    # Summary markdown
    lines = []
    lines.append("# Phase 5: capitulation_flush strategy validation")
    lines.append(f"\n**Backtest engine**: production `BacktestEngine` with `PaperTradingEngine`. **Fees**: 5+5 bps. **Equity**: $25k. **Data**: 28mo Hyperliquid 4h.\n")

    lines.append("## Pass 1 — default params (lookback=120 percentile=5 stop=3ATR tp=1.5ATR size=10%)")
    lines.append("\n| symbol | trades | full_ret% | WR% | Sharpe | maxDD% | profit_factor | Phase 4 verdict |")
    lines.append("|---|---|---|---|---|---|---|---|")
    p4_status = {
        "LINK": "✓ all 4 gates", "AVAX": "✓ all 4 gates", "DOGE": "✓ all 4 gates",
        "BTC": "✗ Gate 2 (IS≠OOS)", "SOL": "✗ Gate 2", "ETH": "✗ Gate 1", "ARB": "✗ Gate 1",
    }
    for r in [r for r in results if r.get("pass") == "default" and "error" not in r]:
        lines.append(f"| {r['symbol']} | {r['trades']} | {r['ret_pct']:+.2f} | {r['wr']:.1f} | {r['sharpe']:+.2f} | {r['max_dd_pct']:.1f} | {r['profit_factor']:.2f} | {p4_status.get(r['symbol'], '?')} |")

    lines.append("\n## Pass 2 — parameter sweep on Phase 4 survivors")
    for sym in ["LINK", "AVAX", "DOGE"]:
        sym_runs = [r for r in results if r.get("symbol") == sym and r.get("pass") == "sweep" and "error" not in r and r["trades"] >= 20]
        if not sym_runs:
            continue
        sym_runs.sort(key=lambda x: -x["sharpe"])
        lines.append(f"\n### {sym} — top 10 parameter combos by Sharpe")
        lines.append("| stop | tp | pct | trades | ret% | Sharpe | maxDD% | PF |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in sym_runs[:10]:
            p = r["params"]
            lines.append(f"| {p['stop_atr_mult']:.1f} | {p['tp_atr_mult']:.1f} | {p['percentile']:.1f} | {r['trades']} | {r['ret_pct']:+.2f} | {r['sharpe']:+.2f} | {r['max_dd_pct']:.1f} | {r['profit_factor']:.2f} |")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"wrote {OUT_SUMMARY}")
    print(f"\ntotal: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
