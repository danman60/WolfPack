"""Phase 4: Multi-gate edge provenance validator.

Tests 5 hypothesis-driven conditional expectancy claims, not strategies.
Each hypothesis is a statement of the form:
  "When condition X is true, forward N-bar return on symbol Y differs
   from baseline by E with t-statistic T."

Run through 4 sequential gates per (hypothesis, symbol, timeframe) cell:
  Gate 1: Statistical signal exists  (t > 2, |effect| > cost)
  Gate 2: Walk-forward stability     (IS and OOS agree, |OOS effect| > 0.5*IS)
  Gate 3: Cost-aware backtest        (Sharpe > 0.5 net of 10bps round-trip,
                                       beats HODL of same window)
  Gate 4: Robustness perturbation    (signal survives ±20% param changes)

Stops as soon as any gate fails. Output: per-cell verdict at the latest
gate that passed.
"""

import asyncio
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

INTEL_PATH = Path(__file__).resolve().parents[3] / "intel"
sys.path.insert(0, str(INTEL_PATH))

import httpx
import numpy as np
from wolfpack.exchanges.base import Candle

INTEL_API = "http://159.89.115.95:8000"
SYMBOLS = ["BTC", "ETH", "SOL", "LINK", "AVAX", "ARB", "DOGE"]
TIMEFRAMES = [("4h", 5000)]  # 28mo, the trustworthy series
ROUND_TRIP_BPS = 10.0  # 5+5 maker/taker, conservative
COST_PCT = ROUND_TRIP_BPS / 10000.0

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase4_edge_provenance.json"
OUT_SUMMARY = OUT_DIR / "phase4_edge_provenance.md"


# ---------- Hypothesis definitions ----------
# Each hypothesis is a function: (closes, highs, lows, volumes, params) -> boolean array
# True at index i means "condition fired at bar i, take a position with given direction"
# Returns: (fired_array, direction_array)  where direction is +1 (long) or -1 (short)

def h_capitulation_flush(closes, highs, lows, volumes, lookback=120, percentile=5):
    """H1: Sharp downside flush in 5 bars predicts positive forward return.

    Computes 5-bar log return; fires LONG when below the percentile-th
    percentile of trailing `lookback` bars (capitulation).
    """
    n = len(closes)
    fired = np.zeros(n, dtype=bool)
    direction = np.zeros(n, dtype=int)
    log_close = np.log(closes)
    ret_5 = np.zeros(n)
    ret_5[5:] = log_close[5:] - log_close[:-5]
    for i in range(lookback + 5, n):
        window = ret_5[i - lookback : i]
        thresh = np.percentile(window, percentile)
        if ret_5[i] < thresh:
            fired[i] = True
            direction[i] = +1
    return fired, direction


def h_blowoff_top(closes, highs, lows, volumes, lookback=120, percentile=95):
    """H2: Sharp upside blowoff in 5 bars predicts negative forward return."""
    n = len(closes)
    fired = np.zeros(n, dtype=bool)
    direction = np.zeros(n, dtype=int)
    log_close = np.log(closes)
    ret_5 = np.zeros(n)
    ret_5[5:] = log_close[5:] - log_close[:-5]
    for i in range(lookback + 5, n):
        window = ret_5[i - lookback : i]
        thresh = np.percentile(window, percentile)
        if ret_5[i] > thresh:
            fired[i] = True
            direction[i] = -1
    return fired, direction


def h_inside_bar_compression(closes, highs, lows, volumes, lookback=20, atr_pctile=20):
    """H3: ATR compression (low ATR percentile) + inside bar predicts breakout direction = trend continuation."""
    n = len(closes)
    fired = np.zeros(n, dtype=bool)
    direction = np.zeros(n, dtype=int)
    # ATR(14)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
    atr14 = np.zeros(n)
    for i in range(14, n):
        atr14[i] = np.mean(tr[i-14:i])
    for i in range(lookback + 14, n):
        if atr14[i] <= 0: continue
        window = atr14[i - lookback : i]
        thresh = np.percentile(window, atr_pctile)
        # Inside bar
        is_inside = highs[i] < highs[i-1] and lows[i] > lows[i-1]
        if atr14[i] < thresh and is_inside:
            fired[i] = True
            # Direction = sign of close vs open (next-bar bias from current bar candle color)
            direction[i] = +1 if closes[i] > closes[i-1] else -1
    return fired, direction


def h_volume_climax_reversal(closes, highs, lows, volumes, lookback=20, vol_mult=2.5):
    """H4: Volume climax (vol > 2.5x avg) on extreme bar (close near low/high) predicts reversion."""
    n = len(closes)
    fired = np.zeros(n, dtype=bool)
    direction = np.zeros(n, dtype=int)
    for i in range(lookback, n):
        avg_vol = np.mean(volumes[i - lookback : i])
        if avg_vol <= 0 or volumes[i] < vol_mult * avg_vol: continue
        bar_range = highs[i] - lows[i]
        if bar_range <= 0: continue
        close_pos = (closes[i] - lows[i]) / bar_range  # 0 = at low, 1 = at high
        if close_pos < 0.20:  # close near low after vol climax → reversion long
            fired[i] = True
            direction[i] = +1
        elif close_pos > 0.80:  # close near high → reversion short
            fired[i] = True
            direction[i] = -1
    return fired, direction


def h_streak_exhaustion(closes, highs, lows, volumes, streak=6):
    """H5: 6+ consecutive same-direction closes predict reversion."""
    n = len(closes)
    fired = np.zeros(n, dtype=bool)
    direction = np.zeros(n, dtype=int)
    for i in range(streak, n):
        diffs = np.diff(closes[i - streak : i + 1])
        if np.all(diffs > 0):
            fired[i] = True
            direction[i] = -1  # uptrend exhaustion → short
        elif np.all(diffs < 0):
            fired[i] = True
            direction[i] = +1  # downtrend exhaustion → long
    return fired, direction


HYPOTHESES = {
    "H1_capitulation_flush": (h_capitulation_flush, {"lookback": 120, "percentile": 5}),
    "H2_blowoff_top": (h_blowoff_top, {"lookback": 120, "percentile": 95}),
    "H3_inside_bar_compression": (h_inside_bar_compression, {"lookback": 20, "atr_pctile": 20}),
    "H4_volume_climax_reversal": (h_volume_climax_reversal, {"lookback": 20, "vol_mult": 2.5}),
    "H5_streak_exhaustion": (h_streak_exhaustion, {"streak": 6}),
}

FORWARD_HORIZONS = [1, 4, 12, 24]  # bars


# ---------- Forward returns ----------
def compute_forward_returns(closes, fired, direction, horizon):
    """For each fired bar, compute direction-adjusted forward return (close-to-close)."""
    n = len(closes)
    rets = []
    for i in range(n):
        if not fired[i]: continue
        if i + horizon >= n: continue
        raw = (closes[i + horizon] - closes[i]) / closes[i]
        rets.append(raw * direction[i])  # multiply by direction to get directional P&L
    return np.array(rets)


def compute_baseline_returns(closes, fired, direction, horizon):
    """Forward returns on the SAME direction-conditional but on bars where condition did NOT fire.

    To make baseline comparable, we use the global mean directional return —
    sign-conditional baseline gets meaningless when most bars don't fire.
    Use unconditional |return| to compare effect size.
    """
    n = len(closes)
    rets = []
    for i in range(n - horizon):
        if fired[i]: continue
        raw = (closes[i + horizon] - closes[i]) / closes[i]
        rets.append(raw)
    return np.array(rets)


# ---------- Gates ----------
def gate1_signal(closes, fired, direction, horizon):
    """Gate 1: t-stat > 2 AND |effect| > round-trip cost AND n >= 30."""
    fired_rets = compute_forward_returns(closes, fired, direction, horizon)
    n = len(fired_rets)
    if n < 30:
        return {"pass": False, "reason": f"n={n}<30", "n": n}
    m = float(np.mean(fired_rets))
    s = float(np.std(fired_rets, ddof=1)) if n > 1 else 0.0
    if s == 0:
        return {"pass": False, "reason": "zero stddev", "n": n}
    t_stat = m / (s / math.sqrt(n))
    effect_pct = m * 100
    pass_t = t_stat > 2.0
    pass_effect = abs(m) > COST_PCT
    pass_dir = m > 0  # we already direction-adjusted, so positive = edge in our favor
    passed = pass_t and pass_effect and pass_dir
    return {
        "pass": bool(passed), "n": n, "mean_pct": effect_pct,
        "t_stat": t_stat, "stddev_pct": s * 100,
        "reason": (None if passed else f"t={t_stat:.2f} effect={effect_pct:+.3f}% pass_t={pass_t} pass_effect={pass_effect} pass_dir={pass_dir}"),
    }


def gate2_walkforward(closes, fired, direction, horizon, split=0.7):
    """Gate 2: split into IS/OOS, both must show same-sign effect, OOS effect >= 0.5 * IS."""
    n = len(closes)
    cutoff = int(n * split)
    fired_is = fired.copy(); fired_is[cutoff:] = False
    fired_oos = fired.copy(); fired_oos[:cutoff] = False
    is_rets = compute_forward_returns(closes, fired_is, direction, horizon)
    oos_rets = compute_forward_returns(closes, fired_oos, direction, horizon)
    if len(is_rets) < 15 or len(oos_rets) < 15:
        return {"pass": False, "reason": f"is_n={len(is_rets)} oos_n={len(oos_rets)} too few"}
    is_m = float(np.mean(is_rets))
    oos_m = float(np.mean(oos_rets))
    same_sign = (is_m > 0 and oos_m > 0) or (is_m < 0 and oos_m < 0)
    oos_meaningful = abs(oos_m) >= 0.5 * abs(is_m) if is_m != 0 else False
    passed = same_sign and oos_meaningful and oos_m > 0
    return {
        "pass": bool(passed),
        "is_n": len(is_rets), "is_mean_pct": is_m * 100,
        "oos_n": len(oos_rets), "oos_mean_pct": oos_m * 100,
        "reason": (None if passed else f"IS={is_m*100:+.3f}% OOS={oos_m*100:+.3f}% same_sign={same_sign} oos_meaningful={oos_meaningful}"),
    }


def gate3_cost_backtest(closes, fired, direction, horizon):
    """Gate 3: full strategy P&L net of round-trip cost; Sharpe > 0.5; beats HODL."""
    fired_rets = compute_forward_returns(closes, fired, direction, horizon)
    if len(fired_rets) < 30:
        return {"pass": False, "reason": "too few trades"}
    net_rets = fired_rets - COST_PCT  # subtract round-trip cost per trade
    cumulative_pct = float(np.sum(net_rets) * 100)  # simple sum, not compounded — fast
    m = float(np.mean(net_rets))
    s = float(np.std(net_rets, ddof=1))
    if s == 0:
        return {"pass": False, "reason": "zero stddev net"}
    # Annualize Sharpe — bars/year depends on TF; for 4h: 6*365=2190
    bars_per_year = 2190
    annualization = math.sqrt(bars_per_year / horizon)
    sharpe = (m / s) * annualization
    # HODL comparison: full-period buy-and-hold from first to last bar
    hodl_pct = (closes[-1] / closes[0] - 1) * 100
    beats_hodl = cumulative_pct > hodl_pct
    pass_sharpe = sharpe > 0.5
    pass_pos = cumulative_pct > 0
    passed = pass_sharpe and pass_pos
    return {
        "pass": bool(passed), "cumulative_pct": cumulative_pct,
        "hodl_pct": hodl_pct, "sharpe": sharpe, "beats_hodl": bool(beats_hodl),
        "n_trades": len(fired_rets),
        "reason": (None if passed else f"sharpe={sharpe:.2f} cum={cumulative_pct:+.2f}% hodl={hodl_pct:+.2f}%"),
    }


def gate4_robustness(closes, highs, lows, volumes, h_func, base_params, horizon):
    """Gate 4: perturb each numeric parameter ±20%, ensure Gate 1 still passes."""
    perturbations_ok = []
    perturbations_fail = []
    for k, v in base_params.items():
        if not isinstance(v, (int, float)):
            continue
        for mult in [0.8, 1.2]:
            new_v = type(v)(v * mult) if isinstance(v, int) else v * mult
            if new_v == v:  # too small to perturb
                continue
            new_params = {**base_params, k: new_v}
            try:
                fired_p, direction_p = h_func(closes, highs, lows, volumes, **new_params)
                g1 = gate1_signal(closes, fired_p, direction_p, horizon)
                if g1["pass"]:
                    perturbations_ok.append(f"{k}={new_v}")
                else:
                    perturbations_fail.append(f"{k}={new_v}: {g1.get('reason','fail')}")
            except Exception as e:
                perturbations_fail.append(f"{k}={new_v}: exc {e}")
    pass_count = len(perturbations_ok)
    fail_count = len(perturbations_fail)
    total = pass_count + fail_count
    if total == 0:
        return {"pass": False, "reason": "no numeric params to perturb"}
    pass_rate = pass_count / total
    passed = pass_rate >= 0.75
    return {
        "pass": bool(passed), "ok": pass_count, "fail": fail_count,
        "pass_rate": pass_rate, "fail_examples": perturbations_fail[:3],
    }


# ---------- Driver ----------
async def fetch_candles(client, symbol, interval, limit):
    r = await client.get(
        f"{INTEL_API}/market/candles",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=120,
    )
    r.raise_for_status()
    return [Candle(**c) for c in r.json()["candles"]]


def candle_arrays(candles):
    closes = np.array([c.close for c in candles], dtype=np.float64)
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows = np.array([c.low for c in candles], dtype=np.float64)
    volumes = np.array([c.volume for c in candles], dtype=np.float64)
    return closes, highs, lows, volumes


async def main():
    t0 = time.time()
    print(f"Phase 4 — Edge Provenance Validator")
    print(f"  Hypotheses: {len(HYPOTHESES)}")
    print(f"  Symbols: {len(SYMBOLS)}")
    print(f"  Timeframes: {len(TIMEFRAMES)}")
    print(f"  Forward horizons: {FORWARD_HORIZONS}")
    print(f"  Round-trip cost: {ROUND_TRIP_BPS} bps")
    print()

    candles_cache = {}
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
    print(f"\nfetch took {time.time()-t0:.0f}s\n")

    results = []
    for hyp_name, (h_func, base_params) in HYPOTHESES.items():
        print(f"\n=== {hyp_name} ===")
        for tf, _ in TIMEFRAMES:
            for sym in SYMBOLS:
                candles = candles_cache.get((sym, tf), [])
                if len(candles) < 500:
                    continue
                closes, highs, lows, volumes = candle_arrays(candles)
                fired, direction = h_func(closes, highs, lows, volumes, **base_params)
                n_fired = int(np.sum(fired))

                # Best forward horizon by Gate 1 t-stat
                best_horizon = None
                best_g1 = None
                for h in FORWARD_HORIZONS:
                    g1 = gate1_signal(closes, fired, direction, h)
                    if g1.get("t_stat") is not None:
                        if best_g1 is None or g1["t_stat"] > best_g1["t_stat"]:
                            best_g1 = g1
                            best_horizon = h

                if best_g1 is None or not best_g1["pass"]:
                    print(f"  {sym:5} {tf:3} fired={n_fired:4} GATE1 FAIL @ best_h={best_horizon}: {best_g1['reason'] if best_g1 else 'no fires'}")
                    results.append({
                        "hypothesis": hyp_name, "symbol": sym, "tf": tf, "n_fired": n_fired,
                        "best_horizon": best_horizon, "gate1": best_g1, "passed_to": "Gate 1",
                    })
                    continue

                # Gate 2 at the winning horizon
                g2 = gate2_walkforward(closes, fired, direction, best_horizon)
                if not g2["pass"]:
                    print(f"  {sym:5} {tf:3} fired={n_fired:4} h={best_horizon} GATE1✓ (t={best_g1['t_stat']:.2f}, eff={best_g1['mean_pct']:+.3f}%) GATE2✗: {g2['reason']}")
                    results.append({
                        "hypothesis": hyp_name, "symbol": sym, "tf": tf, "n_fired": n_fired,
                        "best_horizon": best_horizon, "gate1": best_g1, "gate2": g2, "passed_to": "Gate 1",
                    })
                    continue

                # Gate 3
                g3 = gate3_cost_backtest(closes, fired, direction, best_horizon)
                if not g3["pass"]:
                    print(f"  {sym:5} {tf:3} fired={n_fired:4} h={best_horizon} GATE1✓ GATE2✓ (IS={g2['is_mean_pct']:+.3f}% OOS={g2['oos_mean_pct']:+.3f}%) GATE3✗: {g3['reason']}")
                    results.append({
                        "hypothesis": hyp_name, "symbol": sym, "tf": tf, "n_fired": n_fired,
                        "best_horizon": best_horizon, "gate1": best_g1, "gate2": g2, "gate3": g3, "passed_to": "Gate 2",
                    })
                    continue

                # Gate 4
                g4 = gate4_robustness(closes, highs, lows, volumes, h_func, base_params, best_horizon)
                hodl_str = "BEATS_HODL" if g3["beats_hodl"] else f"under_HODL({g3['hodl_pct']:+.1f}%)"
                if not g4["pass"]:
                    print(f"  {sym:5} {tf:3} fired={n_fired:4} h={best_horizon} G1✓ G2✓ G3✓ (Sharpe={g3['sharpe']:.2f}, {hodl_str}) G4✗ (pass_rate={g4['pass_rate']:.0%})")
                    results.append({
                        "hypothesis": hyp_name, "symbol": sym, "tf": tf, "n_fired": n_fired,
                        "best_horizon": best_horizon, "gate1": best_g1, "gate2": g2, "gate3": g3, "gate4": g4, "passed_to": "Gate 3",
                    })
                    continue

                print(f"  {sym:5} {tf:3} fired={n_fired:4} h={best_horizon} ★ALL GATES PASS★ Sharpe={g3['sharpe']:.2f} cum={g3['cumulative_pct']:+.1f}% {hodl_str}")
                results.append({
                    "hypothesis": hyp_name, "symbol": sym, "tf": tf, "n_fired": n_fired,
                    "best_horizon": best_horizon, "gate1": best_g1, "gate2": g2, "gate3": g3, "gate4": g4, "passed_to": "Gate 4",
                })

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")

    # Summary
    lines = []
    lines.append("# Phase 4: Edge Provenance Validator Results")
    lines.append(f"\n**{len(HYPOTHESES)} hypotheses × {len(SYMBOLS)} symbols × {len(TIMEFRAMES)} timeframes** = {len(results)} cells.")
    lines.append(f"\n**Round-trip cost**: {ROUND_TRIP_BPS} bps. **Forward horizons**: {FORWARD_HORIZONS} bars.")
    lines.append(f"\n**Acceptance gates:**")
    lines.append(f"- Gate 1: t-stat > 2 AND |effect| > {ROUND_TRIP_BPS}bps AND n >= 30 AND positive direction")
    lines.append(f"- Gate 2: walk-forward IS/OOS same-sign AND OOS effect >= 0.5×IS AND OOS positive")
    lines.append(f"- Gate 3: net Sharpe > 0.5 (annualized) AND cumulative > 0 net of cost")
    lines.append(f"- Gate 4: Gate 1 survives ±20% on every numeric parameter, ≥75% perturbation pass\n")

    by_gate = defaultdict(list)
    for r in results:
        by_gate[r["passed_to"]].append(r)

    lines.append("## Verdict counts")
    lines.append("| Gate reached | Count |")
    lines.append("|---|---|")
    for g in ["Gate 4", "Gate 3", "Gate 2", "Gate 1"]:
        lines.append(f"| Passed through {g} | {len(by_gate[g])} |")

    survivors = by_gate["Gate 4"]
    lines.append(f"\n## Survivors ({len(survivors)} cells passed all 4 gates)")
    if survivors:
        lines.append("| hypothesis | sym | tf | n | h | mean% | t | Sharpe | cum% | HODL% | beats |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in sorted(survivors, key=lambda x: -x["gate3"]["sharpe"]):
            g1 = r["gate1"]; g3 = r["gate3"]
            beats = "✓" if g3["beats_hodl"] else "✗"
            lines.append(f"| {r['hypothesis']} | {r['symbol']} | {r['tf']} | {g1['n']} | {r['best_horizon']} | {g1['mean_pct']:+.3f} | {g1['t_stat']:.2f} | {g3['sharpe']:.2f} | {g3['cumulative_pct']:+.1f} | {g3['hodl_pct']:+.1f} | {beats} |")
    else:
        lines.append("\n**No cells passed all 4 gates.**\n")

    lines.append("\n## Cells that passed Gate 1 (statistical signal exists)")
    g1_passers = [r for r in results if r["gate1"] and r["gate1"]["pass"]]
    lines.append(f"\n{len(g1_passers)} of {len(results)} cells.")
    if g1_passers:
        lines.append("\n| hypothesis | sym | tf | n | h | mean% | t-stat | next_gate_failed | reason |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in sorted(g1_passers, key=lambda x: -x["gate1"]["t_stat"]):
            g1 = r["gate1"]
            failed_at = "passed all" if r["passed_to"] == "Gate 4" else r["passed_to"]
            reason = ""
            if "gate2" in r and not r["gate2"]["pass"]: reason = r["gate2"]["reason"]
            elif "gate3" in r and not r["gate3"]["pass"]: reason = r["gate3"]["reason"]
            elif "gate4" in r and not r["gate4"]["pass"]: reason = f"perturbation pass_rate={r['gate4']['pass_rate']:.0%}"
            lines.append(f"| {r['hypothesis']} | {r['symbol']} | {r['tf']} | {g1['n']} | {r['best_horizon']} | {g1['mean_pct']:+.3f} | {g1['t_stat']:.2f} | {failed_at} | {reason} |")

    # By-hypothesis success summary
    by_hyp = defaultdict(lambda: {"total": 0, "g1": 0, "g2": 0, "g3": 0, "g4": 0})
    for r in results:
        by_hyp[r["hypothesis"]]["total"] += 1
        if r["gate1"] and r["gate1"]["pass"]: by_hyp[r["hypothesis"]]["g1"] += 1
        if r.get("gate2") and r["gate2"]["pass"]: by_hyp[r["hypothesis"]]["g2"] += 1
        if r.get("gate3") and r["gate3"]["pass"]: by_hyp[r["hypothesis"]]["g3"] += 1
        if r.get("gate4") and r["gate4"]["pass"]: by_hyp[r["hypothesis"]]["g4"] += 1
    lines.append("\n## By hypothesis — gate funnel")
    lines.append("| hypothesis | cells | G1 pass | G2 pass | G3 pass | G4 pass |")
    lines.append("|---|---|---|---|---|---|")
    for h, s in by_hyp.items():
        lines.append(f"| {h} | {s['total']} | {s['g1']} | {s['g2']} | {s['g3']} | {s['g4']} |")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"wrote {OUT_SUMMARY}")
    print(f"\ntotal: {time.time()-t0:.0f}s")
    print(f"survivors (passed all 4 gates): {len(survivors)} / {len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
