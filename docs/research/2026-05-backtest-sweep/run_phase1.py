"""Phase 1: coarse 7×11 backtest sweep over 90 days.

Pulls candles from public /market/candles endpoint, runs BacktestEngine locally
with each (symbol, strategy) pair, writes results JSON + summary markdown.

Usage: python3 run_phase1.py
"""

import asyncio
import json
import sys
import time
import traceback
from pathlib import Path

# Add intel/ to import path
INTEL_PATH = Path(__file__).resolve().parents[3] / "intel"
sys.path.insert(0, str(INTEL_PATH))

import httpx
from wolfpack.exchanges.base import Candle
from wolfpack.models.backtest_models import BacktestConfig
from wolfpack.backtest_engine import BacktestEngine
from wolfpack.strategies import STRATEGIES

INTEL_API = "http://159.89.115.95:8000"
SYMBOLS = ["BTC", "ETH", "SOL", "LINK", "AVAX", "ARB", "DOGE"]
STRATEGY_KEYS = list(STRATEGIES.keys())  # all 11
INTERVAL = "1h"
DAYS = 90
CANDLES_NEEDED = DAYS * 24  # 2160

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase1_results.json"
OUT_SUMMARY = OUT_DIR / "phase1_summary.md"


async def fetch_candles(client: httpx.AsyncClient, symbol: str) -> list[Candle]:
    r = await client.get(
        f"{INTEL_API}/market/candles",
        params={"symbol": symbol, "interval": INTERVAL, "limit": CANDLES_NEEDED},
        timeout=60,
    )
    r.raise_for_status()
    raw = r.json()["candles"]
    return [Candle(**c) for c in raw]


async def run_one(symbol: str, strategy: str, candles: list[Candle]) -> dict:
    if len(candles) < 100:
        return {"error": f"only {len(candles)} candles"}
    cfg = BacktestConfig(
        symbol=symbol,
        exchange="hyperliquid",
        interval=INTERVAL,
        start_time=candles[0].timestamp,
        end_time=candles[-1].timestamp,
        starting_equity=25000.0,
        commission_bps=5.0,
        slippage_bps=5.0,
        strategy=strategy,
        strategy_params={},
        max_position_pct=25.0,
        stop_loss_pct=None,
        take_profit_pct=None,
    )
    try:
        engine = BacktestEngine(cfg)
        result = await engine.run(candles)
        m = result.metrics
        # OOS slice: last 30 days (last 720 candles), reuse strategy from full result trades
        oos_cutoff_ts = candles[-1].timestamp - 30 * 24 * 3600 * 1000
        oos_trades = [t for t in result.trades if t.exit_time >= oos_cutoff_ts]
        oos_pnl = sum(t.pnl_usd for t in oos_trades)
        oos_wins = sum(1 for t in oos_trades if t.pnl_usd > 0)
        return {
            "symbol": symbol,
            "strategy": strategy,
            "full": {
                "total_return_pct": m.total_return_pct,
                "sharpe": m.sharpe_ratio,
                "calmar": m.calmar_ratio,
                "max_dd_pct": m.max_drawdown_pct,
                "win_rate": m.win_rate,
                "trades": m.total_trades,
                "expectancy_pct": m.expectancy_pct,
                "profit_factor": m.profit_factor,
                "avg_holding_bars": m.avg_holding_bars,
            },
            "oos_30d": {
                "trades": len(oos_trades),
                "wins": oos_wins,
                "win_rate": (oos_wins / len(oos_trades)) if oos_trades else 0.0,
                "pnl_usd": oos_pnl,
            },
            "duration_seconds": result.duration_seconds,
        }
    except Exception as e:
        return {
            "symbol": symbol,
            "strategy": strategy,
            "error": f"{type(e).__name__}: {e}",
            "trace": traceback.format_exc(),
        }


async def main():
    print(f"phase 1 sweep: {len(SYMBOLS)} symbols × {len(STRATEGY_KEYS)} strategies = {len(SYMBOLS)*len(STRATEGY_KEYS)} runs")
    print(f"strategies: {STRATEGY_KEYS}")
    t0 = time.time()
    candles_by_sym = {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            print(f"fetching {sym} candles...")
            try:
                candles_by_sym[sym] = await fetch_candles(client, sym)
                print(f"  got {len(candles_by_sym[sym])} candles, {sym}")
            except Exception as e:
                print(f"  FAILED: {e}")
                candles_by_sym[sym] = []
    print(f"candles fetched in {time.time()-t0:.1f}s")

    results = []
    for sym in SYMBOLS:
        candles = candles_by_sym[sym]
        if not candles:
            for st in STRATEGY_KEYS:
                results.append({"symbol": sym, "strategy": st, "error": "no candles"})
            continue
        for st in STRATEGY_KEYS:
            t1 = time.time()
            r = await run_one(sym, st, candles)
            elapsed = time.time() - t1
            if "error" in r:
                print(f"  {sym:5} {st:25} ERROR ({elapsed:.1f}s): {r['error'][:80]}")
            else:
                m = r["full"]
                print(f"  {sym:5} {st:25} ret={m['total_return_pct']:+7.2f}% trades={m['trades']:3} wr={m['win_rate']*100:5.1f}% calmar={m['calmar']:5.2f} ({elapsed:.1f}s)")
            results.append(r)

    # Persist raw
    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")

    # Build markdown summary
    successes = [r for r in results if "error" not in r]
    successes.sort(key=lambda r: -r["full"]["total_return_pct"])
    failures = [r for r in results if "error" in r]

    lines = []
    lines.append("# Phase 1 Backtest Sweep — 90d, 1h candles")
    lines.append(f"\nRan {len(results)} cells ({len(successes)} succeeded, {len(failures)} failed) in {time.time()-t0:.0f}s.\n")
    lines.append("## Top 20 by full-period total return")
    lines.append("")
    lines.append("| sym | strategy | trades | WR% | full_ret% | calmar | max_dd% | OOS_trades | OOS_pnl$ |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in successes[:20]:
        m = r["full"]
        o = r["oos_30d"]
        lines.append(f"| {r['symbol']} | {r['strategy']} | {m['trades']} | {m['win_rate']*100:.1f} | {m['total_return_pct']:+.2f} | {m['calmar']:.2f} | {m['max_dd_pct']:.2f} | {o['trades']} | {o['pnl_usd']:+.2f} |")

    lines.append("\n## Bottom 20 (worst) by full-period total return")
    lines.append("")
    lines.append("| sym | strategy | trades | WR% | full_ret% | calmar | max_dd% |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in successes[-20:]:
        m = r["full"]
        lines.append(f"| {r['symbol']} | {r['strategy']} | {m['trades']} | {m['win_rate']*100:.1f} | {m['total_return_pct']:+.2f} | {m['calmar']:.2f} | {m['max_dd_pct']:.2f} |")

    # Per-strategy aggregate
    by_strat = {}
    for r in successes:
        s = r["strategy"]
        by_strat.setdefault(s, []).append(r)
    lines.append("\n## By strategy — average across 7 symbols")
    lines.append("")
    lines.append("| strategy | avg_ret% | avg_calmar | total_trades | avg_WR% | n_pos_symbols | avg_OOS_pnl$ |")
    lines.append("|---|---|---|---|---|---|---|")
    strat_summary = []
    for s, runs in by_strat.items():
        avg_ret = sum(r["full"]["total_return_pct"] for r in runs) / len(runs)
        avg_cal = sum(r["full"]["calmar"] for r in runs) / len(runs)
        total_tr = sum(r["full"]["trades"] for r in runs)
        avg_wr = sum(r["full"]["win_rate"] for r in runs) / len(runs) * 100
        n_pos = sum(1 for r in runs if r["full"]["total_return_pct"] > 0)
        avg_oos = sum(r["oos_30d"]["pnl_usd"] for r in runs) / len(runs)
        strat_summary.append((s, avg_ret, avg_cal, total_tr, avg_wr, n_pos, avg_oos))
    strat_summary.sort(key=lambda x: -x[1])
    for s, avg_ret, avg_cal, total_tr, avg_wr, n_pos, avg_oos in strat_summary:
        lines.append(f"| {s} | {avg_ret:+.2f} | {avg_cal:.2f} | {total_tr} | {avg_wr:.1f} | {n_pos}/7 | {avg_oos:+.2f} |")

    # Per-symbol aggregate
    by_sym = {}
    for r in successes:
        by_sym.setdefault(r["symbol"], []).append(r)
    lines.append("\n## By symbol — average across 11 strategies")
    lines.append("")
    lines.append("| symbol | avg_ret% | best_strategy | best_ret% | n_pos_strategies |")
    lines.append("|---|---|---|---|---|")
    sym_summary = []
    for sym, runs in by_sym.items():
        avg_ret = sum(r["full"]["total_return_pct"] for r in runs) / len(runs)
        best = max(runs, key=lambda r: r["full"]["total_return_pct"])
        n_pos = sum(1 for r in runs if r["full"]["total_return_pct"] > 0)
        sym_summary.append((sym, avg_ret, best["strategy"], best["full"]["total_return_pct"], n_pos))
    sym_summary.sort(key=lambda x: -x[1])
    for sym, avg_ret, best_st, best_ret, n_pos in sym_summary:
        lines.append(f"| {sym} | {avg_ret:+.2f} | {best_st} | {best_ret:+.2f} | {n_pos}/11 |")

    if failures:
        lines.append("\n## Failures")
        lines.append("")
        for f in failures[:20]:
            err = f.get('error', '?')[:120]
            lines.append(f"- {f.get('symbol','?')} / {f.get('strategy','?')}: {err}")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"wrote {OUT_SUMMARY}")
    print(f"\ntotal time: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
