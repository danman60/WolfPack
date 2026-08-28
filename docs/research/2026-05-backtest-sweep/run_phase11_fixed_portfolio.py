"""Phase 11: 3-leg portfolio with three fixes applied.

Fix A: Hysteresis on regime classifier — require 3 consecutive confirming bars
       before flipping. Kills whipsaw exits.

Fix B: Replace Leg 2 ladder + chandelier with simple "hold while BULL true".
       Same for Leg 3 (hold while BEAR true). No artificial upside cap.

Fix C: Leading regime classifier:
       BULL: price > 200-SMA AND 7d return > +2% AND funding > 0
       BEAR: price < 200-SMA AND 7d return < -2% AND funding < 0
       (Earlier than 30d > +10% / 30d < -10%)

Test: same last 90 days. Direct comparison to Phase 10.
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
TEST_BARS = 540
HYSTERESIS_BARS = 3  # require 3 confirming bars

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase11_fixed.json"
OUT_SUMMARY = OUT_DIR / "phase11_fixed.md"


# ---------- data ----------
async def fetch_funding(client, coin, start_ms):
    all_records = []
    cursor = start_ms; backoff = 0.5
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


def align(funding_records, candles):
    funding_records.sort(key=lambda x: x["time"])
    f_t = np.array([r["time"] for r in funding_records])
    f_v = np.array([float(r["fundingRate"]) for r in funding_records])
    closes = np.array([c.close for c in candles], dtype=np.float64)
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows = np.array([c.low for c in candles], dtype=np.float64)
    aligned = np.full(len(candles), np.nan)
    times = np.array([c.timestamp for c in candles])
    for i, t in enumerate(times):
        idx = np.searchsorted(f_t, t, side="right") - 1
        if idx >= 0: aligned[i] = f_v[idx]
    return closes, highs, lows, aligned


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


def classify_regime_leading_with_hysteresis(closes, funding, hysteresis=HYSTERESIS_BARS):
    """Fix C: leading classifier — 7d return + funding sign + 200-SMA position.
       Fix A: hysteresis — 3 confirming bars before flipping."""
    n = len(closes)
    s200 = sma(closes, 200)
    r7 = returns_n_bars(closes, 42)  # 7d × 6 4h-bars/day = 42

    raw = ["UNKNOWN"] * n
    for i in range(max(200, 42), n):
        if np.isnan(s200[i]) or np.isnan(r7[i]) or np.isnan(funding[i]):
            continue
        if closes[i] > s200[i] and r7[i] > 0.02 and funding[i] > 0:
            raw[i] = "BULL"
        elif closes[i] < s200[i] and r7[i] < -0.02 and funding[i] < 0:
            raw[i] = "BEAR"
        else:
            raw[i] = "SIDEWAYS"

    confirmed = ["UNKNOWN"] * n
    current = "UNKNOWN"
    pending = None
    pending_count = 0
    for i in range(n):
        if raw[i] == "UNKNOWN":
            confirmed[i] = current
            continue
        if raw[i] == current:
            confirmed[i] = current
            pending = None; pending_count = 0
        else:
            if pending == raw[i]:
                pending_count += 1
            else:
                pending = raw[i]; pending_count = 1
            if pending_count >= hysteresis:
                current = pending
                pending = None; pending_count = 0
            confirmed[i] = current
    return confirmed, raw


# ---------- Leg 1 unchanged ----------
def simulate_leg1(closes, highs, lows, funding_z, test_start, test_end, sleeve_equity=1.0,
                  sl_pct=3.0, tp_pct=2.0, max_hold=12, threshold=-2.0, trade_pct=0.10):
    n = len(closes); equity = sleeve_equity; equity_curve = np.full(n, np.nan); trades = []
    in_pos_until = -1
    for i in range(test_start, test_end):
        if in_pos_until > i: equity_curve[i] = equity; continue
        equity_curve[i] = equity
        if i + max_hold >= n: continue
        if np.isnan(funding_z[i]) or funding_z[i] >= threshold: continue
        entry = closes[i]; sl = entry * (1 - sl_pct/100); tp = entry * (1 + tp_pct/100)
        ex_idx, ex_p, reason = None, None, None
        for j in range(1, max_hold + 1):
            b = i + j
            if b >= n: break
            if lows[b] <= sl: ex_idx, ex_p, reason = b, sl, "stop"; break
            if highs[b] >= tp: ex_idx, ex_p, reason = b, tp, "tp"; break
        if ex_idx is None:
            ex_idx = min(i + max_hold, n - 1); ex_p = closes[ex_idx]; reason = "time"
        net = ((ex_p - entry) / entry) - COST_PCT
        equity += equity * trade_pct * net
        trades.append({"entry": i, "exit": ex_idx, "ret": net, "reason": reason})
        in_pos_until = ex_idx
    for i in range(test_start + 1, test_end):
        if np.isnan(equity_curve[i]): equity_curve[i] = equity_curve[i - 1]
    return trades, equity_curve, equity


# ---------- Leg 2 simplified: hold while BULL ----------
def simulate_leg2_hold(closes, highs, lows, regimes, test_start, test_end, sleeve_equity=1.0, trade_pct=1.0):
    """Enter long on first BULL bar, exit on first non-BULL bar (post-hysteresis)."""
    n = len(closes); equity = sleeve_equity; equity_curve = np.full(n, np.nan); trades = []
    in_pos = False; entry_price = None; entry_idx = None
    for i in range(test_start, test_end):
        equity_curve[i] = equity
        if not in_pos and regimes[i] == "BULL":
            entry_price = closes[i]; entry_idx = i; in_pos = True
            continue
        if in_pos:
            if regimes[i] != "BULL":
                cur = closes[i]
                gross = (cur - entry_price) / entry_price
                net = gross - COST_PCT
                equity += equity * trade_pct * net
                trades.append({"entry": entry_idx, "exit": i, "ret": net, "reason": "regime_exit"})
                in_pos = False
                continue
            # mark-to-market for equity curve
            cur = closes[i]
            unrealized = (cur - entry_price) / entry_price
            equity_curve[i] = equity * (1 + trade_pct * unrealized)
    if in_pos:
        ei = test_end - 1
        cur = closes[ei]; gross = (cur - entry_price) / entry_price; net = gross - COST_PCT
        equity += equity * trade_pct * net
        trades.append({"entry": entry_idx, "exit": ei, "ret": net, "reason": "end_of_data"})
        equity_curve[ei] = equity
    for i in range(test_start + 1, test_end):
        if np.isnan(equity_curve[i]): equity_curve[i] = equity_curve[i - 1]
    return trades, equity_curve, equity


# ---------- Leg 3 simplified: hold while BEAR ----------
def simulate_leg3_hold(closes, highs, lows, regimes, test_start, test_end, sleeve_equity=1.0, trade_pct=1.0):
    n = len(closes); equity = sleeve_equity; equity_curve = np.full(n, np.nan); trades = []
    in_pos = False; entry_price = None; entry_idx = None
    for i in range(test_start, test_end):
        equity_curve[i] = equity
        if not in_pos and regimes[i] == "BEAR":
            entry_price = closes[i]; entry_idx = i; in_pos = True
            continue
        if in_pos:
            if regimes[i] != "BEAR":
                cur = closes[i]
                gross = (entry_price - cur) / entry_price
                net = gross - COST_PCT
                equity += equity * trade_pct * net
                trades.append({"entry": entry_idx, "exit": i, "ret": net, "reason": "regime_exit"})
                in_pos = False
                continue
            cur = closes[i]
            unrealized = (entry_price - cur) / entry_price
            equity_curve[i] = equity * (1 + trade_pct * unrealized)
    if in_pos:
        ei = test_end - 1
        cur = closes[ei]; gross = (entry_price - cur) / entry_price; net = gross - COST_PCT
        equity += equity * trade_pct * net
        trades.append({"entry": entry_idx, "exit": ei, "ret": net, "reason": "end_of_data"})
        equity_curve[ei] = equity
    for i in range(test_start + 1, test_end):
        if np.isnan(equity_curve[i]): equity_curve[i] = equity_curve[i - 1]
    return trades, equity_curve, equity


def hodl_baseline(closes, test_start, test_end):
    return (closes[test_end - 1] - closes[test_start]) / closes[test_start]


def sma200_timing_baseline(closes, test_start, test_end):
    s200 = sma(closes, 200)
    eq = 1.0; holding = False; ep = None
    for i in range(test_start, test_end):
        if np.isnan(s200[i]): continue
        above = closes[i] > s200[i]
        if not holding and above:
            ep = closes[i]; holding = True
        elif holding and not above:
            eq *= (closes[i] / ep); holding = False
    if holding: eq *= (closes[test_end - 1] / ep)
    return eq - 1.0


async def main():
    t0 = time.time()
    print("Phase 11 — fixed 3-leg portfolio (Fixes A+B+C), last 90 days\n")

    funding_cache, candles_cache = {}, {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            print(f"fetching {sym}...")
            funding_cache[sym] = await fetch_funding(client, sym, 1704067200000)
            await asyncio.sleep(2)
            candles_cache[sym] = await fetch_candles(client, sym)
            print(f"  funding={len(funding_cache[sym])} candles={len(candles_cache[sym])}")
    print(f"fetch took {time.time()-t0:.0f}s\n")

    results = {}
    for sym in SYMBOLS:
        if not funding_cache.get(sym) or not candles_cache.get(sym): continue
        closes, highs, lows, funding = align(funding_cache[sym], candles_cache[sym])
        n = len(closes)
        if n < 250: continue
        funding_z = rolling_zscore(funding, 180)
        regimes, raw_regimes = classify_regime_leading_with_hysteresis(closes, funding)
        test_start = max(0, n - TEST_BARS); test_end = n

        reg_dist = defaultdict(int)
        raw_dist = defaultdict(int)
        for i in range(test_start, test_end):
            reg_dist[regimes[i]] += 1
            raw_dist[raw_regimes[i]] += 1

        # Count regime transitions in test window (post-hysteresis)
        transitions = sum(1 for i in range(test_start+1, test_end) if regimes[i] != regimes[i-1])

        l1_t, _, l1_f = simulate_leg1(closes, highs, lows, funding_z, test_start, test_end, sleeve_equity=1.0)
        l2_t, _, l2_f = simulate_leg2_hold(closes, highs, lows, regimes, test_start, test_end, sleeve_equity=1.0)
        l3_t, _, l3_f = simulate_leg3_hold(closes, highs, lows, regimes, test_start, test_end, sleeve_equity=1.0)

        portfolio_ret = (l1_f + l2_f + l3_f) / 3.0 - 1.0
        l1_ret = l1_f - 1; l2_ret = l2_f - 1; l3_ret = l3_f - 1
        hodl = hodl_baseline(closes, test_start, test_end)
        sma_t = sma200_timing_baseline(closes, test_start, test_end)

        results[sym] = {
            "regime_dist_post_hysteresis": dict(reg_dist),
            "regime_dist_raw": dict(raw_dist),
            "post_hysteresis_transitions": transitions,
            "leg1": {"trades": len(l1_t), "ret_pct": l1_ret * 100},
            "leg2": {"trades": len(l2_t), "ret_pct": l2_ret * 100},
            "leg3": {"trades": len(l3_t), "ret_pct": l3_ret * 100},
            "portfolio_ret_pct": portfolio_ret * 100,
            "hodl_ret_pct": hodl * 100,
            "sma200_timing_ret_pct": sma_t * 100,
            "beats_hodl": portfolio_ret > hodl,
            "beats_sma_timing": portfolio_ret > sma_t,
        }

        print(f"\n=== {sym} ===")
        print(f"  regime dist (post-hyst): {dict(reg_dist)}")
        print(f"  raw regime dist:         {dict(raw_dist)}")
        print(f"  post-hysteresis transitions: {transitions}  (Phase 10 had ~14-38 transitions)")
        print(f"  L1 (sideways)  trades={len(l1_t):2} ret={l1_ret*100:+6.2f}%")
        print(f"  L2 (BULL hold) trades={len(l2_t):2} ret={l2_ret*100:+6.2f}%")
        print(f"  L3 (BEAR hold) trades={len(l3_t):2} ret={l3_ret*100:+6.2f}%")
        print(f"  portfolio (1/3 each):  {portfolio_ret*100:+6.2f}%")
        print(f"  HODL:                  {hodl*100:+6.2f}%  beats={portfolio_ret > hodl}")
        print(f"  SMA200 timing:         {sma_t*100:+6.2f}%  beats={portfolio_ret > sma_t}")

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))

    lines = ["# Phase 11: 3-leg portfolio with Fixes A+B+C — last 90 days"]
    lines.append(f"\n**Fixes applied:**")
    lines.append("- A: hysteresis — 3 confirming bars to change regime (kills whipsaw)")
    lines.append("- B: Leg 2/3 simplified — hold full position while regime active, no ladder/chandelier")
    lines.append("- C: leading classifier — price>SMA200 + 7d_return>+2% + funding>0 → BULL (mirror for BEAR)")
    lines.append(f"\n**Window**: last 540 4h-bars (90 days). **Cost**: {ROUND_TRIP_BPS} bps round-trip.\n")

    lines.append("## Per-symbol")
    lines.append("| sym | regime dist (hyst) | transitions | L1 % | L2 % | L3 % | Portfolio % | HODL % | SMA200 % | beats HODL | beats SMA |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for sym, r in results.items():
        rd = r["regime_dist_post_hysteresis"]
        rd_str = f"B={rd.get('BULL',0)} S={rd.get('SIDEWAYS',0)} D={rd.get('BEAR',0)} U={rd.get('UNKNOWN',0)}"
        bh = "✓" if r["beats_hodl"] else "✗"; bs = "✓" if r["beats_sma_timing"] else "✗"
        lines.append(f"| {sym} | {rd_str} | {r['post_hysteresis_transitions']} | {r['leg1']['ret_pct']:+.2f} | {r['leg2']['ret_pct']:+.2f} | {r['leg3']['ret_pct']:+.2f} | {r['portfolio_ret_pct']:+.2f} | {r['hodl_ret_pct']:+.2f} | {r['sma200_timing_ret_pct']:+.2f} | {bh} | {bs} |")

    n = len(results)
    avg_port = sum(r["portfolio_ret_pct"] for r in results.values()) / n
    avg_hodl = sum(r["hodl_ret_pct"] for r in results.values()) / n
    avg_sma = sum(r["sma200_timing_ret_pct"] for r in results.values()) / n
    n_bh = sum(1 for r in results.values() if r["beats_hodl"])
    n_bs = sum(1 for r in results.values() if r["beats_sma_timing"])
    lines.append(f"\n## Aggregate")
    lines.append(f"- Portfolio avg: **{avg_port:+.2f}%**")
    lines.append(f"- HODL avg: {avg_hodl:+.2f}%")
    lines.append(f"- SMA200 timing avg: {avg_sma:+.2f}%")
    lines.append(f"- Beats HODL: **{n_bh}/{n}**")
    lines.append(f"- Beats SMA200: **{n_bs}/{n}**")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"\nwrote {OUT_RESULTS}")
    print(f"wrote {OUT_SUMMARY}")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
