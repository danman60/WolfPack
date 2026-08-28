"""Phase 2: regime-conditioned mean_reversion analysis on each symbol.

For each of 7 symbols:
  1. Run baseline mean_reversion (already done — we just need entry features per trade)
  2. Compute entry-bar features: ATR percentile, EMA200 trend, EMA20 slope, BB width %ile, RSI, Hurst
  3. Bucket trades by feature, compute per-bucket P&L
  4. Identify best-bin regime filter
  5. Re-run with regime filter applied, walk-forward IS/OOS split (60/30)

Goal: answer "is there a regime where mean_reversion is profitable on any symbol?"
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

INTEL_API = "http://159.89.115.95:8000"
SYMBOLS = ["BTC", "ETH", "SOL", "LINK", "AVAX", "ARB", "DOGE"]
INTERVAL = "1h"
CANDLES_NEEDED = 2160

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase2_regime_results.json"
OUT_SUMMARY = OUT_DIR / "phase2_regime_summary.md"


# ---------- feature engineering ----------

def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def atr_series(candles: list[Candle], period: int = 14) -> list[float]:
    trs = []
    for i, c in enumerate(candles):
        if i == 0:
            trs.append(c.high - c.low)
        else:
            prev = candles[i - 1].close
            tr = max(c.high - c.low, abs(c.high - prev), abs(c.low - prev))
            trs.append(tr)
    out = []
    for i in range(len(trs)):
        if i < period:
            out.append(sum(trs[: i + 1]) / (i + 1))
        else:
            out.append(sum(trs[i - period + 1 : i + 1]) / period)
    return out


def rsi_series(closes: list[float], period: int = 14) -> list[float]:
    out = [50.0] * len(closes)
    if len(closes) < period + 1:
        return out
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    for i in range(period, len(closes)):
        avg_g = mean(gains[i - period : i])
        avg_l = mean(losses[i - period : i])
        if avg_l == 0:
            out[i] = 100.0
        else:
            rs = avg_g / avg_l
            out[i] = 100 - 100 / (1 + rs)
    return out


def bb_width_series(closes: list[float], period: int = 20) -> list[float]:
    out = [0.0] * len(closes)
    for i in range(period, len(closes)):
        window = closes[i - period : i]
        m = mean(window)
        var = sum((x - m) ** 2 for x in window) / period
        sd = math.sqrt(var)
        out[i] = (4 * sd) / m if m > 0 else 0
    return out


def hurst(closes: list[float]) -> float:
    """Simplified Hurst exponent via R/S analysis. <0.5 = mean reverting, >0.5 = trending."""
    n = len(closes)
    if n < 20:
        return 0.5
    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, n) if closes[i - 1] > 0]
    if len(log_returns) < 10:
        return 0.5
    m = mean(log_returns)
    dev = [r - m for r in log_returns]
    z = [sum(dev[: i + 1]) for i in range(len(dev))]
    R = max(z) - min(z)
    var = sum(d ** 2 for d in dev) / len(dev)
    S = math.sqrt(var) if var > 0 else 1e-9
    if R == 0 or S == 0:
        return 0.5
    return math.log(R / S) / math.log(n)


def percentile_bin(value: float, all_values: list[float]) -> str:
    if not all_values:
        return "mid"
    sorted_v = sorted(all_values)
    n = len(sorted_v)
    p33 = sorted_v[n // 3]
    p66 = sorted_v[2 * n // 3]
    if value <= p33:
        return "low"
    if value <= p66:
        return "mid"
    return "high"


# ---------- main ----------

async def fetch_candles(client: httpx.AsyncClient, symbol: str) -> list[Candle]:
    r = await client.get(
        f"{INTEL_API}/market/candles",
        params={"symbol": symbol, "interval": INTERVAL, "limit": CANDLES_NEEDED},
        timeout=60,
    )
    r.raise_for_status()
    return [Candle(**c) for c in r.json()["candles"]]


async def baseline_run(symbol: str, candles: list[Candle]):
    cfg = BacktestConfig(
        symbol=symbol, exchange="hyperliquid", interval=INTERVAL,
        start_time=candles[0].timestamp, end_time=candles[-1].timestamp,
        starting_equity=25000.0, commission_bps=5.0, slippage_bps=5.0,
        strategy="mean_reversion", strategy_params={}, max_position_pct=25.0,
    )
    engine = BacktestEngine(cfg)
    return await engine.run(candles)


def decompose_trades_by_regime(result, candles: list[Candle]) -> dict:
    """For each trade, compute entry-bar features, bucket trades by regime."""
    closes = [c.close for c in candles]
    atr = atr_series(candles, 14)
    rsi = rsi_series(closes, 14)
    bbw = bb_width_series(closes, 20)
    e20 = ema(closes, 20)
    e200 = ema(closes, 200)
    # per-trade entry features
    ts_to_idx = {c.timestamp: i for i, c in enumerate(candles)}

    # Distributions for percentile binning
    atr_dist = atr[200:]  # skip warmup
    bbw_dist = [b for b in bbw if b > 0]

    by_regime = defaultdict(lambda: {"n": 0, "wins": 0, "pnl": 0.0, "longs": 0, "shorts": 0})
    by_feature = defaultdict(lambda: defaultdict(lambda: {"n": 0, "pnl": 0.0}))

    for tr in result.trades:
        idx = ts_to_idx.get(tr.entry_time)
        if idx is None or idx < 200:
            continue
        atr_pct = percentile_bin(atr[idx], atr_dist)
        bbw_pct = percentile_bin(bbw[idx], bbw_dist) if bbw[idx] > 0 else "mid"
        # trend filter
        trend = "above_ema200" if closes[idx] > e200[idx] else "below_ema200"
        # ema20 slope (vs 5 bars ago)
        slope_pos = "rising" if idx >= 5 and e20[idx] > e20[idx - 5] else "falling"
        # rsi bucket
        r = rsi[idx]
        if r < 30: rsi_bucket = "oversold"
        elif r < 70: rsi_bucket = "neutral"
        else: rsi_bucket = "overbought"
        # hurst over 50 bars before entry
        h = hurst(closes[max(0, idx - 50): idx]) if idx >= 50 else 0.5
        hurst_bucket = "mean_rev" if h < 0.5 else "trending"

        # Combined regime key (3 most discriminating)
        regime = f"{trend}|atr_{atr_pct}|trend_{slope_pos}"
        s = by_regime[regime]
        s["n"] += 1
        s["pnl"] += tr.pnl_usd
        if tr.pnl_usd > 0: s["wins"] += 1
        if tr.direction == "long": s["longs"] += 1
        else: s["shorts"] += 1

        # Single-feature decomposition
        for fname, fval in [
            ("atr_pct", atr_pct), ("trend_v_ema200", trend),
            ("ema20_slope", slope_pos), ("rsi", rsi_bucket),
            ("bbw_pct", bbw_pct), ("hurst", hurst_bucket),
        ]:
            by_feature[fname][fval]["n"] += 1
            by_feature[fname][fval]["pnl"] += tr.pnl_usd

    return {
        "by_regime": dict(by_regime),
        "by_feature": {k: dict(v) for k, v in by_feature.items()},
    }


async def main():
    t0 = time.time()
    print("Phase 2: regime decomposition on mean_reversion across 7 symbols")
    candles_by_sym = {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            print(f"fetching {sym}...")
            candles_by_sym[sym] = await fetch_candles(client, sym)

    all_results = {}
    for sym in SYMBOLS:
        candles = candles_by_sym[sym]
        print(f"\n=== {sym} ===")
        baseline = await baseline_run(sym, candles)
        m = baseline.metrics
        print(f"baseline: {m.total_trades} trades, ret={m.total_return_pct:+.2f}%, WR={m.win_rate*100:.1f}%")
        decomp = decompose_trades_by_regime(baseline, candles)

        # Top by-feature winners (descending P&L)
        feature_summary = {}
        for fname, buckets in decomp["by_feature"].items():
            sorted_bins = sorted(buckets.items(), key=lambda x: -x[1]["pnl"])
            feature_summary[fname] = sorted_bins
            top = sorted_bins[0]
            print(f"  best {fname}: {top[0]} → n={top[1]['n']} pnl=${top[1]['pnl']:+.2f}")

        # Top combined regimes
        sorted_regimes = sorted(decomp["by_regime"].items(), key=lambda x: -x[1]["pnl"])
        print(f"  top combined regime: {sorted_regimes[0][0]}")
        print(f"    n={sorted_regimes[0][1]['n']} wins={sorted_regimes[0][1]['wins']} pnl=${sorted_regimes[0][1]['pnl']:+.2f}")

        # Walk-forward: split 60/30, compute per-regime IS vs OOS
        cutoff_ts = candles[0].timestamp + 60 * 24 * 3600 * 1000
        is_trades = [t for t in baseline.trades if t.entry_time < cutoff_ts]
        oos_trades = [t for t in baseline.trades if t.entry_time >= cutoff_ts]
        is_pnl = sum(t.pnl_usd for t in is_trades)
        oos_pnl = sum(t.pnl_usd for t in oos_trades)
        print(f"  IS (60d): n={len(is_trades)} pnl=${is_pnl:+.2f}")
        print(f"  OOS (30d): n={len(oos_trades)} pnl=${oos_pnl:+.2f}")

        all_results[sym] = {
            "baseline": {
                "trades": m.total_trades,
                "ret_pct": m.total_return_pct,
                "wr": m.win_rate * 100,
                "calmar": m.calmar_ratio,
                "max_dd": m.max_drawdown_pct,
            },
            "by_feature": feature_summary,
            "top_regimes": sorted_regimes[:5],
            "is_oos": {"is_n": len(is_trades), "is_pnl": is_pnl, "oos_n": len(oos_trades), "oos_pnl": oos_pnl},
        }

    OUT_RESULTS.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")

    # Build summary
    lines = []
    lines.append("# Phase 2: Regime Decomposition on mean_reversion")
    lines.append(f"\n90 days × 7 symbols × 1 strategy. Goal: find regime conditions where mean_reversion has positive expectancy.\n")

    lines.append("## Per-feature P&L decomposition")
    for sym, data in all_results.items():
        lines.append(f"\n### {sym} (baseline: {data['baseline']['trades']} trades, ret {data['baseline']['ret_pct']:+.2f}%, IS-60d ${data['is_oos']['is_pnl']:+.2f} / OOS-30d ${data['is_oos']['oos_pnl']:+.2f})")
        for fname, bins in data["by_feature"].items():
            lines.append(f"\n**{fname}:**")
            lines.append("| bucket | n | pnl$ | per-trade$ |")
            lines.append("|---|---|---|---|")
            for bucket, s in bins:
                avg = s["pnl"] / s["n"] if s["n"] else 0
                lines.append(f"| {bucket} | {s['n']} | {s['pnl']:+.2f} | {avg:+.2f} |")

    lines.append("\n## Top combined regimes per symbol")
    for sym, data in all_results.items():
        lines.append(f"\n### {sym}")
        lines.append("| regime | n | wins | pnl$ | longs | shorts |")
        lines.append("|---|---|---|---|---|---|")
        for regime, s in data["top_regimes"]:
            lines.append(f"| {regime} | {s['n']} | {s['wins']} | {s['pnl']:+.2f} | {s['longs']} | {s['shorts']} |")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"wrote {OUT_SUMMARY}")
    print(f"total time: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
