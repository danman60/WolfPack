"""Phase 3: per-symbol × per-strategy × per-timeframe backtest with walk-forward IS/OOS.

Tests all 12 strategies (11 existing + new rsi2_connors) across 7 symbols on
both 1h (7mo data) and 4h (28mo data) candles. Production-realistic 5+5 bps
fee/slippage. Walk-forward 70/30 train/test split with strict acceptance:

  PASS = full_return > 0 AND oos_return > 0 AND oos_sharpe > 0.5 AND max_dd < 20%

Output: phase3_results.json + phase3_summary.md with the survivor matrix.
"""

import asyncio
import json
import sys
import time
import math
from pathlib import Path
from collections import defaultdict
from statistics import mean

INTEL_PATH = Path(__file__).resolve().parents[3] / "intel"
sys.path.insert(0, str(INTEL_PATH))

import httpx
from wolfpack.exchanges.base import Candle
from wolfpack.models.backtest_models import BacktestConfig
from wolfpack.backtest_engine import BacktestEngine
from wolfpack.strategies import STRATEGIES

INTEL_API = "http://159.89.115.95:8000"
SYMBOLS = ["BTC", "ETH", "SOL", "LINK", "AVAX", "ARB", "DOGE"]
STRATEGY_KEYS = list(STRATEGIES.keys())  # 12 strategies
TIMEFRAMES = [
    ("1h", 5000),   # ~7 months 1h
    ("4h", 5000),   # ~28 months 4h
]
IS_FRACTION = 0.70

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase3_results.json"
OUT_SUMMARY = OUT_DIR / "phase3_summary.md"
OUT_CSV = OUT_DIR / "phase3_matrix.csv"


async def fetch_candles(client, symbol: str, interval: str, limit: int) -> list[Candle]:
    r = await client.get(
        f"{INTEL_API}/market/candles",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=120,
    )
    r.raise_for_status()
    return [Candle(**c) for c in r.json()["candles"]]


def compute_oos_metrics(trades, candles_oos_start_ts):
    oos_trades = [t for t in trades if t.entry_time >= candles_oos_start_ts]
    if not oos_trades:
        return {"n": 0, "wins": 0, "wr": 0.0, "pnl_usd": 0.0, "ret_pct": 0.0, "sharpe": 0.0}
    pnls = [t.pnl_pct for t in oos_trades]
    n = len(oos_trades)
    wins = sum(1 for t in oos_trades if t.pnl_usd > 0)
    pnl_usd = sum(t.pnl_usd for t in oos_trades)
    ret_pct = sum(pnls) * 100
    if len(pnls) > 1:
        m = mean(pnls)
        var = sum((p - m) ** 2 for p in pnls) / (len(pnls) - 1)
        sd = math.sqrt(var) if var > 0 else 1e-9
        sharpe = (m / sd) * math.sqrt(252) if sd > 0 else 0.0
    else:
        sharpe = 0.0
    return {
        "n": n, "wins": wins, "wr": wins / n if n else 0.0,
        "pnl_usd": pnl_usd, "ret_pct": ret_pct, "sharpe": sharpe,
    }


async def run_one(symbol: str, strategy: str, candles: list[Candle], interval: str) -> dict:
    if len(candles) < 250:
        return {"error": "too few candles"}
    cfg = BacktestConfig(
        symbol=symbol,
        exchange="hyperliquid",
        interval=interval,
        start_time=candles[0].timestamp,
        end_time=candles[-1].timestamp,
        starting_equity=25000.0,
        commission_bps=5.0,
        slippage_bps=5.0,
        strategy=strategy,
        strategy_params={},
        max_position_pct=25.0,
    )
    try:
        engine = BacktestEngine(cfg)
        result = await engine.run(candles)
        m = result.metrics
        # IS/OOS split at 70%
        oos_split_idx = int(len(candles) * IS_FRACTION)
        oos_start_ts = candles[oos_split_idx].timestamp
        is_trades = [t for t in result.trades if t.entry_time < oos_start_ts]
        oos_trades = [t for t in result.trades if t.entry_time >= oos_start_ts]
        is_pnl = sum(t.pnl_usd for t in is_trades)
        oos_metrics = compute_oos_metrics(result.trades, oos_start_ts)

        # Acceptance criteria
        acceptance = (
            m.total_return_pct > 0
            and oos_metrics["ret_pct"] > 0
            and oos_metrics["sharpe"] > 0.5
            and m.max_drawdown_pct < 20.0
            and m.total_trades >= 10
        )
        return {
            "symbol": symbol, "strategy": strategy, "interval": interval,
            "full": {
                "ret_pct": m.total_return_pct, "sharpe": m.sharpe_ratio,
                "calmar": m.calmar_ratio, "max_dd_pct": m.max_drawdown_pct,
                "wr": m.win_rate * 100, "trades": m.total_trades,
                "expectancy_pct": m.expectancy_pct, "profit_factor": m.profit_factor,
            },
            "is": {"trades": len(is_trades), "pnl_usd": is_pnl},
            "oos": oos_metrics,
            "passes_acceptance": acceptance,
            "duration_s": result.duration_seconds,
        }
    except Exception as e:
        return {"symbol": symbol, "strategy": strategy, "interval": interval, "error": f"{type(e).__name__}: {e}"}


async def main():
    t0 = time.time()
    cells = len(SYMBOLS) * len(STRATEGY_KEYS) * len(TIMEFRAMES)
    print(f"phase 3: {len(SYMBOLS)} symbols × {len(STRATEGY_KEYS)} strategies × {len(TIMEFRAMES)} timeframes = {cells} cells")
    print(f"strategies: {STRATEGY_KEYS}")

    # Fetch all candles up front
    candles_cache: dict = {}
    async with httpx.AsyncClient() as client:
        for tf, limit in TIMEFRAMES:
            for sym in SYMBOLS:
                print(f"fetching {sym} {tf}...")
                try:
                    candles_cache[(sym, tf)] = await fetch_candles(client, sym, tf, limit)
                    print(f"  got {len(candles_cache[(sym, tf)])} candles")
                except Exception as e:
                    print(f"  FAILED: {e}")
                    candles_cache[(sym, tf)] = []
    print(f"\ncandle fetch took {time.time()-t0:.0f}s\n")

    results = []
    cell_no = 0
    for tf, _ in TIMEFRAMES:
        for sym in SYMBOLS:
            candles = candles_cache.get((sym, tf), [])
            if not candles:
                continue
            for strat in STRATEGY_KEYS:
                cell_no += 1
                t1 = time.time()
                r = await run_one(sym, strat, candles, tf)
                elapsed = time.time() - t1
                results.append(r)
                if "error" in r:
                    print(f"  [{cell_no:3}/{cells}] {sym:5} {strat:25} {tf:3} ERROR ({elapsed:.1f}s): {r['error'][:60]}")
                else:
                    flag = "✓" if r["passes_acceptance"] else " "
                    f = r["full"]; o = r["oos"]
                    print(f"  [{cell_no:3}/{cells}] {flag} {sym:5} {strat:25} {tf:3} ret={f['ret_pct']:+7.2f}% trades={f['trades']:4} OOS={o['ret_pct']:+6.2f}% sharpe={o['sharpe']:+.2f} ({elapsed:.1f}s)")

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")

    # Build summary
    successes = [r for r in results if "error" not in r]
    survivors = [r for r in successes if r["passes_acceptance"]]
    survivors.sort(key=lambda r: -r["oos"]["ret_pct"])

    lines = []
    lines.append("# Phase 3: per-symbol × per-strategy × per-timeframe backtest")
    lines.append(f"\n{cells} cells. {len(successes)} succeeded, {len(survivors)} passed acceptance.")
    lines.append(f"\n**Acceptance:** full_return>0 AND oos_return>0 AND oos_sharpe>0.5 AND max_dd<20% AND trades≥10\n")
    lines.append("**Fees/slippage:** 5+5 bps. **Equity:** $25k. **IS/OOS split:** 70/30 walk-forward.\n")

    lines.append("## Survivors (passed acceptance)")
    if survivors:
        lines.append("| sym | strategy | tf | full_ret% | OOS_ret% | OOS_sharpe | OOS_n | full_trades | full_wr% | max_dd% |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in survivors:
            f = r["full"]; o = r["oos"]
            lines.append(f"| {r['symbol']} | {r['strategy']} | {r['interval']} | {f['ret_pct']:+.2f} | {o['ret_pct']:+.2f} | {o['sharpe']:+.2f} | {o['n']} | {f['trades']} | {f['wr']:.1f} | {f['max_dd_pct']:.2f} |")
    else:
        lines.append("\n**No cells passed full acceptance criteria.**\n")

    # Top 25 by OOS return regardless of acceptance
    lines.append("\n## Top 25 by OOS return (regardless of full-period sign)")
    sorted_by_oos = sorted(successes, key=lambda r: -r["oos"]["ret_pct"])
    lines.append("| sym | strategy | tf | full_ret% | OOS_ret% | OOS_sharpe | OOS_n | accept |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in sorted_by_oos[:25]:
        f = r["full"]; o = r["oos"]
        accept = "✓" if r["passes_acceptance"] else ""
        lines.append(f"| {r['symbol']} | {r['strategy']} | {r['interval']} | {f['ret_pct']:+.2f} | {o['ret_pct']:+.2f} | {o['sharpe']:+.2f} | {o['n']} | {accept} |")

    # By strategy averages
    by_strat = defaultdict(list)
    for r in successes:
        by_strat[(r["strategy"], r["interval"])].append(r)
    lines.append("\n## By strategy × timeframe — averages across 7 symbols")
    lines.append("| strategy | tf | avg_full_ret% | avg_OOS_ret% | n_pos_full | n_pos_OOS | n_pass_acceptance |")
    lines.append("|---|---|---|---|---|---|---|")
    rows = []
    for (st, tf), runs in by_strat.items():
        avg_full = sum(r["full"]["ret_pct"] for r in runs) / len(runs)
        avg_oos = sum(r["oos"]["ret_pct"] for r in runs) / len(runs)
        n_pos_full = sum(1 for r in runs if r["full"]["ret_pct"] > 0)
        n_pos_oos = sum(1 for r in runs if r["oos"]["ret_pct"] > 0)
        n_pass = sum(1 for r in runs if r["passes_acceptance"])
        rows.append((st, tf, avg_full, avg_oos, n_pos_full, n_pos_oos, n_pass))
    rows.sort(key=lambda x: -x[3])  # sort by avg OOS return
    for st, tf, af, ao, np_f, np_o, np_a in rows:
        lines.append(f"| {st} | {tf} | {af:+.2f} | {ao:+.2f} | {np_f}/7 | {np_o}/7 | {np_a}/7 |")

    OUT_SUMMARY.write_text("\n".join(lines))

    # CSV for full inspection
    csv_lines = ["symbol,strategy,interval,full_ret_pct,full_sharpe,full_calmar,full_max_dd,full_trades,full_wr,oos_n,oos_ret_pct,oos_sharpe,oos_pnl_usd,passes"]
    for r in successes:
        f = r["full"]; o = r["oos"]
        csv_lines.append(f"{r['symbol']},{r['strategy']},{r['interval']},{f['ret_pct']:.4f},{f['sharpe']:.4f},{f['calmar']:.4f},{f['max_dd_pct']:.4f},{f['trades']},{f['wr']:.2f},{o['n']},{o['ret_pct']:.4f},{o['sharpe']:.4f},{o['pnl_usd']:.2f},{int(r['passes_acceptance'])}")
    OUT_CSV.write_text("\n".join(csv_lines))

    print(f"wrote {OUT_SUMMARY}")
    print(f"wrote {OUT_CSV}")
    print(f"\ntotal time: {time.time()-t0:.0f}s")
    print(f"survivors: {len(survivors)}/{cells}")


if __name__ == "__main__":
    asyncio.run(main())
