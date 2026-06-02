"""GEX-proxy kill-test spike.

We cannot get historical crypto options OI to compute true GEX. This tests a
realized-volatility PROXY for the GEX regime idea:

  "positive-gamma proxy" = LOW or FALLING realized vol  -> expect MEAN-REVERSION edge
  "negative-gamma proxy" = HIGH or RISING realized vol   -> expect TREND/MOMENTUM edge

Question: does the vol-regime label actually separate MR-vs-trend behavior?
Two independent measurements per regime:
  (a) model-free  : lag-1 autocorr of forward 1h returns within each regime bucket
  (b) strategy-cond: split mean_reversion + vol_breakout trades by entry-bar regime,
                     compute per-regime win rate / total P&L / expectancy.

Verdict PASS if MR-regime shows more-negative autocorr AND mean_reversion has higher
expectancy in MR-regime than trend-regime AND momentum is the reverse. Numbers drive it.
"""

import asyncio
import json
import sys
import time
import math
from pathlib import Path
from collections import defaultdict
from statistics import mean, pstdev

INTEL_PATH = Path(__file__).resolve().parents[3] / "intel"
sys.path.insert(0, str(INTEL_PATH))

import httpx
from wolfpack.exchanges.base import Candle
from wolfpack.models.backtest_models import BacktestConfig
from wolfpack.backtest_engine import BacktestEngine

INTEL_API = "http://159.89.115.95:8000"
SYMBOLS = ["BTC", "ETH", "SOL"]
INTERVAL = "1h"
CANDLES_NEEDED = 2160

# Vol-regime proxy params
RV_WINDOW = 24       # rolling std of log returns over 24 bars (1 day)
TREND_WINDOW = 168   # 1-week mean vol baseline for rising/falling
WARMUP = TREND_WINDOW + RV_WINDOW  # skip bars before this index

MR_STRATEGY = "mean_reversion"
# vol_breakout fires only 1-2x over 90d on 1h (too thin to bucket). range_breakout is a
# true breakout/momentum strategy with a usable per-regime sample (~68 trades on BTC).
MOM_STRATEGY = "range_breakout"

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "proxy_results.json"
OUT_SUMMARY = OUT_DIR / "proxy_summary.md"


# ---------- vol regime engineering ----------

def log_returns(closes: list[float]) -> list[float]:
    """log return at bar i = ln(close[i]/close[i-1]); index 0 = 0.0 (no prior)."""
    out = [0.0]
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            out.append(math.log(closes[i] / closes[i - 1]))
        else:
            out.append(0.0)
    return out


def realized_vol_series(lr: list[float], window: int) -> list[float]:
    """Rolling population std of log returns over `window` bars. NaN(=None) during warmup."""
    out: list[float | None] = [None] * len(lr)
    for i in range(window, len(lr)):
        w = lr[i - window + 1 : i + 1]
        out[i] = pstdev(w)
    return out


def regime_labels(closes: list[float]) -> tuple[list[str | None], list[float | None]]:
    """Per-bar regime label using vol LEVEL (high/low vs median) and DIRECTION (rising/falling).

    Returns (labels, rv) where label in {"mr","trend",None}.
      mr-regime    = positive-gamma proxy = low-level OR falling vol
      trend-regime = negative-gamma proxy = high-level OR rising vol
    Combined rule: count how many of {high-level, rising} are true.
      0 true  -> mr     (low & falling)
      2 true  -> trend  (high & rising)
      1 true  -> tie-break by LEVEL (level dominates: high->trend, low->mr)
    """
    lr = log_returns(closes)
    rv = realized_vol_series(lr, RV_WINDOW)
    # median vol level computed over the valid (post-warmup) region only
    valid_rv = [v for i, v in enumerate(rv) if v is not None and i >= WARMUP]
    median_rv = sorted(valid_rv)[len(valid_rv) // 2] if valid_rv else 0.0

    labels: list[str | None] = [None] * len(closes)
    for i in range(len(closes)):
        if i < WARMUP or rv[i] is None:
            continue
        # direction: current 24h vol vs prior 1-week (168 bar) mean vol
        prior = [v for v in rv[i - TREND_WINDOW : i] if v is not None]
        if not prior:
            continue
        prior_mean = mean(prior)
        rising = rv[i] > prior_mean
        high_level = rv[i] > median_rv
        score = int(high_level) + int(rising)
        if score == 0:
            labels[i] = "mr"
        elif score == 2:
            labels[i] = "trend"
        else:
            labels[i] = "trend" if high_level else "mr"
    return labels, rv


def autocorr_by_regime(closes: list[float], labels: list[str | None]) -> dict:
    """Model-free lag-1 autocorrelation of FORWARD 1h returns, bucketed by regime label.

    For each bar i with a label, we look at the pair (fwd_ret[i], fwd_ret[i+1]) where
    fwd_ret[i] = ln(close[i+1]/close[i]). Negative autocorr => mean-reverting (a move
    tends to reverse next bar). Positive => trending (move persists). We compute the
    Pearson correlation of consecutive forward returns within each bucket.
    """
    lr = log_returns(closes)  # lr[i] = return INTO bar i (ln close[i]/close[i-1])
    # forward return at bar i = lr[i+1]
    n = len(closes)
    buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for i in range(WARMUP, n - 2):
        lab = labels[i]
        if lab is None:
            continue
        x = lr[i + 1]      # forward return at i
        y = lr[i + 2]      # forward return at i+1
        buckets[lab].append((x, y))

    out = {}
    for lab, pairs in buckets.items():
        if len(pairs) < 30:
            out[lab] = {"n": len(pairs), "autocorr": None}
            continue
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        mx, my = mean(xs), mean(ys)
        cov = sum((a - mx) * (b - my) for a, b in pairs) / len(pairs)
        sx = pstdev(xs)
        sy = pstdev(ys)
        ac = cov / (sx * sy) if sx > 0 and sy > 0 else None
        out[lab] = {"n": len(pairs), "autocorr": ac}
    return out


# ---------- harness ----------

async def fetch_candles(client: httpx.AsyncClient, symbol: str) -> list[Candle]:
    r = await client.get(
        f"{INTEL_API}/market/candles",
        params={"symbol": symbol, "interval": INTERVAL, "limit": CANDLES_NEEDED},
        timeout=60,
    )
    r.raise_for_status()
    return [Candle(**c) for c in r.json()["candles"]]


async def run_strategy(symbol: str, strategy: str, candles: list[Candle]):
    cfg = BacktestConfig(
        symbol=symbol, exchange="hyperliquid", interval=INTERVAL,
        start_time=candles[0].timestamp, end_time=candles[-1].timestamp,
        starting_equity=25000.0, commission_bps=5.0, slippage_bps=5.0,
        strategy=strategy, strategy_params={}, max_position_pct=25.0,
    )
    engine = BacktestEngine(cfg)
    return await engine.run(candles)


def trades_by_regime(result, candles: list[Candle], labels: list[str | None]) -> dict:
    """Split a strategy's trades by entry-bar regime label; per-regime WR, P&L, expectancy."""
    ts_to_idx = {c.timestamp: i for i, c in enumerate(candles)}
    by = defaultdict(lambda: {"n": 0, "wins": 0, "pnl": 0.0})
    unlabeled = 0
    for tr in result.trades:
        idx = ts_to_idx.get(tr.entry_time)
        if idx is None:
            unlabeled += 1
            continue
        lab = labels[idx]
        if lab is None:
            unlabeled += 1
            continue
        s = by[lab]
        s["n"] += 1
        s["pnl"] += tr.pnl_usd
        if tr.pnl_usd > 0:
            s["wins"] += 1
    out = {}
    for lab, s in by.items():
        out[lab] = {
            "n": s["n"],
            "wins": s["wins"],
            "win_rate": (s["wins"] / s["n"]) if s["n"] else 0.0,
            "total_pnl": s["pnl"],
            "expectancy": (s["pnl"] / s["n"]) if s["n"] else 0.0,
        }
    out["_unlabeled_trades"] = unlabeled
    return out


async def main():
    t0 = time.time()
    print("GEX-proxy kill-test spike: BTC/ETH/SOL, 1h, vol-regime proxy")
    candles_by_sym = {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            print(f"fetching {sym}...")
            candles_by_sym[sym] = await fetch_candles(client, sym)
            print(f"  {sym}: {len(candles_by_sym[sym])} candles")

    results = {"params": {
        "symbols": SYMBOLS, "interval": INTERVAL, "candles_requested": CANDLES_NEEDED,
        "rv_window": RV_WINDOW, "trend_window": TREND_WINDOW, "warmup": WARMUP,
        "mr_strategy": MR_STRATEGY, "mom_strategy": MOM_STRATEGY,
    }, "per_symbol": {}}

    for sym in SYMBOLS:
        candles = candles_by_sym[sym]
        closes = [c.close for c in candles]
        labels, rv = regime_labels(closes)
        nlab = {"mr": labels.count("mr"), "trend": labels.count("trend"),
                "none": sum(1 for l in labels if l is None)}
        print(f"\n=== {sym} === bars: mr={nlab['mr']} trend={nlab['trend']} none={nlab['none']}")

        # (a) model-free autocorr
        ac = autocorr_by_regime(closes, labels)
        print(f"  autocorr mr={ac.get('mr',{}).get('autocorr')} trend={ac.get('trend',{}).get('autocorr')}")

        # (b) strategy-conditioned
        mr_res = await run_strategy(sym, MR_STRATEGY, candles)
        mom_res = await run_strategy(sym, MOM_STRATEGY, candles)
        mr_split = trades_by_regime(mr_res, candles, labels)
        mom_split = trades_by_regime(mom_res, candles, labels)
        print(f"  {MR_STRATEGY}: {mr_res.metrics.total_trades} trades "
              f"(mr_exp={mr_split.get('mr',{}).get('expectancy')} trend_exp={mr_split.get('trend',{}).get('expectancy')})")
        print(f"  {MOM_STRATEGY}: {mom_res.metrics.total_trades} trades "
              f"(mr_exp={mom_split.get('mr',{}).get('expectancy')} trend_exp={mom_split.get('trend',{}).get('expectancy')})")

        results["per_symbol"][sym] = {
            "regime_bar_counts": nlab,
            "autocorr": ac,
            "mr_strategy": {
                "total_trades": mr_res.metrics.total_trades,
                "total_return_pct": mr_res.metrics.total_return_pct,
                "by_regime": mr_split,
            },
            "mom_strategy": {
                "total_trades": mom_res.metrics.total_trades,
                "total_return_pct": mom_res.metrics.total_return_pct,
                "by_regime": mom_split,
            },
        }

    # ---------- verdict ----------
    # Aggregate effect sizes across symbols.
    ac_gaps, mr_exp_gaps, mom_exp_gaps = [], [], []
    for sym, d in results["per_symbol"].items():
        ac = d["autocorr"]
        a_mr = ac.get("mr", {}).get("autocorr")
        a_tr = ac.get("trend", {}).get("autocorr")
        if a_mr is not None and a_tr is not None:
            # expect mr more negative than trend -> gap = a_tr - a_mr (positive = expected direction)
            ac_gaps.append(a_tr - a_mr)
        mr = d["mr_strategy"]["by_regime"]
        if "mr" in mr and "trend" in mr and mr["mr"]["n"] >= 5 and mr["trend"]["n"] >= 5:
            # expect mr_strategy better in mr-regime -> gap = mr_exp - trend_exp (positive = expected)
            mr_exp_gaps.append(mr["mr"]["expectancy"] - mr["trend"]["expectancy"])
        mom = d["mom_strategy"]["by_regime"]
        if "mr" in mom and "trend" in mom and mom["mr"]["n"] >= 5 and mom["trend"]["n"] >= 5:
            # expect momentum better in trend-regime -> gap = trend_exp - mr_exp (positive = expected)
            mom_exp_gaps.append(mom["trend"]["expectancy"] - mom["mr"]["expectancy"])

    avg_ac_gap = mean(ac_gaps) if ac_gaps else None
    avg_mr_gap = mean(mr_exp_gaps) if mr_exp_gaps else None
    avg_mom_gap = mean(mom_exp_gaps) if mom_exp_gaps else None

    # Verdict rule
    AC_THRESH = 0.02      # meaningful autocorr separation
    EXP_THRESH = 0.0      # expectancy gap must point the right way
    autocorr_ok = avg_ac_gap is not None and avg_ac_gap > AC_THRESH
    mr_ok = avg_mr_gap is not None and avg_mr_gap > EXP_THRESH
    mom_ok = avg_mom_gap is not None and avg_mom_gap > EXP_THRESH

    if autocorr_ok and mr_ok and mom_ok:
        verdict = "PASS"
    elif (avg_ac_gap is None) or (avg_mr_gap is None) or (avg_mom_gap is None):
        verdict = "INCONCLUSIVE"
    elif autocorr_ok or mr_ok or mom_ok:
        # partial signal: not all three agree
        verdict = "INCONCLUSIVE"
    else:
        verdict = "FAIL"

    results["verdict"] = {
        "verdict": verdict,
        "avg_autocorr_gap_trend_minus_mr": avg_ac_gap,
        "avg_mr_strategy_expectancy_gap_mr_minus_trend": avg_mr_gap,
        "avg_mom_strategy_expectancy_gap_trend_minus_mr": avg_mom_gap,
        "thresholds": {"autocorr_gap": AC_THRESH, "expectancy_gap": EXP_THRESH},
        "checks": {"autocorr_separation": autocorr_ok, "mr_strategy_direction": mr_ok,
                   "mom_strategy_direction": mom_ok},
        "n_symbols_autocorr": len(ac_gaps),
        "n_symbols_mr": len(mr_exp_gaps),
        "n_symbols_mom": len(mom_exp_gaps),
    }

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")

    # ---------- markdown summary ----------
    L = []
    L.append("# GEX-Proxy Kill-Test Spike")
    L.append("")
    L.append(f"Vol-regime proxy for GEX. {len(SYMBOLS)} symbols x {INTERVAL} candles "
             f"(requested {CANDLES_NEEDED}). RV window {RV_WINDOW}b, trend baseline {TREND_WINDOW}b, "
             f"warmup {WARMUP}b.")
    L.append("")
    L.append("Proxy: **mr-regime** = positive-gamma proxy = low/falling realized vol "
             "(expect mean-reversion). **trend-regime** = negative-gamma proxy = high/rising vol "
             "(expect momentum).")
    L.append("")

    L.append("## (a) Model-free: lag-1 autocorr of forward 1h returns by regime")
    L.append("Negative autocorr = mean-reverting; positive = trending. "
             "Proxy works if mr-regime autocorr is *more negative* than trend-regime.")
    L.append("")
    L.append("| symbol | mr-regime autocorr (n) | trend-regime autocorr (n) | gap (trend - mr) |")
    L.append("|---|---|---|---|")
    for sym, d in results["per_symbol"].items():
        ac = d["autocorr"]
        amr = ac.get("mr", {})
        atr = ac.get("trend", {})
        a_mr = amr.get("autocorr")
        a_tr = atr.get("autocorr")
        gap = (a_tr - a_mr) if (a_mr is not None and a_tr is not None) else None
        def fmt(v): return f"{v:+.4f}" if isinstance(v, (int, float)) else "n/a"
        L.append(f"| {sym} | {fmt(a_mr)} ({amr.get('n','-')}) | {fmt(a_tr)} ({atr.get('n','-')}) | {fmt(gap)} |")
    L.append("")

    L.append("## (b) Strategy-conditioned: per-regime expectancy ($/trade)")
    L.append("")
    for stratkey, stratname in [("mr_strategy", MR_STRATEGY), ("mom_strategy", MOM_STRATEGY)]:
        L.append(f"### {stratname}")
        L.append("| symbol | mr-regime n/WR/exp$ | trend-regime n/WR/exp$ |")
        L.append("|---|---|---|")
        for sym, d in results["per_symbol"].items():
            br = d[stratkey]["by_regime"]
            def cell(lab):
                s = br.get(lab)
                if not s:
                    return "0 / - / -"
                return f"{s['n']} / {s['win_rate']*100:.0f}% / {s['expectancy']:+.2f}"
            L.append(f"| {sym} | {cell('mr')} | {cell('trend')} |")
        L.append("")

    v = results["verdict"]
    L.append("## VERDICT")
    L.append("")
    L.append(f"### {v['verdict']}")
    L.append("")
    L.append("Effect sizes (averaged across symbols, positive = proxy works as hypothesized):")
    L.append("")
    def fmtg(x): return f"{x:+.5f}" if isinstance(x, (int, float)) else "n/a"
    L.append(f"- Autocorr gap (trend - mr), want > {AC_THRESH}: "
             f"**{fmtg(v['avg_autocorr_gap_trend_minus_mr'])}** "
             f"(n={v['n_symbols_autocorr']}) -> {'OK' if v['checks']['autocorr_separation'] else 'NO'}")
    L.append(f"- {MR_STRATEGY} expectancy gap (mr - trend), want > {EXP_THRESH}: "
             f"**{fmtg(v['avg_mr_strategy_expectancy_gap_mr_minus_trend'])}** "
             f"(n={v['n_symbols_mr']}) -> {'OK' if v['checks']['mr_strategy_direction'] else 'NO'}")
    L.append(f"- {MOM_STRATEGY} expectancy gap (trend - mr), want > {EXP_THRESH}: "
             f"**{fmtg(v['avg_mom_strategy_expectancy_gap_trend_minus_mr'])}** "
             f"(n={v['n_symbols_mom']}) -> {'OK' if v['checks']['mom_strategy_direction'] else 'NO'}")
    L.append("")
    L.append("PASS requires all three checks OK. FAIL if all point wrong/flat. "
             "INCONCLUSIVE if mixed or insufficient sample.")
    L.append("")
    L.append("### Caveats")
    L.append(f"- Sample: {CANDLES_NEEDED} 1h bars requested (~90 days) per symbol. "
             "Short window; one vol epoch.")
    L.append("- Proxy is realized-vol, NOT true dealer gamma. A null result kills the *proxy*, "
             "not necessarily true GEX (but removes the cheap justification to buy options history).")
    L.append(f"- Strategy-conditioned test depends on the in-repo {MR_STRATEGY} / {MOM_STRATEGY} "
             "signal logic and trade counts; thin per-regime buckets reduce reliability. "
             "(vol_breakout fired only 1-2x/90d on 1h, hence range_breakout for the momentum leg.)")

    OUT_SUMMARY.write_text("\n".join(L))
    print(f"wrote {OUT_SUMMARY}")
    print(f"total time: {time.time()-t0:.1f}s")
    print(f"\nVERDICT: {verdict}")


if __name__ == "__main__":
    asyncio.run(main())
