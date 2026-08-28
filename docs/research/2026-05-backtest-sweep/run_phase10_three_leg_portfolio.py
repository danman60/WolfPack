"""Phase 10: 3-leg regime-routed portfolio backtest, last 90 days.

Architecture:
  - Regime classifier: BULL (+10%/30d AND price>SMA200), BEAR (-10% AND <SMA200), else SIDEWAYS
  - Leg 1 (sideways harvester): funding-z < -2 → long, exit on ATR-trail/SL/TP
  - Leg 2 (trend rider): on BULL regime entry → long, ladder profits at +5%/+10%/+20%, trail rest
  - Leg 3 (downtrend follower): on BEAR regime entry → short, same ladder inverted

Each leg has its own equity sleeve (1/3 of total). They run independently.

Test: last 540 bars (90 days × 6 4h-bars). Use prior 28mo for indicator warmup.

Compare 3-leg portfolio to:
  - HODL of the same symbol
  - 200-SMA simple timing (long when above, flat when below)
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

TEST_BARS = 540  # last 90 days at 4h
SLEEVE_PER_LEG = 1.0 / 3.0  # equal capital weight

OUT_DIR = Path(__file__).parent
OUT_RESULTS = OUT_DIR / "phase10_three_leg.json"
OUT_SUMMARY = OUT_DIR / "phase10_three_leg.md"


# ---------- data ----------
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


# ---------- indicators ----------
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


def atr_series(highs, lows, closes, period=14):
    n = len(closes)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
    out = np.full(n, np.nan)
    for i in range(period, n):
        out[i] = np.mean(tr[i - period : i])
    return out


def classify_regime(closes, lookback=180):
    """Return per-bar regime: BULL/SIDEWAYS/BEAR/UNKNOWN."""
    n = len(closes)
    s200 = sma(closes, 200)
    r30 = returns_n_bars(closes, lookback)
    out = ["UNKNOWN"] * n
    for i in range(max(200, lookback), n):
        if np.isnan(s200[i]) or np.isnan(r30[i]):
            continue
        if r30[i] > 0.10 and closes[i] > s200[i]:
            out[i] = "BULL"
        elif r30[i] < -0.10 and closes[i] < s200[i]:
            out[i] = "BEAR"
        else:
            out[i] = "SIDEWAYS"
    return out


# ---------- Leg 1: sideways harvester ----------
def simulate_leg1(closes, highs, lows, funding_z, test_start, test_end, sleeve_equity=1.0,
                  sl_pct=3.0, tp_pct=2.0, max_hold=12, threshold=-2.0, trade_pct=0.10):
    """Enter long when funding_z < threshold. Exit on first of {SL, TP, time-stop}.
    Trades only opened in [test_start, test_end). Position size = trade_pct of sleeve."""
    n = len(closes)
    equity = sleeve_equity
    equity_curve = np.full(n, np.nan)
    equity_curve[test_start] = equity
    trades = []
    in_position_until = -1
    for i in range(test_start, test_end):
        if in_position_until > i:
            equity_curve[i] = equity
            continue
        equity_curve[i] = equity
        if i + max_hold >= n: continue
        if np.isnan(funding_z[i]) or funding_z[i] >= threshold: continue

        entry = closes[i]
        sl = entry * (1 - sl_pct / 100)
        tp = entry * (1 + tp_pct / 100)
        exit_idx, exit_price, reason = None, None, None
        for j in range(1, max_hold + 1):
            b = i + j
            if b >= n: break
            if lows[b] <= sl: exit_idx, exit_price, reason = b, sl, "stop"; break
            if highs[b] >= tp: exit_idx, exit_price, reason = b, tp, "tp"; break
        if exit_idx is None:
            exit_idx = min(i + max_hold, n - 1)
            exit_price = closes[exit_idx]
            reason = "time"
        gross = (exit_price - entry) / entry
        net = gross - COST_PCT
        equity += equity * trade_pct * net
        trades.append({"leg": "L1", "entry": i, "exit": exit_idx, "ret": net, "reason": reason})
        in_position_until = exit_idx
    # forward-fill
    for i in range(test_start + 1, test_end):
        if np.isnan(equity_curve[i]): equity_curve[i] = equity_curve[i - 1]
    return trades, equity_curve, equity


# ---------- Leg 2: trend rider with profit ladder ----------
def simulate_leg2(closes, highs, lows, regimes, test_start, test_end, sleeve_equity=1.0,
                  trade_pct=0.20, ladder=[(0.05, 0.25), (0.10, 0.25), (0.20, 0.25)],
                  trail_atr_mult=3.0, atr_arr=None):
    """Enter long on regime transition into BULL. Take ladder profits, trail last 25%.
    Exit fully when regime != BULL or chandelier stop hit."""
    n = len(closes)
    equity = sleeve_equity
    equity_curve = np.full(n, np.nan)
    equity_curve[test_start] = equity
    trades = []
    in_position = False
    entry_price = None
    remaining_size = 0  # fraction of trade_pct still open
    ladder_hit = [False] * len(ladder)
    trail_high = None
    entry_idx = None

    for i in range(test_start, test_end):
        equity_curve[i] = equity
        prev_reg = regimes[i - 1] if i > 0 else "UNKNOWN"
        cur_reg = regimes[i]

        # Entry: regime transitions into BULL
        if not in_position and cur_reg == "BULL" and prev_reg != "BULL":
            entry_price = closes[i]
            entry_idx = i
            remaining_size = 1.0
            ladder_hit = [False] * len(ladder)
            trail_high = closes[i]
            in_position = True
            continue

        if in_position:
            cur = closes[i]
            trail_high = max(trail_high, highs[i])
            atr_now = atr_arr[i] if atr_arr is not None and not np.isnan(atr_arr[i]) else cur * 0.02

            # Hard exit: regime flipped
            if cur_reg != "BULL":
                gross = (cur - entry_price) / entry_price
                net = gross - COST_PCT
                equity += equity * trade_pct * remaining_size * net
                trades.append({"leg": "L2", "entry": entry_idx, "exit": i, "ret": net, "reason": "regime_exit", "size_remaining": remaining_size})
                in_position = False
                continue

            # Chandelier trailing stop: trail_high - 3*ATR
            chand_stop = trail_high - trail_atr_mult * atr_now
            if lows[i] <= chand_stop:
                gross = (chand_stop - entry_price) / entry_price
                net = gross - COST_PCT
                equity += equity * trade_pct * remaining_size * net
                trades.append({"leg": "L2", "entry": entry_idx, "exit": i, "ret": net, "reason": "chandelier", "size_remaining": remaining_size})
                in_position = False
                continue

            # Ladder profit-taking
            for k, (target_pct, scale_out) in enumerate(ladder):
                if ladder_hit[k]: continue
                if highs[i] >= entry_price * (1 + target_pct):
                    fill_price = entry_price * (1 + target_pct)
                    gross = target_pct
                    net = gross - COST_PCT
                    equity += equity * trade_pct * scale_out * net
                    trades.append({"leg": "L2", "entry": entry_idx, "exit": i, "ret": net, "reason": f"ladder_{target_pct*100:.0f}", "size_remaining": scale_out})
                    remaining_size -= scale_out
                    ladder_hit[k] = True

    # final force-close
    if in_position:
        final_idx = test_end - 1
        cur = closes[final_idx]
        gross = (cur - entry_price) / entry_price
        net = gross - COST_PCT
        equity += equity * trade_pct * remaining_size * net
        trades.append({"leg": "L2", "entry": entry_idx, "exit": final_idx, "ret": net, "reason": "end_of_data", "size_remaining": remaining_size})

    for i in range(test_start + 1, test_end):
        if np.isnan(equity_curve[i]): equity_curve[i] = equity_curve[i - 1]
    return trades, equity_curve, equity


# ---------- Leg 3: bear follower ----------
def simulate_leg3(closes, highs, lows, regimes, test_start, test_end, sleeve_equity=1.0,
                  trade_pct=0.20, ladder=[(0.05, 0.25), (0.10, 0.25), (0.20, 0.25)],
                  trail_atr_mult=3.0, atr_arr=None):
    """Mirror of Leg 2: short on BEAR regime entry, ladder profits as price drops, trail rest."""
    n = len(closes)
    equity = sleeve_equity
    equity_curve = np.full(n, np.nan)
    equity_curve[test_start] = equity
    trades = []
    in_position = False
    entry_price = None
    remaining_size = 0
    ladder_hit = [False] * len(ladder)
    trail_low = None
    entry_idx = None

    for i in range(test_start, test_end):
        equity_curve[i] = equity
        prev_reg = regimes[i - 1] if i > 0 else "UNKNOWN"
        cur_reg = regimes[i]

        if not in_position and cur_reg == "BEAR" and prev_reg != "BEAR":
            entry_price = closes[i]
            entry_idx = i
            remaining_size = 1.0
            ladder_hit = [False] * len(ladder)
            trail_low = closes[i]
            in_position = True
            continue

        if in_position:
            cur = closes[i]
            trail_low = min(trail_low, lows[i])
            atr_now = atr_arr[i] if atr_arr is not None and not np.isnan(atr_arr[i]) else cur * 0.02

            if cur_reg != "BEAR":
                gross = (entry_price - cur) / entry_price
                net = gross - COST_PCT
                equity += equity * trade_pct * remaining_size * net
                trades.append({"leg": "L3", "entry": entry_idx, "exit": i, "ret": net, "reason": "regime_exit", "size_remaining": remaining_size})
                in_position = False
                continue

            chand_stop = trail_low + trail_atr_mult * atr_now
            if highs[i] >= chand_stop:
                gross = (entry_price - chand_stop) / entry_price
                net = gross - COST_PCT
                equity += equity * trade_pct * remaining_size * net
                trades.append({"leg": "L3", "entry": entry_idx, "exit": i, "ret": net, "reason": "chandelier", "size_remaining": remaining_size})
                in_position = False
                continue

            for k, (target_pct, scale_out) in enumerate(ladder):
                if ladder_hit[k]: continue
                if lows[i] <= entry_price * (1 - target_pct):
                    gross = target_pct
                    net = gross - COST_PCT
                    equity += equity * trade_pct * scale_out * net
                    trades.append({"leg": "L3", "entry": entry_idx, "exit": i, "ret": net, "reason": f"ladder_{target_pct*100:.0f}", "size_remaining": scale_out})
                    remaining_size -= scale_out
                    ladder_hit[k] = True

    if in_position:
        final_idx = test_end - 1
        cur = closes[final_idx]
        gross = (entry_price - cur) / entry_price
        net = gross - COST_PCT
        equity += equity * trade_pct * remaining_size * net
        trades.append({"leg": "L3", "entry": entry_idx, "exit": final_idx, "ret": net, "reason": "end_of_data", "size_remaining": remaining_size})

    for i in range(test_start + 1, test_end):
        if np.isnan(equity_curve[i]): equity_curve[i] = equity_curve[i - 1]
    return trades, equity_curve, equity


# ---------- baselines ----------
def hodl_baseline(closes, test_start, test_end):
    return (closes[test_end - 1] - closes[test_start]) / closes[test_start]


def sma200_timing_baseline(closes, test_start, test_end):
    """Long when close > SMA200, flat otherwise. No leverage."""
    s200 = sma(closes, 200)
    equity = 1.0
    holding = False
    entry_price = None
    for i in range(test_start, test_end):
        if np.isnan(s200[i]): continue
        above = closes[i] > s200[i]
        if not holding and above:
            entry_price = closes[i]; holding = True
        elif holding and not above:
            equity *= (closes[i] / entry_price)
            holding = False
    if holding:
        equity *= (closes[test_end - 1] / entry_price)
    return equity - 1.0


# ---------- main ----------
async def main():
    t0 = time.time()
    print("Phase 10 — 3-leg regime portfolio, last 90 days\n")

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
        regimes = classify_regime(closes, 180)
        atr = atr_series(highs, lows, closes, 14)

        test_start = max(0, n - TEST_BARS)
        test_end = n

        # Regime distribution in test window
        reg_counts = defaultdict(int)
        for i in range(test_start, test_end):
            reg_counts[regimes[i]] += 1

        # Each leg gets 1/3 of $1 starting capital (reported as % return on its sleeve)
        l1_trades, l1_eq, l1_final = simulate_leg1(closes, highs, lows, funding_z, test_start, test_end, sleeve_equity=1.0)
        l2_trades, l2_eq, l2_final = simulate_leg2(closes, highs, lows, regimes, test_start, test_end, sleeve_equity=1.0, atr_arr=atr)
        l3_trades, l3_eq, l3_final = simulate_leg3(closes, highs, lows, regimes, test_start, test_end, sleeve_equity=1.0, atr_arr=atr)

        # Combined portfolio: equal-weight 1/3 each
        portfolio_return = (l1_final + l2_final + l3_final) / 3.0 - 1.0  # as fraction
        l1_ret = l1_final - 1
        l2_ret = l2_final - 1
        l3_ret = l3_final - 1

        hodl_ret = hodl_baseline(closes, test_start, test_end)
        sma_timing_ret = sma200_timing_baseline(closes, test_start, test_end)

        results[sym] = {
            "test_bars": test_end - test_start,
            "regime_dist": dict(reg_counts),
            "leg1": {"trades": len(l1_trades), "ret_pct": l1_ret * 100},
            "leg2": {"trades": len(l2_trades), "ret_pct": l2_ret * 100},
            "leg3": {"trades": len(l3_trades), "ret_pct": l3_ret * 100},
            "portfolio_ret_pct": portfolio_return * 100,
            "hodl_ret_pct": hodl_ret * 100,
            "sma200_timing_ret_pct": sma_timing_ret * 100,
            "beats_hodl": portfolio_return > hodl_ret,
            "beats_sma_timing": portfolio_return > sma_timing_ret,
        }

        print(f"\n=== {sym} ===")
        print(f"  regime dist: {dict(reg_counts)}")
        print(f"  L1 (sideways) trades={len(l1_trades):2} ret={l1_ret*100:+6.2f}%")
        print(f"  L2 (bull rider) trades={len(l2_trades):2} ret={l2_ret*100:+6.2f}%")
        print(f"  L3 (bear short) trades={len(l3_trades):2} ret={l3_ret*100:+6.2f}%")
        print(f"  portfolio (1/3 each): {portfolio_return*100:+6.2f}%")
        print(f"  HODL:                 {hodl_ret*100:+6.2f}%  beats={portfolio_return > hodl_ret}")
        print(f"  SMA200 timing:        {sma_timing_ret*100:+6.2f}%  beats={portfolio_return > sma_timing_ret}")

    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))

    # Summary
    lines = ["# Phase 10: 3-leg regime portfolio — last 90 days"]
    lines.append(f"\n**Window**: last 540 4h-bars (~90 days). **Cost**: {ROUND_TRIP_BPS} bps round-trip.\n")
    lines.append("**Architecture:**")
    lines.append("- Regime classifier: 30d return + 200-SMA → BULL/SIDEWAYS/BEAR")
    lines.append("- Leg 1: funding-z < -2 → long, exit at first of 3% SL / 2% TP / 48h")
    lines.append("- Leg 2: BULL regime entry → long with profit ladder (+5%/+10%/+20% scale-out 25% each), trail last 25% on 3-ATR chandelier")
    lines.append("- Leg 3: BEAR regime entry → short with mirror ladder")
    lines.append("- Portfolio: equal-weight 1/3 per leg\n")

    lines.append("## Per-symbol results")
    lines.append("| sym | regime dist | L1 (n,ret%) | L2 (n,ret%) | L3 (n,ret%) | Portfolio% | HODL% | SMA200 timing% | beats HODL | beats SMA |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for sym, r in results.items():
        rd = r["regime_dist"]
        rd_str = f"B={rd.get('BULL',0)} S={rd.get('SIDEWAYS',0)} D={rd.get('BEAR',0)} U={rd.get('UNKNOWN',0)}"
        l1 = r["leg1"]; l2 = r["leg2"]; l3 = r["leg3"]
        bh = "✓" if r["beats_hodl"] else "✗"
        bs = "✓" if r["beats_sma_timing"] else "✗"
        lines.append(f"| {sym} | {rd_str} | {l1['trades']},{l1['ret_pct']:+.2f} | {l2['trades']},{l2['ret_pct']:+.2f} | {l3['trades']},{l3['ret_pct']:+.2f} | {r['portfolio_ret_pct']:+.2f} | {r['hodl_ret_pct']:+.2f} | {r['sma200_timing_ret_pct']:+.2f} | {bh} | {bs} |")

    # Aggregate
    n = len(results)
    avg_port = sum(r["portfolio_ret_pct"] for r in results.values()) / n
    avg_hodl = sum(r["hodl_ret_pct"] for r in results.values()) / n
    avg_sma = sum(r["sma200_timing_ret_pct"] for r in results.values()) / n
    n_beats_hodl = sum(1 for r in results.values() if r["beats_hodl"])
    n_beats_sma = sum(1 for r in results.values() if r["beats_sma_timing"])
    lines.append("\n## Aggregate (avg across 7 symbols)")
    lines.append(f"- Portfolio avg return: **{avg_port:+.2f}%**")
    lines.append(f"- HODL avg return: {avg_hodl:+.2f}%")
    lines.append(f"- SMA200 timing avg return: {avg_sma:+.2f}%")
    lines.append(f"- Symbols where portfolio beats HODL: **{n_beats_hodl}/{n}**")
    lines.append(f"- Symbols where portfolio beats SMA200 timing: **{n_beats_sma}/{n}**")

    OUT_SUMMARY.write_text("\n".join(lines))
    print(f"\nwrote {OUT_RESULTS}")
    print(f"wrote {OUT_SUMMARY}")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
