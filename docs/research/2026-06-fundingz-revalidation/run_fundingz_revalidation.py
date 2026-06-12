"""Funding-z-low (F2) edge revalidation — June 2026.

Re-runs the Phase 6 (docs/research/2026-05-backtest-sweep/run_phase6_funding_edge.py)
F2 gate methodology on the latest available Hyperliquid data, then the Phase 8
regime segmentation, then produces a regime-gated trade list for portfolio assembly.

Differences from Phase 6 (forced, documented):
  - Candles come directly from Hyperliquid candleSnapshot (intel API droplet :8000
    refused connection at run time). HL caps candleSnapshot at the most recent
    ~5000 candles per interval, same effective cap the intel API had (limit=5000).
  - Everything else (z-window, thresholds, gates, costs, horizons) identical.

Research-only. Touches nothing outside docs/research/2026-06-fundingz-revalidation/.
"""

import asyncio
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np

HL_API = "https://api.hyperliquid.xyz/info"
SYMBOLS = ["BTC", "ETH", "SOL", "LINK", "AVAX", "ARB", "DOGE"]  # Phase 6 set (already includes ETH, SOL)
ROUND_TRIP_BPS = 10.0
COST_PCT = ROUND_TRIP_BPS / 10000.0
FORWARD_HORIZONS = [1, 3, 6, 12]  # 4h bars
Z_WINDOW = 180  # 30d of 4h bars
Z_THRESH = -2.0
SL_PCT, TP_PCT, MAX_HOLD = 3.0, 2.0, 12  # Phase 7 best params, used by Phase 8

OUT_DIR = Path(__file__).parent
DATA_DIR = OUT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
OUT_RESULTS = OUT_DIR / "results.json"
OUT_TRADES = OUT_DIR / "trade_list_regime_gated.json"

ORIGINAL_PHASE6 = {  # from phase6_funding_edge.md (2026-05-07 run)
    "BTC": {"n": 143, "best_h": 3, "mean_pct": 0.417, "t_stat": 2.65, "verdict": "ALL GATES PASS"},
    "DOGE": {"n": 147, "best_h": 6, "mean_pct": 1.029, "t_stat": 2.87, "verdict": "ALL GATES PASS"},
    "AVAX": {"n": 219, "best_h": 12, "mean_pct": 1.019, "t_stat": 2.48, "verdict": "Gate 1 only"},
    "LINK": {"n": 156, "best_h": 6, "mean_pct": 0.704, "t_stat": 2.13, "verdict": "Gate 1 only"},
}


# ---------------- data fetch ----------------
async def fetch_funding_history(client, coin, start_ms):
    all_records, cursor, backoff = [], start_ms, 0.5
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
        if len(all_records) > 60000: break
        await asyncio.sleep(0.25)
    seen, out = set(), []
    for rec in all_records:
        if rec["time"] in seen: continue
        seen.add(rec["time"]); out.append(rec)
    out.sort(key=lambda x: x["time"])
    return out


async def fetch_candles_hl(client, coin, start_ms, end_ms):
    r = await client.post(HL_API, json={
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": "4h", "startTime": start_ms, "endTime": end_ms},
    }, timeout=120)
    r.raise_for_status()
    raw = r.json()
    return [{
        "timestamp": c["t"],
        "open": float(c["o"]), "high": float(c["h"]),
        "low": float(c["l"]), "close": float(c["c"]),
    } for c in raw]


async def get_all_data():
    start_ms = 1704067200000  # 2024-01-01 UTC, same as Phase 6
    end_ms = int(time.time() * 1000)
    funding, candles, counts = {}, {}, {}
    async with httpx.AsyncClient() as client:
        for sym in SYMBOLS:
            fpath = DATA_DIR / f"funding_{sym}.json"
            cpath = DATA_DIR / f"candles_{sym}.json"
            if fpath.exists():
                funding[sym] = json.loads(fpath.read_text())
            else:
                print(f"fetching {sym} funding...", flush=True)
                funding[sym] = await fetch_funding_history(client, sym, start_ms)
                fpath.write_text(json.dumps(funding[sym]))
                await asyncio.sleep(1.5)
            if cpath.exists():
                candles[sym] = json.loads(cpath.read_text())
            else:
                print(f"fetching {sym} candles...", flush=True)
                candles[sym] = await fetch_candles_hl(client, sym, start_ms, end_ms)
                cpath.write_text(json.dumps(candles[sym]))
                await asyncio.sleep(1.0)
            counts[sym] = {
                "funding_records": len(funding[sym]),
                "candles": len(candles[sym]),
                "funding_first": iso(funding[sym][0]["time"]) if funding[sym] else None,
                "funding_last": iso(funding[sym][-1]["time"]) if funding[sym] else None,
                "candle_first": iso(candles[sym][0]["timestamp"]) if candles[sym] else None,
                "candle_last": iso(candles[sym][-1]["timestamp"]) if candles[sym] else None,
            }
            print(f"  {sym}: funding={counts[sym]['funding_records']} candles={counts[sym]['candles']} "
                  f"({counts[sym]['candle_first']} -> {counts[sym]['candle_last']})", flush=True)
    return funding, candles, counts


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------- Phase 6 machinery (identical math) ----------------
def align(funding_records, candles):
    funding_records = sorted(funding_records, key=lambda x: x["time"])
    f_t = np.array([r["time"] for r in funding_records])
    f_v = np.array([float(r["fundingRate"]) for r in funding_records])
    closes = np.array([c["close"] for c in candles], dtype=np.float64)
    highs = np.array([c["high"] for c in candles], dtype=np.float64)
    lows = np.array([c["low"] for c in candles], dtype=np.float64)
    times = np.array([c["timestamp"] for c in candles])
    aligned = np.full(len(candles), np.nan)
    for i, t in enumerate(times):
        idx = np.searchsorted(f_t, t, side="right") - 1
        if idx >= 0:
            aligned[i] = f_v[idx]
    return closes, highs, lows, aligned, times


def rolling_zscore(arr, window=Z_WINDOW):
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        w = arr[i - window:i]
        w = w[~np.isnan(w)]
        if len(w) < window // 2: continue
        mu, sigma = np.mean(w), np.std(w, ddof=1)
        if sigma > 0:
            out[i] = (arr[i] - mu) / sigma
    return out


def forward_rets(closes, fired, horizon, mask=None):
    n = len(closes)
    rets, idxs = [], []
    for i in range(n - horizon):
        if not fired[i]: continue
        if mask is not None and not mask[i]: continue
        rets.append((closes[i + horizon] - closes[i]) / closes[i])  # long-only (direction=+1)
        idxs.append(i)
    return np.array(rets), idxs


def gate1(closes, fired, horizon):
    rets, _ = forward_rets(closes, fired, horizon)
    if len(rets) < 30:
        return {"pass": False, "n": int(len(rets)), "reason": f"n={len(rets)}<30"}
    m, s = float(np.mean(rets)), float(np.std(rets, ddof=1))
    if s == 0: return {"pass": False, "n": int(len(rets)), "reason": "zero stddev"}
    t_stat = m / (s / math.sqrt(len(rets)))
    ok = t_stat > 2.0 and abs(m) > COST_PCT and m > 0
    return {"pass": bool(ok), "n": int(len(rets)), "mean_pct": m * 100, "t_stat": t_stat,
            "stddev_pct": s * 100,
            "reason": None if ok else f"t={t_stat:.2f} eff={m*100:+.3f}% dir={m>0}"}


def gate2(closes, fired, horizon, split=0.7):
    n = len(closes)
    cutoff = int(n * split)
    is_mask = np.zeros(n, bool); is_mask[:cutoff] = True
    oos_mask = ~is_mask
    is_rets, _ = forward_rets(closes, fired, horizon, mask=is_mask)
    oos_rets, _ = forward_rets(closes, fired, horizon, mask=oos_mask)
    if len(is_rets) < 15 or len(oos_rets) < 15:
        return {"pass": False, "is_n": int(len(is_rets)), "oos_n": int(len(oos_rets)), "reason": "too few"}
    is_m, oos_m = float(np.mean(is_rets)), float(np.mean(oos_rets))
    same = (is_m > 0 and oos_m > 0) or (is_m < 0 and oos_m < 0)
    meaningful = abs(oos_m) >= 0.5 * abs(is_m) if is_m != 0 else False
    return {"pass": bool(same and meaningful and oos_m > 0),
            "is_n": int(len(is_rets)), "is_mean_pct": is_m * 100,
            "oos_n": int(len(oos_rets)), "oos_mean_pct": oos_m * 100}


def gate3(closes, fired, horizon):
    rets, _ = forward_rets(closes, fired, horizon)
    if len(rets) < 30: return {"pass": False, "reason": "too few"}
    net = rets - COST_PCT
    cum = float(np.sum(net) * 100)
    m, s = float(np.mean(net)), float(np.std(net, ddof=1))
    if s == 0: return {"pass": False, "reason": "zero stddev"}
    sharpe = (m / s) * math.sqrt(2190 / horizon)
    hodl = (closes[-1] / closes[0] - 1) * 100
    return {"pass": bool(sharpe > 0.5 and cum > 0), "cumulative_pct": cum, "sharpe": sharpe,
            "hodl_pct": hodl, "beats_hodl": bool(cum > hodl), "n_trades": int(len(rets))}


def gate4(closes, funding_aligned, horizon):
    ok = fail = 0
    for thresh in [-1.6, -2.4]:  # ±20% perturbation, as Phase 6
        z = rolling_zscore(funding_aligned)
        fired_p = z < thresh
        g1 = gate1(closes, fired_p, horizon)
        if g1["pass"]: ok += 1
        else: fail += 1
    return {"pass": bool(ok / (ok + fail) >= 0.5), "ok": ok, "fail": fail}


# ---------------- Phase 8 machinery (identical math) ----------------
def classify_regime(closes, lookback_bars=180):
    n = len(closes)
    regimes = ["UNKNOWN"] * n
    for i in range(lookback_bars, n):
        ret = (closes[i] - closes[i - lookback_bars]) / closes[i - lookback_bars]
        if ret > 0.10: regimes[i] = "BULL"
        elif ret < -0.10: regimes[i] = "BEAR"
        else: regimes[i] = "SIDEWAYS"
    return regimes


def simulate(closes, highs, lows, times, fired, sl_pct=SL_PCT, tp_pct=TP_PCT, max_hold=MAX_HOLD):
    """Phase 8 trade simulator + MAE tracking."""
    n = len(closes)
    trades = []
    in_position_until = -1
    for i in range(n):
        if in_position_until > i: continue
        if not fired[i] or i + max_hold >= n: continue
        entry = closes[i]
        sl_price = entry * (1 - sl_pct / 100.0)
        tp_price = entry * (1 + tp_pct / 100.0)
        exit_idx = exit_price = exit_reason = None
        mae = 0.0  # max adverse excursion, % (negative)
        for j in range(1, max_hold + 1):
            bar = i + j
            mae = min(mae, (lows[bar] - entry) / entry * 100)
            if lows[bar] <= sl_price:
                exit_idx, exit_price, exit_reason = bar, sl_price, "stop"; break
            if highs[bar] >= tp_price:
                exit_idx, exit_price, exit_reason = bar, tp_price, "tp"; break
        if exit_idx is None:
            exit_idx, exit_price, exit_reason = i + max_hold, closes[i + max_hold], "time"
        gross = (exit_price - entry) / entry
        trades.append({
            "entry_idx": i, "exit_idx": exit_idx,
            "entry_ts": iso(int(times[i])), "exit_ts": iso(int(times[exit_idx])),
            "entry_price": float(entry), "exit_price": float(exit_price),
            "gross_ret_pct": gross * 100, "net_ret_pct": (gross - COST_PCT) * 100,
            "exit_reason": exit_reason, "hold_bars": exit_idx - i, "mae_pct": mae,
        })
        in_position_until = exit_idx
    return trades


def aggregate_by_regime(trades, regimes, closes, max_hold=MAX_HOLD):
    by_regime = defaultdict(lambda: {"trades": [], "hodl": []})
    for t in trades:
        by_regime[regimes[t["entry_idx"]]]["trades"].append(t)
    n = len(closes)
    for i in range(n - max_hold):
        reg = regimes[i]
        if reg == "UNKNOWN": continue
        by_regime[reg]["hodl"].append((closes[i + max_hold] - closes[i]) / closes[i] * 100)
    out = {}
    for reg, d in by_regime.items():
        ts = d["trades"]
        if len(ts) < 1: continue
        nets = [t["net_ret_pct"] for t in ts]
        wins = sum(1 for r in nets if r > 0)
        hodl_mean = float(np.mean(d["hodl"])) if d["hodl"] else 0.0
        out[reg] = {
            "n_trades": len(ts), "wins": wins, "wr": wins / len(ts),
            "strat_mean_pct": float(np.mean(nets)), "strat_total_pct": float(np.sum(nets)),
            "hodl_mean_pct_per_window": hodl_mean,
            "edge_vs_hodl_per_trade": float(np.mean(nets)) - hodl_mean,
        }
    return out


def trade_stats(nets, maes):
    nets = np.array(nets)
    if len(nets) == 0:
        return {"n": 0}
    wins = nets[nets > 0]
    losses = nets[nets <= 0]
    pf = float(np.sum(wins) / abs(np.sum(losses))) if len(losses) and np.sum(losses) != 0 else float("inf")
    return {
        "n": int(len(nets)),
        "expectancy_pct": float(np.mean(nets)),
        "total_pct": float(np.sum(nets)),
        "win_rate": float(np.mean(nets > 0)),
        "profit_factor": pf,
        "worst_trade_pct": float(np.min(nets)),
        "best_trade_pct": float(np.max(nets)),
        "max_adverse_excursion_pct": float(np.min(maes)) if len(maes) else None,
        "mean_mae_pct": float(np.mean(maes)) if len(maes) else None,
    }


def monte_carlo(nets, n_sims=10000, seed=42):
    nets = np.array(nets)
    if len(nets) < 5:
        return {"n_sims": 0, "note": "too few trades for MC"}
    rng = np.random.default_rng(seed)
    sims = rng.choice(nets, size=(n_sims, len(nets)), replace=True).sum(axis=1)
    return {
        "n_sims": n_sims,
        "prob_profit": float(np.mean(sims > 0)),
        "p5_total_pct": float(np.percentile(sims, 5)),
        "p50_total_pct": float(np.percentile(sims, 50)),
        "p95_total_pct": float(np.percentile(sims, 95)),
    }


# ---------------- main ----------------
async def main():
    t0 = time.time()
    now_ms = int(time.time() * 1000)
    cut90_ms = now_ms - 90 * 86400 * 1000
    discovery_ms = 1778112000000  # 2026-05-07 00:00 UTC — original Phase 6 run date

    funding, candles, counts = await get_all_data()
    print(f"\nfetch/load took {time.time()-t0:.0f}s\n", flush=True)

    results = {"meta": {
        "run_at": iso(now_ms),
        "symbols": SYMBOLS,
        "z_window_bars": Z_WINDOW, "z_threshold": Z_THRESH,
        "cost_round_trip_bps": ROUND_TRIP_BPS,
        "sim_params": {"sl_pct": SL_PCT, "tp_pct": TP_PCT, "max_hold_bars": MAX_HOLD},
        "candle_source": "hyperliquid candleSnapshot direct (intel API :8000 unreachable at run time)",
        "data_counts": counts,
        "recent90_cutoff": iso(cut90_ms),
        "post_discovery_cutoff": iso(discovery_ms),
    }, "gates": {}, "recent_oos": {}, "regime": {}, "leg_stats": {}}

    all_gated_trades = []

    for sym in SYMBOLS:
        if not funding.get(sym) or not candles.get(sym):
            results["gates"][sym] = {"error": "no data"}
            continue
        closes, highs, lows, fund, times = align(funding[sym], candles[sym])
        if int(np.sum(~np.isnan(fund))) < 200:
            results["gates"][sym] = {"error": "insufficient aligned funding"}
            continue
        z = rolling_zscore(fund)
        fired = z < Z_THRESH
        n_fired = int(np.sum(fired))

        # ---- Part 1: Phase 6 gates on extended window ----
        best_h, best_g1 = None, None
        for h in FORWARD_HORIZONS:
            g1 = gate1(closes, fired, h)
            if g1.get("t_stat") is not None and (best_g1 is None or g1["t_stat"] > best_g1.get("t_stat", -99)):
                best_g1, best_h = g1, h
        gate_rec = {"n_fired": n_fired, "best_h": best_h, "g1": best_g1}
        passed_to = "Gate 1"
        if best_g1 and best_g1["pass"]:
            g2 = gate2(closes, fired, best_h); gate_rec["g2"] = g2
            if g2["pass"]:
                g3 = gate3(closes, fired, best_h); gate_rec["g3"] = g3
                passed_to = "Gate 2"
                if g3["pass"]:
                    g4 = gate4(closes, fund, best_h); gate_rec["g4"] = g4
                    passed_to = "Gate 3"
                    if g4["pass"]:
                        passed_to = "ALL GATES PASS"
        gate_rec["verdict"] = passed_to

        # Also evaluate at the ORIGINAL best horizon for apples-to-apples comparison
        orig = ORIGINAL_PHASE6.get(sym)
        if orig:
            g1_orig_h = gate1(closes, fired, orig["best_h"])
            gate_rec["g1_at_original_h"] = g1_orig_h
            gate_rec["original_phase6"] = orig
        results["gates"][sym] = gate_rec

        # ---- Recent-90d + post-discovery OOS (forward returns at original/best h) ----
        h_eval = orig["best_h"] if orig else best_h
        oos = {}
        for label, cutoff in [("recent_90d", cut90_ms), ("post_discovery_2026-05-07", discovery_ms)]:
            mask = times >= cutoff
            rets, idxs = forward_rets(closes, fired, h_eval, mask=mask)
            oos[label] = {
                "h": h_eval, "n": int(len(rets)),
                "mean_pct": float(np.mean(rets) * 100) if len(rets) else None,
                "total_pct": float(np.sum(rets) * 100) if len(rets) else None,
                "win_rate": float(np.mean(rets > 0)) if len(rets) else None,
                "fire_timestamps": [iso(int(times[i])) for i in idxs],
            }
        results["recent_oos"][sym] = oos

        # ---- Part 2: Phase 8 regime segmentation on extended data ----
        regimes = classify_regime(closes)
        trades_all = simulate(closes, highs, lows, times, fired)
        regime_summary = aggregate_by_regime(trades_all, regimes, closes)
        results["regime"][sym] = {
            "regime_counts": {r: regimes.count(r) for r in set(regimes)},
            "total_trades": len(trades_all),
            "by_regime": regime_summary,
        }

        # ---- Part 3: regime-gated trade list (fire only in SIDEWAYS/BEAR) ----
        gate_mask = np.array([r in ("SIDEWAYS", "BEAR") for r in regimes])
        fired_gated = fired & gate_mask
        trades_gated = simulate(closes, highs, lows, times, fired_gated)
        for t in trades_gated:
            t["symbol"] = sym
            t["regime_at_entry"] = regimes[t["entry_idx"]]
        all_gated_trades.extend(trades_gated)

        # per-symbol gated stats
        nets = [t["net_ret_pct"] for t in trades_gated]
        maes = [t["mae_pct"] for t in trades_gated]
        st = trade_stats(nets, maes)
        st["monte_carlo"] = monte_carlo(nets)
        results["leg_stats"][sym] = st

        print(f"{sym}: fired={n_fired} verdict={passed_to} gated_trades={len(trades_gated)}", flush=True)

    # ---- combined portfolio-leg stats: survivors (BTC+DOGE) and all symbols ----
    for label, syms in [("BTC_DOGE_combined", ["BTC", "DOGE"]), ("all_symbols_combined", SYMBOLS)]:
        ts = [t for t in all_gated_trades if t["symbol"] in syms]
        nets = [t["net_ret_pct"] for t in ts]
        maes = [t["mae_pct"] for t in ts]
        st = trade_stats(nets, maes)
        st["monte_carlo"] = monte_carlo(nets)
        results["leg_stats"][label] = st

    # trade list JSON (sorted by entry time)
    all_gated_trades.sort(key=lambda t: t["entry_ts"])
    trade_list = {
        "description": "F2 funding-z-low long, regime-gated (fires only in SIDEWAYS/BEAR at entry). "
                       "Exit: first of 3% SL / 2% TP / 48h time-stop. Net of 10bps round trip. "
                       "Portfolio leg = filter symbol in ['BTC','DOGE'] (gate survivors).",
        "params": results["meta"]["sim_params"],
        "generated_at": results["meta"]["run_at"],
        "trades": [{
            "symbol": t["symbol"], "entry_ts": t["entry_ts"], "exit_ts": t["exit_ts"],
            "entry_price": t["entry_price"], "exit_price": t["exit_price"],
            "net_pnl_pct": round(t["net_ret_pct"], 4), "gross_pnl_pct": round(t["gross_ret_pct"], 4),
            "exit_reason": t["exit_reason"], "hold_bars": t["hold_bars"],
            "mae_pct": round(t["mae_pct"], 4), "regime_at_entry": t["regime_at_entry"],
        } for t in all_gated_trades],
    }
    OUT_TRADES.write_text(json.dumps(trade_list, indent=2))
    OUT_RESULTS.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_RESULTS}")
    print(f"wrote {OUT_TRADES} ({len(all_gated_trades)} trades)")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
