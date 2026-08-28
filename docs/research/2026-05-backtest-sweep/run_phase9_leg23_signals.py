"""Phase 9: Leg 2 (bull) + Leg 3 (bear) signal hypothesis tests.

Phase 6 found Leg 1 (sideways/bear long via funding-z-low). This script tests
hypotheses for the other two regimes:

Leg 2 — TRENDING UP signals (LONG):
  B1: premium_z > +1.5 (7d) AND price > SMA200 — healthy contango + uptrend
  B2: funding_z in [+0.5, +1.5] (30d) AND price > SMA200 — paid momentum
  B3: 30d return > +5% AND price > SMA200 AND funding > 0 — TSMOM with fund confirm

Leg 3 — TRENDING DOWN signals (SHORT):
  D1: funding_z > +2 (30d) AND price < SMA200 — long crowding into weakness
  D2: premium_z < -1.5 (7d) AND price < SMA200 — backwardation in downtrend
  D3: 30d return < -5% AND price < SMA200 — TSMOM down

Same 4-gate framework as Phase 4/6.
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
OUT_RESULTS = OUT_DIR / "phase9_leg23_signals.json"
OUT_SUMMARY = OUT_DIR / "phase9_leg23_signals.md"


async def fetch_funding(client, coin, start_ms):
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


def align(funding_records, candles, key):
    funding_records.sort(key=lambda x: x["time"])
    f_t = np.array([r["time"] for r in funding_records])
    f_v = np.array([float(r[key]) for r in funding_records])
    closes = np.array([c.close for c in candles], dtype=np.float64)
    aligned = np.full(len(candles), np.nan)
    times = np.array([c.timestamp for c in candles])
    for i, t in enumerate(times):
        idx = np.searchsorted(f_t, t, side="right") - 1
        if idx >= 0: aligned[i] = f_v[idx]
    return closes, aligned


def rolling_zscore(arr, window):
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        w = arr[i - window : i]
        w = w[~np.isnan(w)]
        if len(w) < window // 2: continue
        mu, sigma = np.mean(w), np.std(w, ddof=1)
        if sigma > 0: out[i] = (arr[i] - mu) / sigma
    return out


def sma(closes, period):
    out = np.full(len(closes), np.nan)
    for i in range(period, len(closes)):
        out[i] = np.mean(closes[i - period : i])
    return out


def returns_n_bars(closes, n):
    out = np.full(len(closes), np.nan)
    for i in range(n, len(closes)):
        if closes[i - n] > 0:
            out[i] = (closes[i] - closes[i - n]) / closes[i - n]
    return out


# ---------- Hypothesis fire functions ----------
def h_b1_premium_high_uptrend(closes, premium):
    z = rolling_zscore(premium, 42)  # 7d
    s200 = sma(closes, 200)
    fired = (z > 1.5) & (closes > s200)
    direction = np.where(fired, +1, 0)
    return fired, direction


def h_b2_funding_moderate_uptrend(closes, funding):
    z = rolling_zscore(funding, 180)  # 30d
    s200 = sma(closes, 200)
    fired = (z > 0.5) & (z < 1.5) & (closes > s200)
    direction = np.where(fired, +1, 0)
    return fired, direction


def h_b3_tsmom_long(closes, funding):
    s200 = sma(closes, 200)
    r30 = returns_n_bars(closes, 180)
    fired = (r30 > 0.05) & (closes > s200) & (funding > 0)
    direction = np.where(fired, +1, 0)
    return fired, direction


def h_d1_funding_high_downtrend(closes, funding):
    z = rolling_zscore(funding, 180)
    s200 = sma(closes, 200)
    fired = (z > 2.0) & (closes < s200)
    direction = np.where(fired, -1, 0)
    return fired, direction


def h_d2_premium_low_downtrend(closes, premium):
    z = rolling_zscore(premium, 42)
    s200 = sma(closes, 200)
    fired = (z < -1.5) & (closes < s200)
    direction = np.where(fired, -1, 0)
    return fired, direction


def h_d3_tsmom_short(closes, funding=None):
    s200 = sma(closes, 200)
    r30 = returns_n_bars(closes, 180)
    fired = (r30 < -0.05) & (closes < s200)
    direction = np.where(fired, -1, 0)
    return fired, direction


HYPOTHESES = {
    "B1_premium_high_uptrend_LONG": ("premium", h_b1_premium_high_uptrend),
    "B2_funding_moderate_uptrend_LONG": ("fundingRate", h_b2_funding_moderate_uptrend),
    "B3_tsmom_long_LONG": ("fundingRate", h_b3_tsmom_long),
    "D1_funding_high_downtrend_SHORT": ("fundingRate", h_d1_funding_high_downtrend),
    "D2_premium_low_downtrend_SHORT": ("premium", h_d2_premium_low_downtrend),
    "D3_tsmom_short_SHORT": ("fundingRate", h_d3_tsmom_short),
}

FORWARD_HORIZONS = [1, 3, 6, 12]  # 4h, 12h, 24h, 48h


# ---------- Gates ----------
def gate1(closes, fired, direction, horizon):
    n = len(closes)
    rets = []
    for i in range(n - horizon):
        if not fired[i]: continue
        raw = (closes[i + horizon] - closes[i]) / closes[i]
        rets.append(raw * direction[i])
    rets = np.array(rets)
    if len(rets) < 30:
        return {"pass": False, "reason": f"n={len(rets)}<30"}
    m, s = float(np.mean(rets)), float(np.std(rets, ddof=1))
    if s == 0: return {"pass": False, "reason": "zero stddev"}
    t = m / (s / math.sqrt(len(rets)))
    return {
        "pass": bool(t > 2.0 and abs(m) > COST_PCT and m > 0),
        "n": len(rets), "mean_pct": m * 100, "t_stat": t,
        "reason": (None if (t > 2.0 and abs(m) > COST_PCT and m > 0) else f"t={t:.2f} eff={m*100:+.3f}% dir={m>0}"),
    }


def gate2(closes, fired, direction, horizon, split=0.7):
    n = len(closes)
    cutoff = int(n * split)
    is_rets, oos_rets = [], []
    for i in range(n - horizon):
        if not fired[i]: continue
        raw = ((closes[i + horizon] - closes[i]) / closes[i]) * direction[i]
        if i < cutoff: is_rets.append(raw)
        else: oos_rets.append(raw)
    if len(is_rets) < 15 or len(oos_rets) < 15:
        return {"pass": False, "reason": f"is_n={len(is_rets)} oos_n={len(oos_rets)}"}
    is_m, oos_m = float(np.mean(is_rets)), float(np.mean(oos_rets))
    same_sign = (is_m > 0 and oos_m > 0) or (is_m < 0 and oos_m < 0)
    oos_meaningful = abs(oos_m) >= 0.5 * abs(is_m) if is_m != 0 else False
    return {
        "pass": bool(same_sign and oos_meaningful and oos_m > 0),
        "is_n": len(is_rets), "is_mean_pct": is_m * 100,
        "oos_n": len(oos_rets), "oos_mean_pct": oos_m * 100,
    }


def gate3(closes, fired, direction, horizon):
    rets = []
    n = len(closes)
    for i in range(n - horizon):
        if not fired[i]: continue
        raw = (closes[i + horizon] - closes[i]) / closes[i]
        rets.append(raw * direction[i])
    rets = np.array(rets)
    if len(rets) < 30: return {"pass": False, "reason": "too few"}
    net = rets - COST_PCT
    cum = float(np.sum(net) * 100)
    m, s = float(np.mean(net)), float(np.std(net, ddof=1))
    if s == 0: return {"pass": False, "reason": "zero stddev"}
    bars_per_year = 2190
    annualization = math.sqrt(bars_per_year / horizon)
    sharpe = (m / s) * annualization
    hodl = (closes[-1] / closes[0] - 1) * 100
    return {
        "pass": bool(sharpe > 0.5 and cum > 0),
        "cumulative_pct": cum, "sharpe": sharpe, "hodl_pct": hodl,
        "beats_hodl": bool(cum > hodl), "n_trades": len(rets),
    }


def gate4(closes, signal, h_func, horizon):
    """Perturb the threshold in the function. We don't have a clean factorization,
    so we re-implement with a few perturbations of internal thresholds."""
    perts_ok, perts_fail = [], []
    if h_func == h_b1_premium_high_uptrend:
        for thresh in [1.2, 1.8]:
            z = rolling_zscore(signal, 42)
            s200 = sma(closes, 200)
            fired_p = (z > thresh) & (closes > s200)
            direction_p = np.where(fired_p, +1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perts_ok if g1["pass"] else perts_fail).append(f"thresh={thresh}")
    elif h_func == h_b2_funding_moderate_uptrend:
        for lo, hi in [(0.4, 1.2), (0.6, 1.8)]:
            z = rolling_zscore(signal, 180)
            s200 = sma(closes, 200)
            fired_p = (z > lo) & (z < hi) & (closes > s200)
            direction_p = np.where(fired_p, +1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perts_ok if g1["pass"] else perts_fail).append(f"range=[{lo},{hi}]")
    elif h_func == h_b3_tsmom_long:
        for r_thresh in [0.04, 0.06]:
            s200 = sma(closes, 200)
            r30 = returns_n_bars(closes, 180)
            fired_p = (r30 > r_thresh) & (closes > s200) & (signal > 0)
            direction_p = np.where(fired_p, +1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perts_ok if g1["pass"] else perts_fail).append(f"r_thresh={r_thresh}")
    elif h_func == h_d1_funding_high_downtrend:
        for thresh in [1.6, 2.4]:
            z = rolling_zscore(signal, 180)
            s200 = sma(closes, 200)
            fired_p = (z > thresh) & (closes < s200)
            direction_p = np.where(fired_p, -1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perts_ok if g1["pass"] else perts_fail).append(f"thresh={thresh}")
    elif h_func == h_d2_premium_low_downtrend:
        for thresh in [-1.2, -1.8]:
            z = rolling_zscore(signal, 42)
            s200 = sma(closes, 200)
            fired_p = (z < thresh) & (closes < s200)
            direction_p = np.where(fired_p, -1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perts_ok if g1["pass"] else perts_fail).append(f"thresh={thresh}")
    elif h_func == h_d3_tsmom_short:
        for r_thresh in [-0.04, -0.06]:
            s200 = sma(closes, 200)
            r30 = returns_n_bars(closes, 180)
            fired_p = (r30 < r_thresh) & (closes < s200)
            direction_p = np.where(fired_p, -1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perts_ok if g1["pass"] else perts_fail).append(f"r_thresh={r_thresh}")
    total = len(perts_ok) + len(perts_fail)
    if total == 0: return {"pass": False}
    return {"pass": bool(len(perts_ok) / total >= 0.5),
            "ok": len(perts_ok), "fail": len(perts_fail)}


async def main():
    t0 = time.time()
    print("Phase 9 — Leg 2 (BULL) + Leg 3 (BEAR) signal validator\n")

    funding_cache, candles_cache = {}, {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            print(f"fetching {sym}...")
            funding_cache[sym] = await fetch_funding(client, sym, 1704067200000)
            await asyncio.sleep(2)
            candles_cache[sym] = await fetch_candles(client, sym)
            print(f"  funding={len(funding_cache[sym])} candles={len(candles_cache[sym])}")
    print(f"fetch took {time.time()-t0:.0f}s\n")

    results = []
    for hyp_name, (key, h_func) in HYPOTHESES.items():
        print(f"\n=== {hyp_name} ===")
        for sym in SYMBOLS:
            if not funding_cache.get(sym) or not candles_cache.get(sym): continue
            closes, signal = align(funding_cache[sym], candles_cache[sym], key=key)
            if np.sum(~np.isnan(signal)) < 200: continue
            fired, direction = h_func(closes, signal)
            n_fired = int(np.sum(fired))
            if n_fired < 20:
                print(f"  {sym:5} fired={n_fired:4} too few")
                results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "passed_to": "fire"})
                continue

            best_h, best_g1 = None, None
            for h in FORWARD_HORIZONS:
                g1 = gate1(closes, fired, direction, h)
                if g1.get("t_stat") is not None and (best_g1 is None or g1["t_stat"] > best_g1["t_stat"]):
                    best_g1, best_h = g1, h

            if best_g1 is None or not best_g1["pass"]:
                print(f"  {sym:5} fired={n_fired:4} G1✗ best_h={best_h}: {best_g1.get('reason') if best_g1 else 'none'}")
                results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "best_h": best_h, "g1": best_g1, "passed_to": "Gate 1"})
                continue

            g2 = gate2(closes, fired, direction, best_h)
            if not g2["pass"]:
                print(f"  {sym:5} fired={n_fired:4} h={best_h} G1✓ (t={best_g1['t_stat']:.2f}) G2✗ IS={g2.get('is_mean_pct',0):+.3f}% OOS={g2.get('oos_mean_pct',0):+.3f}%")
                results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "best_h": best_h, "g1": best_g1, "g2": g2, "passed_to": "Gate 1"})
                continue

            g3 = gate3(closes, fired, direction, best_h)
            if not g3["pass"]:
                print(f"  {sym:5} fired={n_fired:4} h={best_h} G1✓ G2✓ G3✗ Sharpe={g3.get('sharpe',0):.2f} cum={g3.get('cumulative_pct',0):+.1f}%")
                results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "best_h": best_h, "g1": best_g1, "g2": g2, "g3": g3, "passed_to": "Gate 2"})
                continue

            g4 = gate4(closes, signal, h_func, best_h)
            beats = "BEATS_HODL" if g3["beats_hodl"] else f"under_HODL({g3['hodl_pct']:+.1f}%)"
            if not g4["pass"]:
                print(f"  {sym:5} fired={n_fired:4} h={best_h} G1✓ G2✓ G3✓ {beats} G4✗")
                results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "best_h": best_h, "g1": best_g1, "g2": g2, "g3": g3, "g4": g4, "passed_to": "Gate 3"})
                continue

            print(f"  {sym:5} fired={n_fired:4} h={best_h} ★ALL GATES PASS★ Sharpe={g3['sharpe']:.2f} cum={g3['cumulative_pct']:+.1f}% {beats}")
            results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "best_h": best_h, "g1": best_g1, "g2": g2, "g3": g3, "g4": g4, "passed_to": "Gate 4"})

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))

    # Summary
    lines = ["# Phase 9: Leg 2 (BULL) + Leg 3 (BEAR) signal hypotheses"]
    lines.append("\nSame 4-gate framework as Phase 4/6.\n")
    by_gate = defaultdict(list)
    for r in results: by_gate[r["passed_to"]].append(r)

    lines.append("## Verdict counts")
    lines.append("| Gate reached | Count |")
    lines.append("|---|---|")
    for g in ["Gate 4", "Gate 3", "Gate 2", "Gate 1", "fire"]:
        lines.append(f"| {g} | {len(by_gate[g])} |")

    survivors = by_gate["Gate 4"]
    lines.append(f"\n## Survivors ({len(survivors)} cells)")
    if survivors:
        lines.append("| hypothesis | sym | n | h | mean% | t | Sharpe | cum% | beats HODL |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in sorted(survivors, key=lambda x: -x["g3"]["sharpe"]):
            beats = "✓" if r["g3"]["beats_hodl"] else "✗"
            lines.append(f"| {r['hypothesis']} | {r['symbol']} | {r['g1']['n']} | {r['best_h']} | {r['g1']['mean_pct']:+.3f} | {r['g1']['t_stat']:.2f} | {r['g3']['sharpe']:.2f} | {r['g3']['cumulative_pct']:+.1f} | {beats} |")
    else:
        lines.append("\n**No cells passed all 4 gates.**\n")

    g1_passers = [r for r in results if r.get("g1") and r["g1"]["pass"]]
    lines.append(f"\n## Cells passing Gate 1 (statistical signal exists, n={len(g1_passers)})")
    if g1_passers:
        lines.append("| hypothesis | sym | n | h | mean% | t | reached |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in sorted(g1_passers, key=lambda x: -x["g1"]["t_stat"]):
            lines.append(f"| {r['hypothesis']} | {r['symbol']} | {r['g1']['n']} | {r['best_h']} | {r['g1']['mean_pct']:+.3f} | {r['g1']['t_stat']:.2f} | {r['passed_to']} |")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"\nwrote {OUT_RESULTS}")
    print(f"wrote {OUT_SUMMARY}")
    print(f"total: {time.time()-t0:.0f}s")
    print(f"survivors: {len(survivors)}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
