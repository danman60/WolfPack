"""Phase 6: Funding-rate / premium-basis edge provenance validator.

Tests 4 whale-positioning hypotheses on Hyperliquid funding history,
through the same 4-gate framework as Phase 4.

Data:
  - Hyperliquid /info fundingHistory: hourly funding + premium per symbol
  - 4h price candles via our intel API (28 months)

Hypotheses (whale-positioning proxies):
  F1: 30d funding z > +2 → forward 4h-48h price return is NEGATIVE (long crowding fades)
  F2: 30d funding z < -2 → forward return POSITIVE (short crowding fades)
  F3: 7d premium z > +2.5 → SHORT (perp trading rich vs oracle = leveraged-buyer crowding)
  F4: Absolute funding > 0.005%/hr (~44% APR) → SHORT (extreme directional crowding)
"""

import asyncio
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

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
OUT_RESULTS = OUT_DIR / "phase6_funding_edge.json"
OUT_SUMMARY = OUT_DIR / "phase6_funding_edge.md"


async def fetch_funding_history(client, coin: str, start_ms: int):
    """Paginate fundingHistory backwards from start_ms. Returns list of {time, fundingRate, premium}."""
    all_records = []
    cursor = start_ms
    backoff = 0.5
    while True:
        try:
            r = await client.post(HL_API, json={"type": "fundingHistory", "coin": coin, "startTime": cursor}, timeout=60)
            if r.status_code == 429:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            r.raise_for_status()
            backoff = 0.5
        except Exception as e:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
            if backoff >= 30:
                raise
            continue
        batch = r.json()
        if not batch:
            break
        all_records.extend(batch)
        last_time = batch[-1]["time"]
        if last_time <= cursor:  # no progress
            break
        cursor = last_time + 1
        if len(batch) < 100:  # likely last page
            break
        if len(all_records) > 50000:  # safety
            break
        await asyncio.sleep(0.3)  # gentle pacing between successful pages
    # dedupe by time
    seen = set()
    out = []
    for rec in all_records:
        if rec["time"] in seen:
            continue
        seen.add(rec["time"])
        out.append(rec)
    out.sort(key=lambda x: x["time"])
    return out


async def fetch_candles(client, symbol, interval="4h", limit=5000):
    r = await client.get(
        f"{INTEL_API}/market/candles",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=120,
    )
    r.raise_for_status()
    return [Candle(**c) for c in r.json()["candles"]]


def align_funding_to_candles(funding_records, candles, key="fundingRate"):
    """For each candle, find the most recent funding observation at or before it.
    Returns parallel arrays: closes (np), funding (np)."""
    # Sort funding by time ascending
    funding_records = sorted(funding_records, key=lambda x: x["time"])
    f_times = np.array([r["time"] for r in funding_records])
    f_vals = np.array([float(r[key]) for r in funding_records])
    closes = np.array([c.close for c in candles], dtype=np.float64)
    candle_times = np.array([c.timestamp for c in candles])
    aligned = np.full(len(candles), np.nan)
    for i, t in enumerate(candle_times):
        # binary search for last funding obs <= t
        idx = np.searchsorted(f_times, t, side="right") - 1
        if idx >= 0:
            aligned[i] = f_vals[idx]
    return closes, aligned, candle_times


def rolling_zscore(arr, window):
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        w = arr[i - window : i]
        w = w[~np.isnan(w)]
        if len(w) < window // 2:
            continue
        mu = np.mean(w)
        sigma = np.std(w, ddof=1)
        if sigma > 0:
            out[i] = (arr[i] - mu) / sigma
    return out


# ---------- Hypothesis fire arrays ----------
def h_f1_funding_high(closes, funding, candle_times):
    """F1: 30d funding z > +2 → SHORT."""
    z = rolling_zscore(funding, window=180)  # 30d * 6 4h-bars/day = 180
    fired = z > 2.0
    direction = np.where(fired, -1, 0)
    return fired, direction


def h_f2_funding_low(closes, funding, candle_times):
    """F2: 30d funding z < -2 → LONG."""
    z = rolling_zscore(funding, window=180)
    fired = z < -2.0
    direction = np.where(fired, +1, 0)
    return fired, direction


def h_f3_premium_high(closes, premium, candle_times):
    """F3: 7d premium z > +2.5 → SHORT."""
    z = rolling_zscore(premium, window=42)  # 7d * 6 4h-bars/day = 42
    fired = z > 2.5
    direction = np.where(fired, -1, 0)
    return fired, direction


def h_f4_absolute_funding_high(closes, funding, candle_times):
    """F4: absolute hourly funding > 0.005% → SHORT."""
    fired = funding > 0.00005  # 0.005% per hour
    direction = np.where(fired, -1, 0)
    return fired, direction


HYPOTHESES = {
    "F1_funding_z_high_short": ("fundingRate", h_f1_funding_high),
    "F2_funding_z_low_long": ("fundingRate", h_f2_funding_low),
    "F3_premium_z_high_short": ("premium", h_f3_premium_high),
    "F4_funding_abs_high_short": ("fundingRate", h_f4_absolute_funding_high),
}

FORWARD_HORIZONS = [1, 3, 6, 12]  # in 4h-bars: 4h, 12h, 24h, 48h forward


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
    m = float(np.mean(rets))
    s = float(np.std(rets, ddof=1))
    if s == 0:
        return {"pass": False, "reason": "zero stddev"}
    t_stat = m / (s / math.sqrt(len(rets)))
    pass_t = t_stat > 2.0
    pass_eff = abs(m) > COST_PCT
    pass_dir = m > 0
    return {
        "pass": bool(pass_t and pass_eff and pass_dir),
        "n": len(rets), "mean_pct": m * 100, "t_stat": t_stat, "stddev_pct": s * 100,
        "reason": (None if (pass_t and pass_eff and pass_dir) else f"t={t_stat:.2f} eff={m*100:+.3f}% dir={pass_dir}"),
    }


def gate2(closes, fired, direction, horizon, split=0.7):
    n = len(closes)
    cutoff = int(n * split)
    fired_is = fired.copy(); fired_is[cutoff:] = False
    fired_oos = fired.copy(); fired_oos[:cutoff] = False
    is_rets, oos_rets = [], []
    for i in range(n - horizon):
        if fired_is[i]:
            is_rets.append(((closes[i + horizon] - closes[i]) / closes[i]) * direction[i])
        elif fired_oos[i]:
            oos_rets.append(((closes[i + horizon] - closes[i]) / closes[i]) * direction[i])
    is_rets, oos_rets = np.array(is_rets), np.array(oos_rets)
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
    if len(rets) < 30:
        return {"pass": False, "reason": "too few"}
    net = rets - COST_PCT
    cum = float(np.sum(net) * 100)
    m, s = float(np.mean(net)), float(np.std(net, ddof=1))
    if s == 0:
        return {"pass": False, "reason": "zero stddev"}
    bars_per_year = 2190  # 4h
    annualization = math.sqrt(bars_per_year / horizon)
    sharpe = (m / s) * annualization
    hodl = (closes[-1] / closes[0] - 1) * 100
    return {
        "pass": bool(sharpe > 0.5 and cum > 0),
        "cumulative_pct": cum, "sharpe": sharpe, "hodl_pct": hodl,
        "beats_hodl": bool(cum > hodl), "n_trades": len(rets),
    }


def gate4(closes, funding_or_premium, h_func, horizon):
    """Perturb the threshold ±20%. Re-test Gate 1."""
    # The threshold isn't directly a parameter here — we'd need to factor it out.
    # For F1: z > 2.0; perturb to 1.6 and 2.4
    # We re-implement inline for this validator
    candle_times = np.arange(len(closes))  # not used in fire functions for funding
    perturbations_ok, perturbations_fail = [], []
    if h_func == h_f1_funding_high:
        for thresh in [1.6, 2.4]:
            z = rolling_zscore(funding_or_premium, 180)
            fired_p = z > thresh
            direction_p = np.where(fired_p, -1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perturbations_ok if g1["pass"] else perturbations_fail).append(f"thresh={thresh}")
    elif h_func == h_f2_funding_low:
        for thresh in [-1.6, -2.4]:
            z = rolling_zscore(funding_or_premium, 180)
            fired_p = z < thresh
            direction_p = np.where(fired_p, +1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perturbations_ok if g1["pass"] else perturbations_fail).append(f"thresh={thresh}")
    elif h_func == h_f3_premium_high:
        for thresh in [2.0, 3.0]:
            z = rolling_zscore(funding_or_premium, 42)
            fired_p = z > thresh
            direction_p = np.where(fired_p, -1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perturbations_ok if g1["pass"] else perturbations_fail).append(f"thresh={thresh}")
    elif h_func == h_f4_absolute_funding_high:
        for thresh in [0.00004, 0.00006]:
            fired_p = funding_or_premium > thresh
            direction_p = np.where(fired_p, -1, 0)
            g1 = gate1(closes, fired_p, direction_p, horizon)
            (perturbations_ok if g1["pass"] else perturbations_fail).append(f"thresh={thresh}")
    total = len(perturbations_ok) + len(perturbations_fail)
    if total == 0:
        return {"pass": False}
    return {
        "pass": bool(len(perturbations_ok) / total >= 0.5),
        "ok": len(perturbations_ok), "fail": len(perturbations_fail),
    }


async def main():
    t0 = time.time()
    print("Phase 6 — Funding/Premium Edge Provenance")
    print()

    # We need funding back ~28 months. Start from 2024-01-01.
    start_ms = 1704067200000  # 2024-01-01 UTC

    funding_cache = {}
    candles_cache = {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            print(f"fetching {sym} funding history...")
            try:
                fh = await fetch_funding_history(client, sym, start_ms)
                funding_cache[sym] = fh
                print(f"  got {len(fh)} hourly funding records")
            except Exception as e:
                print(f"  FAILED: {e}")
                funding_cache[sym] = []
            await asyncio.sleep(2)  # pause between symbols to be polite to HL
            print(f"fetching {sym} 4h candles...")
            try:
                c = await fetch_candles(client, sym, "4h", 5000)
                candles_cache[sym] = c
                print(f"  got {len(c)} candles")
            except Exception as e:
                print(f"  FAILED: {e}")
                candles_cache[sym] = []
    print(f"fetch took {time.time()-t0:.0f}s\n")

    results = []
    for hyp_name, (key, h_func) in HYPOTHESES.items():
        print(f"\n=== {hyp_name} (uses {key}) ===")
        for sym in SYMBOLS:
            if not funding_cache.get(sym) or not candles_cache.get(sym):
                continue
            closes, aligned_signal, candle_times = align_funding_to_candles(
                funding_cache[sym], candles_cache[sym], key=key
            )
            # drop leading NaNs
            valid = ~np.isnan(aligned_signal)
            if np.sum(valid) < 200:
                print(f"  {sym}: not enough aligned data ({np.sum(valid)})")
                continue
            fired, direction = h_func(closes, aligned_signal, candle_times)
            n_fired = int(np.sum(fired))
            if n_fired < 20:
                print(f"  {sym:5} fired={n_fired} too few")
                results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "passed_to": "fire", "reason": "too few fires"})
                continue

            # Best horizon by t-stat
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
                print(f"  {sym:5} fired={n_fired:4} h={best_h} G1✓ (t={best_g1['t_stat']:.2f} eff={best_g1['mean_pct']:+.3f}%) G2✗ IS={g2.get('is_mean_pct',0):+.3f}% OOS={g2.get('oos_mean_pct',0):+.3f}%")
                results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "best_h": best_h, "g1": best_g1, "g2": g2, "passed_to": "Gate 1"})
                continue

            g3 = gate3(closes, fired, direction, best_h)
            if not g3["pass"]:
                print(f"  {sym:5} fired={n_fired:4} h={best_h} G1✓ G2✓ G3✗ Sharpe={g3.get('sharpe',0):.2f} cum={g3.get('cumulative_pct',0):+.1f}%")
                results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "best_h": best_h, "g1": best_g1, "g2": g2, "g3": g3, "passed_to": "Gate 2"})
                continue

            g4 = gate4(closes, aligned_signal, h_func, best_h)
            beats = "BEATS_HODL" if g3["beats_hodl"] else f"under_HODL({g3['hodl_pct']:+.1f}%)"
            if not g4["pass"]:
                print(f"  {sym:5} fired={n_fired:4} h={best_h} G1✓ G2✓ G3✓ Sharpe={g3['sharpe']:.2f} {beats} G4✗")
                results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "best_h": best_h, "g1": best_g1, "g2": g2, "g3": g3, "g4": g4, "passed_to": "Gate 3"})
                continue

            print(f"  {sym:5} fired={n_fired:4} h={best_h} ★ALL GATES PASS★ Sharpe={g3['sharpe']:.2f} cum={g3['cumulative_pct']:+.1f}% {beats}")
            results.append({"hypothesis": hyp_name, "symbol": sym, "n_fired": n_fired, "best_h": best_h, "g1": best_g1, "g2": g2, "g3": g3, "g4": g4, "passed_to": "Gate 4"})

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")

    # Summary
    lines = ["# Phase 6: Funding/Premium Edge Provenance"]
    lines.append(f"\n4 hypotheses × 7 symbols × 4h timeframe = 28 cells.")
    lines.append(f"\n**Round-trip cost**: {ROUND_TRIP_BPS} bps. **Forward horizons**: {FORWARD_HORIZONS} 4h-bars (= 4h, 12h, 24h, 48h).\n")

    by_gate = defaultdict(list)
    for r in results:
        by_gate[r["passed_to"]].append(r)

    lines.append("## Verdict counts")
    lines.append("| Gate reached | Count |")
    lines.append("|---|---|")
    for g in ["Gate 4", "Gate 3", "Gate 2", "Gate 1", "fire"]:
        lines.append(f"| Passed through {g} | {len(by_gate[g])} |")

    survivors = by_gate["Gate 4"]
    lines.append(f"\n## Survivors ({len(survivors)} cells passed all 4 gates)")
    if survivors:
        lines.append("| hypothesis | sym | n | h | mean% | t-stat | Sharpe | cum% | HODL% | beats |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in sorted(survivors, key=lambda x: -x["g3"]["sharpe"]):
            g1, g3 = r["g1"], r["g3"]
            beats = "✓" if g3["beats_hodl"] else "✗"
            lines.append(f"| {r['hypothesis']} | {r['symbol']} | {g1['n']} | {r['best_h']} | {g1['mean_pct']:+.3f} | {g1['t_stat']:.2f} | {g3['sharpe']:.2f} | {g3['cumulative_pct']:+.1f} | {g3['hodl_pct']:+.1f} | {beats} |")
    else:
        lines.append("\n**No cells passed all 4 gates.**\n")

    g1_passers = [r for r in results if r.get("g1") and r["g1"]["pass"]]
    lines.append(f"\n## Cells that passed Gate 1 (statistical signal exists, n={len(g1_passers)})")
    if g1_passers:
        lines.append("| hypothesis | sym | n | h | mean% | t-stat | reached_gate |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in sorted(g1_passers, key=lambda x: -x["g1"]["t_stat"]):
            g1 = r["g1"]
            lines.append(f"| {r['hypothesis']} | {r['symbol']} | {g1['n']} | {r['best_h']} | {g1['mean_pct']:+.3f} | {g1['t_stat']:.2f} | {r['passed_to']} |")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"wrote {OUT_SUMMARY}")
    print(f"\ntotal: {time.time()-t0:.0f}s")
    print(f"survivors: {len(survivors)}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
