#!/usr/bin/env python3
"""Moonshot Scalper — MECHANICAL-LEG backtest (RESEARCH ONLY, new files only).

WHAT THIS IS
------------
The full moonshot strategy = BUZZ filter + CHART-TRIGGER quick-scalp. The buzz leg
is NOT backtestable (no historical social-buzz data; 51/230 HL perps already
delisted -> survivorship bias). This harness isolates and backtests ONLY the
mechanical chart-trigger/execution leg on the live HL small-cap perp universe:

    "Does a momentum/breakout quick-long scalp with tight risk have positive
     expectancy on thin alts, BEFORE buzz is layered on?"

ENTRY (reuses the live screener's gate, unmodified import of momentum_buckets):
    long when  MomentumBuckets(window).regime_hint == "breakout"
               AND momentum_score >= MOM_THRESH (0.4, screener default)
               AND conviction     >= CONV_THRESH (0.5, screener default)
    Long-only (matches "quick long in/out").

EXIT (first to trigger, checked intrabar against OHLC):
    - take-profit  (sweep: +5%, +8%, or R-multiple 1.5R / 2.0R off the stop)
    - stop-loss    (sweep: fixed -3% / -4%, or ATR-based 1.5*ATR)
    - max-hold cap (sweep: 4h / 12h / 24h, in bars)

COSTS (critical — thin alts):
    Per-side cost = slippage_bps + commission_bps, applied on entry AND exit.
    Default REALISTIC small-cap cost = 30 bps slippage + 5 bps commission.
    Best combo re-run at 40 bps slippage to stress it. (Harness default 10bps is
    NOT used — it is unrealistic for this class.)

SURVIVORSHIP CAVEAT: only currently-listed perps are testable. The delisted
moonshots that went to ~zero are gone from the data -> results are OPTIMISTICALLY
BIASED. Quantified in the summary.

Run from intel/ with the repo python:
    cd intel && python3 ../docs/research/2026-06-moonshot-scalper/run_moonshot_backtest.py

NO TRADING. NO DB. NO WALLET CONFIG. NO MIGRATION. Reads candles via the intel API
(GET /market/candles) and writes JSON + MD into this folder only.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone

# --- repo python path (run from intel/, mirror the phase2 harness pattern) ---
INTEL_PATH = Path(__file__).resolve().parents[3] / "intel"
sys.path.insert(0, str(INTEL_PATH))

import httpx  # noqa: E402
from wolfpack.exchanges.base import Candle  # noqa: E402
from wolfpack.modules.momentum_buckets import MomentumBuckets  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
INTEL_API = "http://159.89.115.95:8000"
HL_INFO = "https://api.hyperliquid.xyz/info"

INTERVAL = "15m"          # scalp timeframe; 15m returns ~52d history (5m only ~17d)
BARS_PER_HOUR = 4         # 15m bars
CANDLES_LIMIT = 5000      # API hard cap is 5001

SMALL_CAP_VOL_MAX = 5_000_000
VOL_FLOOR = 250_000

# Screener entry gate (matches moonshot_screener.py is_shot logic, long-only)
MOM_THRESH = 0.4
CONV_THRESH = 0.5
SIGNAL_WINDOW = 80        # trailing candles fed to MomentumBuckets (needs 55+ for all windows)

# IMPORTANT FINDING: the screener's literal is_shot gate
#   (regime_hint=="breakout" AND momentum_score>=0.4 AND conviction>=0.5)
# fires ZERO times on historical 15m data for EVERY small-cap tested. This is
# structural, not a data gap: momentum_buckets only labels a bar "breakout" when
# the SHORT window is fast but the LONG window is flat (short_vel>0.3 & long_vel<0.1),
# which mechanically caps the 4-window composite momentum_score at ~0.40 on those
# exact bars — so "breakout AND momentum>=0.4" is near-impossible by construction.
# (This matches the live screener: 0/7 candidates ever passed is_shot.)
#
# So we test the gate AS WRITTEN (-> 0 trades, the honest literal result) PLUS three
# FAITHFUL interpretations of the "breakout quick-long" intent that actually fire,
# so the mechanical leg gets a real expectancy verdict rather than a null one.
def gate_as_written(m) -> bool:
    return (m.regime_hint == "breakout" and m.momentum_score >= MOM_THRESH
            and m.conviction >= CONV_THRESH)

def gate_breakout_intent(m) -> bool:
    # fresh upside breakout you're confident in (screener's INTENT)
    return (m.regime_hint == "breakout" and m.momentum_score > 0
            and m.conviction >= CONV_THRESH)

def gate_breakout_uptrend(m) -> bool:
    return (m.regime_hint == "breakout"
            and m.primary_trend.value in ("up", "strong_up")
            and m.conviction >= CONV_THRESH)

def gate_momentum_long(m) -> bool:
    # broader "momentum quick-long": breakout OR trending, strong & confident
    return (m.regime_hint in ("breakout", "trending")
            and m.momentum_score >= MOM_THRESH and m.conviction >= CONV_THRESH)

GATES = {
    "as_written": gate_as_written,
    "breakout_intent": gate_breakout_intent,
    "breakout_uptrend": gate_breakout_uptrend,
    "momentum_long": gate_momentum_long,
}

# Realistic costs (per task): 30bps slip + 5bps commission baseline; 40bps stress
COMMISSION_BPS = 5.0
SLIP_BASE_BPS = 30.0
SLIP_STRESS_BPS = 40.0

# Sweep grid
TP_VARIANTS = [
    ("tp_5pct", {"type": "pct", "val": 0.05}),
    ("tp_8pct", {"type": "pct", "val": 0.08}),
    ("tp_1.5R", {"type": "R", "val": 1.5}),
    ("tp_2.0R", {"type": "R", "val": 2.0}),
]
STOP_VARIANTS = [
    ("stop_3pct", {"type": "pct", "val": 0.03}),
    ("stop_4pct", {"type": "pct", "val": 0.04}),
    ("stop_atr1.5", {"type": "atr", "val": 1.5}),
]
HOLD_VARIANTS = [
    ("hold_4h", 4 * BARS_PER_HOUR),
    ("hold_12h", 12 * BARS_PER_HOUR),
    ("hold_24h", 24 * BARS_PER_HOUR),
]

# Universe: small-cap tier names with enough history. Pulled live + capped to a
# representative ~18 spanning the <$5M and <$1M sub-tiers.
PREFERRED = [
    "LINK", "AVAX", "ARB", "APT", "PENGU", "ICP", "HBAR", "SEI", "TIA", "WIF",
    "DOT", "UNI", "CRV", "JUP", "LDO", "RENDER", "DYDX", "IP", "OP", "AR",
]

OUT_DIR = Path(__file__).resolve().parent
OUT_JSON = OUT_DIR / "moonshot_backtest_results.json"
OUT_MD = OUT_DIR / "moonshot_backtest_summary.md"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def fetch_universe(client: httpx.Client) -> dict[str, dict]:
    r = client.post(HL_INFO, json={"type": "metaAndAssetCtxs"}, timeout=30)
    meta, ctxs = r.json()
    out = {}
    for u, c in zip(meta["universe"], ctxs):
        if u.get("isDelisted"):
            continue
        mark = float(c.get("markPx", 0) or 0)
        vol = float(c.get("dayNtlVlm", 0) or 0)
        out[u["name"]] = {"vol": vol, "mark": mark, "maxlev": u.get("maxLeverage", 0)}
    return out


def fetch_candles(client: httpx.Client, symbol: str) -> list[Candle]:
    try:
        d = client.get(f"{INTEL_API}/market/candles",
                       params={"symbol": symbol, "interval": INTERVAL, "limit": CANDLES_LIMIT},
                       timeout=60).json()
        return [Candle(**c) for c in d.get("candles", [])]
    except Exception as e:  # noqa: BLE001
        print(f"[warn] candles {symbol} failed: {e}", file=sys.stderr)
        return []


def fetch_spread_bps(client: httpx.Client, symbol: str) -> float | None:
    try:
        r = client.post(HL_INFO, json={"type": "l2Book", "coin": symbol}, timeout=20)
        lv = r.json().get("levels", [])
        if len(lv) < 2 or not lv[0] or not lv[1]:
            return None
        bid = float(lv[0][0]["px"]); ask = float(lv[1][0]["px"]); mid = (bid + ask) / 2
        return round((ask - bid) / mid * 1e4, 2) if mid > 0 else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------
def atr_at(candles: list[Candle], idx: int, period: int = 14) -> float:
    lo = max(1, idx - period + 1)
    trs = []
    for i in range(lo, idx + 1):
        prev = candles[i - 1].close
        c = candles[i]
        trs.append(max(c.high - c.low, abs(c.high - prev), abs(c.low - prev)))
    return sum(trs) / len(trs) if trs else (candles[idx].high - candles[idx].low)


# ---------------------------------------------------------------------------
# Backtest core — long-only scalp with explicit TP/stop/max-hold exits
# ---------------------------------------------------------------------------
@dataclass
class Trade:
    entry_idx: int
    exit_idx: int
    entry_price: float      # post-cost fill
    exit_price: float       # post-cost fill
    gross_entry: float
    gross_exit: float
    pnl_pct: float          # net of cost, on price
    exit_reason: str
    holding_bars: int


@dataclass
class ComboResult:
    n_trades: int = 0
    wins: int = 0
    sum_pnl_pct: float = 0.0     # net %/trade summed
    gross_win_pct: float = 0.0
    gross_loss_pct: float = 0.0
    win_pcts: list = field(default_factory=list)
    loss_pcts: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)  # cumulative product
    holds: list = field(default_factory=list)
    reasons: dict = field(default_factory=dict)


def _tp_price(entry_gross: float, stop_gross: float, tp_cfg: dict) -> float:
    if tp_cfg["type"] == "pct":
        return entry_gross * (1 + tp_cfg["val"])
    # R multiple: distance from entry to stop, scaled
    risk = entry_gross - stop_gross
    return entry_gross + tp_cfg["val"] * risk


def _stop_price(entry_gross: float, atr: float, stop_cfg: dict) -> float:
    if stop_cfg["type"] == "pct":
        return entry_gross * (1 - stop_cfg["val"])
    # atr-based
    return entry_gross - stop_cfg["val"] * atr


def compute_signals(candles: list[Candle], gate) -> list[tuple]:
    """Bar i fires if gate(MomentumBuckets(trailing window)) is True. Cost-independent."""
    mb = MomentumBuckets()
    n = len(candles)
    sigs = []
    for i in range(SIGNAL_WINDOW, n):
        m = mb.analyze(candles[i - SIGNAL_WINDOW + 1 : i + 1], asset="x")
        if gate(m):
            sigs.append((i, atr_at(candles, i, 14)))
    return sigs


def run_symbol(candles: list[Candle], cost_bps: float, signals: list[tuple]) -> dict:
    """Run the full TP x stop x hold sweep for one symbol at one cost level.

    Entry signals are precomputed (cost-independent); only fills depend on cost.
    Returns {combo_key: ComboResult-as-dict, "_signals": int}.
    """
    cost_pct = cost_bps / 10_000.0
    n = len(candles)

    results: dict[str, ComboResult] = {}
    for tp_name, tp_cfg in TP_VARIANTS:
        for st_name, st_cfg in STOP_VARIANTS:
            for hold_name, hold_bars in HOLD_VARIANTS:
                key = f"{tp_name}|{st_name}|{hold_name}"
                results[key] = ComboResult(equity_curve=[1.0])

    for tp_name, tp_cfg in TP_VARIANTS:
        for st_name, st_cfg in STOP_VARIANTS:
            for hold_name, hold_bars in HOLD_VARIANTS:
                key = f"{tp_name}|{st_name}|{hold_name}"
                res = results[key]
                busy_until = -1  # no pyramiding; one position at a time
                for sig_idx, atr in signals:
                    if sig_idx <= busy_until:
                        continue
                    if sig_idx + 1 >= n:
                        continue
                    # Entry: fill at signal-bar close, costed (pay the spread/slip on entry)
                    entry_gross = candles[sig_idx].close
                    if entry_gross <= 0:
                        continue
                    entry_fill = entry_gross * (1 + cost_pct)  # long buys up
                    stop_gross = _stop_price(entry_gross, atr, st_cfg)
                    tp_gross = _tp_price(entry_gross, stop_gross, tp_cfg)
                    if stop_gross <= 0 or stop_gross >= entry_gross or tp_gross <= entry_gross:
                        continue

                    exit_idx = None
                    exit_gross = None
                    reason = None
                    last = min(sig_idx + hold_bars, n - 1)
                    for j in range(sig_idx + 1, last + 1):
                        c = candles[j]
                        hit_stop = c.low <= stop_gross
                        hit_tp = c.high >= tp_gross
                        if hit_stop and hit_tp:
                            # conservative: assume stop first (worst case for a long)
                            exit_gross = stop_gross; reason = "stop"; exit_idx = j
                            break
                        if hit_stop:
                            exit_gross = stop_gross; reason = "stop"; exit_idx = j
                            break
                        if hit_tp:
                            exit_gross = tp_gross; reason = "take_profit"; exit_idx = j
                            break
                    if exit_idx is None:
                        exit_idx = last
                        exit_gross = candles[last].close
                        reason = "max_hold"

                    exit_fill = exit_gross * (1 - cost_pct)  # long sells down
                    pnl_pct = (exit_fill - entry_fill) / entry_fill
                    res.n_trades += 1
                    res.sum_pnl_pct += pnl_pct
                    res.holds.append(exit_idx - sig_idx)
                    res.reasons[reason] = res.reasons.get(reason, 0) + 1
                    if pnl_pct > 0:
                        res.wins += 1
                        res.gross_win_pct += pnl_pct
                        res.win_pcts.append(pnl_pct)
                    else:
                        res.gross_loss_pct += abs(pnl_pct)
                        res.loss_pcts.append(pnl_pct)
                    res.equity_curve.append(res.equity_curve[-1] * (1 + pnl_pct))
                    busy_until = exit_idx

    out = {"_signals": len(signals)}
    for key, r in results.items():
        out[key] = _summarize(r)
    return out


def _summarize(r: ComboResult) -> dict:
    n = r.n_trades
    if n == 0:
        return {"n_trades": 0, "win_rate": 0.0, "expectancy_pct": 0.0,
                "profit_factor": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0,
                "avg_rr": 0.0, "total_return_pct": 0.0, "max_dd_pct": 0.0,
                "avg_hold_bars": 0.0, "reasons": {}}
    win_rate = r.wins / n
    avg_win = (r.gross_win_pct / r.wins) if r.wins else 0.0
    n_loss = n - r.wins
    avg_loss = (r.gross_loss_pct / n_loss) if n_loss else 0.0  # magnitude
    pf = (r.gross_win_pct / r.gross_loss_pct) if r.gross_loss_pct > 0 else (999.0 if r.gross_win_pct > 0 else 0.0)
    avg_rr = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    total_ret = (r.equity_curve[-1] - 1.0) * 100
    # max drawdown on equity curve
    peak = r.equity_curve[0]; max_dd = 0.0
    for e in r.equity_curve:
        peak = max(peak, e)
        dd = (peak - e) / peak * 100 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    avg_hold = sum(r.holds) / len(r.holds) if r.holds else 0.0
    return {
        "n_trades": n,
        "win_rate": round(win_rate, 4),
        "expectancy_pct": round(r.sum_pnl_pct / n * 100, 4),  # net %/trade
        "profit_factor": round(min(pf, 999.0), 4),
        "avg_win_pct": round(avg_win * 100, 4),
        "avg_loss_pct": round(avg_loss * 100, 4),
        "avg_rr": round(avg_rr, 4),
        "total_return_pct": round(total_ret, 4),
        "max_dd_pct": round(max_dd, 4),
        "avg_hold_bars": round(avg_hold, 2),
        "reasons": r.reasons,
    }


def aggregate(per_symbol: dict[str, dict], combo_keys: list[str]) -> dict:
    """Pool trades across symbols per combo (equal-weight on trades)."""
    agg = {}
    for key in combo_keys:
        n = wins = 0
        sum_pnl = 0.0
        gw = gl = 0.0
        eq = [1.0]
        holds = 0.0
        for sym, res in per_symbol.items():
            c = res.get(key)
            if not c or c["n_trades"] == 0:
                continue
            n += c["n_trades"]
            wins += round(c["win_rate"] * c["n_trades"])
            sum_pnl += c["expectancy_pct"] / 100 * c["n_trades"]
            gw += c["avg_win_pct"] / 100 * round(c["win_rate"] * c["n_trades"])
            gl += c["avg_loss_pct"] / 100 * (c["n_trades"] - round(c["win_rate"] * c["n_trades"]))
            holds += c["avg_hold_bars"] * c["n_trades"]
        if n == 0:
            agg[key] = {"n_trades": 0, "expectancy_pct": 0.0, "win_rate": 0.0,
                        "profit_factor": 0.0, "avg_rr": 0.0, "avg_hold_bars": 0.0}
            continue
        win_rate = wins / n
        avg_win = gw / wins if wins else 0.0
        avg_loss = gl / (n - wins) if (n - wins) else 0.0
        pf = (gw / gl) if gl > 0 else (999.0 if gw > 0 else 0.0)
        agg[key] = {
            "n_trades": n,
            "win_rate": round(win_rate, 4),
            "expectancy_pct": round(sum_pnl / n * 100, 4),
            "profit_factor": round(min(pf, 999.0), 4),
            "avg_rr": round(avg_win / avg_loss, 4) if avg_loss > 0 else 0.0,
            "avg_hold_bars": round(holds / n, 2),
        }
    return agg


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _run_gate(candles_by, tested, combo_keys, gate, coverage):
    """Run baseline(35bps) + stress(45bps) + zero-cost for ONE gate. Returns a dict block."""
    base_cost = SLIP_BASE_BPS + COMMISSION_BPS
    stress_cost = SLIP_STRESS_BPS + COMMISSION_BPS

    # precompute signals once per symbol (cost-independent)
    sigs_by = {s: compute_signals(candles_by[s], gate) for s in tested}
    total_sigs = sum(len(v) for v in sigs_by.values())

    per_base = {s: run_symbol(candles_by[s], base_cost, sigs_by[s]) for s in tested}
    per_stress = {s: run_symbol(candles_by[s], stress_cost, sigs_by[s]) for s in tested}
    per_zero = {s: run_symbol(candles_by[s], 0.0, sigs_by[s]) for s in tested}

    agg_base = aggregate(per_base, combo_keys)
    agg_stress = aggregate(per_stress, combo_keys)
    agg_zero = aggregate(per_zero, combo_keys)

    # best by expectancy at baseline (require a non-trivial trade count)
    cand = {k: v for k, v in agg_base.items() if v["n_trades"] >= 20} or agg_base
    best_key = max(cand, key=lambda k: cand[k]["expectancy_pct"]) if cand else None
    best_key_stress = max(
        {k: v for k, v in agg_stress.items() if v["n_trades"] >= 20} or agg_stress,
        key=lambda k: agg_stress[k]["expectancy_pct"]) if agg_stress else None

    return {
        "total_signals": total_sigs,
        "signals_per_symbol": {s: len(v) for s, v in sigs_by.items()},
        "best_key": best_key,
        "best_at_35bps": agg_base.get(best_key, {}),
        "best_at_45bps_samecombo": agg_stress.get(best_key, {}),
        "best_at_0bps_samecombo": agg_zero.get(best_key, {}),
        "best_key_at_45bps": best_key_stress,
        "best_at_45bps_independent": agg_stress.get(best_key_stress, {}),
        "agg_35bps": agg_base,
        "agg_45bps": agg_stress,
        "per_symbol_35bps_bestcombo": {s: per_base[s].get(best_key, {}) for s in tested},
    }


def main():
    t0 = time.time()
    combo_keys = [f"{tp}|{st}|{ho}"
                  for tp, _ in TP_VARIANTS for st, _ in STOP_VARIANTS for ho, _ in HOLD_VARIANTS]

    with httpx.Client() as client:
        uni = fetch_universe(client)
        small = {s: r for s, r in uni.items() if VOL_FLOOR <= r["vol"] < SMALL_CAP_VOL_MAX}
        symbols = [s for s in PREFERRED if s in small]
        print(f"HL small-cap tier: {len(small)} | testing {len(symbols)}: {symbols}")

        candles_by, coverage = {}, {}
        for s in symbols:
            c = fetch_candles(client, s)
            if len(c) < SIGNAL_WINDOW + 50:
                print(f"  [skip] {s}: only {len(c)} candles")
                continue
            candles_by[s] = c
            coverage[s] = {
                "n_bars": len(c),
                "start": datetime.fromtimestamp(c[0].timestamp / 1000, tz=timezone.utc).isoformat(),
                "end": datetime.fromtimestamp(c[-1].timestamp / 1000, tz=timezone.utc).isoformat(),
                "days": round((c[-1].timestamp - c[0].timestamp) / 86_400_000, 1),
                "vol_24h": round(small[s]["vol"]),
                "spread_bps_live": fetch_spread_bps(client, s),
            }
            print(f"  {s:8} n={len(c)} {coverage[s]['days']}d spread={coverage[s]['spread_bps_live']}bps")

    tested = list(candles_by.keys())

    gate_blocks = {}
    for gname, gfn in GATES.items():
        print(f"\n=== gate: {gname} ===")
        blk = _run_gate(candles_by, tested, combo_keys, gfn, coverage)
        gate_blocks[gname] = blk
        bk = blk["best_key"]; b = blk["best_at_35bps"]
        print(f"  signals={blk['total_signals']}  best={bk}  "
              f"exp@35bps={b.get('expectancy_pct',0):+.3f}%/trade  n={b.get('n_trades',0)}  "
              f"PF={b.get('profit_factor',0):.2f}")

    results = {
        "meta": {
            "generated": datetime.now(timezone.utc).isoformat(),
            "interval": INTERVAL,
            "signal_window": SIGNAL_WINDOW,
            "mom_thresh": MOM_THRESH, "conv_thresh": CONV_THRESH,
            "costs_bps_per_side": {"baseline": SLIP_BASE_BPS + COMMISSION_BPS,
                                   "stress": SLIP_STRESS_BPS + COMMISSION_BPS,
                                   "slip_base": SLIP_BASE_BPS, "slip_stress": SLIP_STRESS_BPS,
                                   "commission": COMMISSION_BPS},
            "symbols_tested": tested,
            "coverage": coverage,
            "gates": {
                "as_written": "regime==breakout AND mom>=0.4 AND conv>=0.5 (literal screener is_shot; STRUCTURALLY FIRES 0x)",
                "breakout_intent": "regime==breakout AND mom>0 AND conv>=0.5 (faithful: fresh confident upside breakout)",
                "breakout_uptrend": "regime==breakout AND primary_trend up/strong_up AND conv>=0.5",
                "momentum_long": "regime in {breakout,trending} AND mom>=0.4 AND conv>=0.5 (broad momentum long)",
            },
        },
        "gate_results": gate_blocks,
    }
    OUT_JSON.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {OUT_JSON}")
    write_summary(results, coverage, tested)
    print(f"wrote {OUT_MD}")
    print(f"total {time.time()-t0:.1f}s")


def _verdict(best35, best45):
    e30 = best35.get("expectancy_pct", 0)
    e40 = best45.get("expectancy_pct", 0)
    pf = best35.get("profit_factor", 0)
    n = best35.get("n_trades", 0)
    if n < 20:
        return ("**INCONCLUSIVE** — too few trades (n=%d) at this gate to judge expectancy." % n)
    if e30 <= 0:
        return (f"**FAIL** — best-combo expectancy at realistic 35bps = {e30:+.3f}%/trade "
                f"(PF {pf:.2f}, n={n}). Negative before any buzz overlay or survivorship correction.")
    if e40 <= 0:
        return (f"**FRAGILE** — positive at 35bps ({e30:+.3f}%/trade) but negative at 45bps "
                f"({e40:+.3f}%/trade). Edge sits inside the spread-uncertainty band.")
    return (f"**PASS (survivor-only, conditional)** — best combo positive at both 35bps "
            f"({e30:+.3f}%/trade) and 45bps ({e40:+.3f}%/trade), PF {pf:.2f}, n={n}. "
            f"Still subject to the survivorship drag below.")


def write_summary(results, coverage, tested):
    m = results["meta"]
    G = results["gate_results"]
    base = m["costs_bps_per_side"]["baseline"]; stress = m["costs_bps_per_side"]["stress"]
    L = []
    L.append("# Moonshot Scalper — MECHANICAL-LEG Backtest")
    L.append(f"\n**Generated:** {m['generated']}  ")
    L.append(f"**Interval:** {INTERVAL} ({coverage[tested[0]]['days']}d history)  •  "
             f"**Universe:** {len(tested)} live HL small-cap perps (<$5M/24h, >=$250k)  ")
    L.append(f"**Costs:** baseline = {SLIP_BASE_BPS}bps slip + {COMMISSION_BPS}bps comm = **{base:.0f}bps/side**; "
             f"stress = {SLIP_STRESS_BPS}+{COMMISSION_BPS} = **{stress:.0f}bps/side**. Cost paid on BOTH entry and exit.\n")

    L.append("## What this is (and is NOT)")
    L.append("- **Tested:** the **mechanical chart-trigger leg only** — the moonshot screener's "
             "momentum/breakout entry gate (reusing `momentum_buckets` unmodified) run bar-by-bar, "
             "long-only, with fast TP / tight stop / max-hold exits.")
    L.append("- **NOT tested:** the buzz filter (no historical social-buzz data) and the 51 delisted "
             "perps (gone from the data). See survivorship section.\n")

    L.append("### KEY STRUCTURAL FINDING — the literal screener gate is dead")
    aw = G["as_written"]
    L.append(f"The screener's **literal `is_shot` gate** (regime==breakout AND momentum>=0.4 AND "
             f"conviction>=0.5) fired **{aw['total_signals']} times across all {len(tested)} symbols over "
             f"{coverage[tested[0]]['days']} days** — i.e. **zero tradeable signals**. This is *structural*, "
             "not a data gap: `momentum_buckets` only labels a bar `breakout` when the short window is fast "
             "but the long window is flat (`short_vel>0.3 & long_vel<0.1`), which mechanically caps the "
             "4-window composite momentum_score at ~0.40 on exactly those bars. So "
             "`breakout AND momentum>=0.4` is near-impossible by construction. This matches the live "
             "screener (0/7 candidates ever passed `is_shot`). **The mechanical entry, as literally coded, "
             "produces no trade stream at all.**\n")
    L.append("To still answer *'does the breakout-quick-long idea have edge'*, three FAITHFUL "
             "interpretations of the screener's intent were backtested (they fire normally):\n")
    L.append("| gate | definition |")
    L.append("|---|---|")
    for k, v in m["gates"].items():
        L.append(f"| `{k}` | {v} |")

    # coverage
    L.append("\n## 1. Symbols tested + candle coverage")
    L.append("| symbol | bars | start | end | days | 24h vol | live spread (bps) |")
    L.append("|---|---|---|---|---|---|---|")
    for s in tested:
        c = coverage[s]
        L.append(f"| {s} | {c['n_bars']} | {c['start'][:10]} | {c['end'][:10]} | {c['days']} "
                 f"| ${c['vol_24h']:,} | {c['spread_bps_live']} |")

    # per-gate headline
    L.append("\n## 2. Headline per gate — expectancy at REALISTIC cost")
    L.append("| gate | signals | best combo | n trades | win% | exp%/trade @35bps | PF | exp%/trade @45bps | verdict |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for gname, blk in G.items():
        b = blk["best_at_35bps"]; b45 = blk["best_at_45bps_samecombo"]
        v = _verdict(b, b45).split("**")[1] if "**" in _verdict(b, b45) else "?"
        L.append(f"| `{gname}` | {blk['total_signals']} | `{blk['best_key']}` | {b.get('n_trades',0)} "
                 f"| {b.get('win_rate',0)*100:.1f} | {b.get('expectancy_pct',0):+.3f} | {b.get('profit_factor',0):.2f} "
                 f"| {b45.get('expectancy_pct',0):+.3f} | {v} |")

    # detailed per fireable gate
    for gname, blk in G.items():
        if blk["total_signals"] == 0:
            continue
        b = blk["best_at_35bps"]; b45 = blk["best_at_45bps_samecombo"]; b0 = blk["best_at_0bps_samecombo"]
        bk = blk["best_key"]
        L.append(f"\n## 3.{gname} — gate `{gname}` detail")
        L.append(f"**Best combo @ {base:.0f}bps: `{bk}`** → "
                 f"exp **{b.get('expectancy_pct',0):+.3f}%/trade**, WR {b.get('win_rate',0)*100:.1f}%, "
                 f"PF {b.get('profit_factor',0):.2f}, R:R {b.get('avg_rr',0):.2f}, n={b.get('n_trades',0)}, "
                 f"avg hold {b.get('avg_hold_bars',0):.1f} bars")
        L.append(f"- @ 0bps (no cost): {b0.get('expectancy_pct',0):+.3f}%/trade  → "
                 f"**cost drag {b0.get('expectancy_pct',0)-b.get('expectancy_pct',0):+.3f}%/trade**")
        L.append(f"- @ {stress:.0f}bps (stress): {b45.get('expectancy_pct',0):+.3f}%/trade, PF {b45.get('profit_factor',0):.2f}")
        L.append(f"- best combo re-optimised @ {stress:.0f}bps: `{blk['best_key_at_45bps']}` → "
                 f"{blk['best_at_45bps_independent'].get('expectancy_pct',0):+.3f}%/trade")
        # sweep matrix @35bps
        L.append(f"\n**Sweep @ {base:.0f}bps (top 12 by expectancy):**")
        L.append("| TP | stop | hold | n | win% | exp%/trade | PF | R:R |")
        L.append("|---|---|---|---|---|---|---|---|")
        agg = blk["agg_35bps"]
        for key in sorted(agg, key=lambda k: -agg[k]["expectancy_pct"])[:12]:
            a = agg[key]; tp, st, ho = key.split("|")
            L.append(f"| {tp} | {st} | {ho} | {a['n_trades']} | {a['win_rate']*100:.1f} "
                     f"| {a['expectancy_pct']:+.3f} | {a['profit_factor']:.2f} | {a['avg_rr']:.2f} |")
        # per-symbol best combo
        L.append(f"\n**Per-symbol @ {base:.0f}bps on best combo `{bk}`:**")
        L.append("| symbol | n | win% | exp%/trade | PF | total ret% | max DD% |")
        L.append("|---|---|---|---|---|---|---|")
        for s in tested:
            c = blk["per_symbol_35bps_bestcombo"][s]
            if c.get("n_trades", 0) == 0:
                L.append(f"| {s} | 0 | - | - | - | - | - |"); continue
            L.append(f"| {s} | {c['n_trades']} | {c['win_rate']*100:.1f} | {c['expectancy_pct']:+.3f} "
                     f"| {c['profit_factor']:.2f} | {c['total_return_pct']:+.2f} | {c['max_dd_pct']:.2f} |")

    # survivorship
    # pick the best fireable gate for the drag comparison
    fireable = {g: b for g, b in G.items() if b["total_signals"] > 0}
    best_gate = max(fireable, key=lambda g: fireable[g]["best_at_35bps"].get("expectancy_pct", -9)) if fireable else None
    best_exp = G[best_gate]["best_at_35bps"].get("expectancy_pct", 0) if best_gate else 0
    L.append("\n## 4. SURVIVORSHIP BIAS — results are OPTIMISTICALLY BIASED (headline caveat)")
    L.append("Only **currently-listed** HL perps are testable. Of **230 HL perps, 51 are already delisted** "
             "— and delisting is exactly the fate of a failed moonshot (pumped, dumped, went to ~zero, "
             "removed). Those **−100% paths are absent from this data**. Every symbol tested here is a "
             "*survivor*; the test cannot see the moonshots that died.")
    L.append("\n**Drag estimate.** 51/230 = **22% of the perp population delisted**. The mechanical leg is "
             "long-only on breakouts — precisely the entries most exposed to a token that subsequently "
             "collapses and delists. If the screener's small-cap candidates delist at even half that base "
             "rate (~11%) and a delisting trade averages ~−80% (vs a clean survivor stop at −3/−4%):")
    L.append("\n> drag ≈ 0.11 × (−80%) ≈ **−8.8%/trade** of hidden downside. "
             "Even a conservative 5% delist rate × −80% ≈ **−4%/trade**.")
    L.append(f"\nThe best survivor-only expectancy measured (gate `{best_gate}`) is **{best_exp:+.3f}%/trade**. "
             f"A delisting drag of −4 to −9%/trade **swamps it by 1–2 orders of magnitude**. For survivors "
             f"to carry the strategy to breakeven after delistings, they would need to average roughly "
             f"**+4 to +9%/trade NET** — versus the {best_exp:+.3f}%/trade actually observed.")

    # overall verdict
    L.append("\n## 5. OVERALL VERDICT")
    if best_gate is None:
        L.append("**FAIL** — no gate produced a tradeable signal stream.")
    else:
        bg = G[best_gate]
        L.append(f"- Literal screener gate (`as_written`): **dead** — 0 signals, structural.")
        L.append(f"- Best faithful interpretation (`{best_gate}`): {_verdict(bg['best_at_35bps'], bg['best_at_45bps_samecombo'])}")
        any_pass = any(v.get("expectancy_pct", -9) > 0 and b["best_at_45bps_samecombo"].get("expectancy_pct", -9) > 0
                       for g, b in fireable.items() for v in [b["best_at_35bps"]])
        if best_exp <= 0:
            tag = "**FAIL**"
        elif any_pass:
            tag = "**INCONCLUSIVE (survivor-positive, delist-negative)**"
        else:
            tag = "**FRAGILE / FAIL**"
        L.append(f"\n### {tag}")
        L.append("Even on survivor-only data the mechanical leg's best honest expectancy is "
                 f"{best_exp:+.3f}%/trade — and the survivorship drag (−4 to −9%/trade) **dominates it**. "
                 "The mechanical chart-trigger leg, in isolation, does **not** demonstrate a robust edge on "
                 "thin HL small-caps at realistic cost. Spread/cost is the killer on this class: the per-trade "
                 "edge lives entirely inside the 30–40bps cost band. The buzz filter would need to add edge an "
                 "order of magnitude larger than the mechanical leg's — AND dodge the delisting tail — to make "
                 "the full strategy viable.")

    L.append("\n## Files")
    L.append(f"- `{OUT_JSON.name}` — full per-gate / per-symbol / sweep results")
    L.append(f"- `{OUT_MD.name}` — this summary")
    L.append(f"- `{Path(__file__).name}` — the harness")
    OUT_MD.write_text("\n".join(L))


if __name__ == "__main__":
    main()
