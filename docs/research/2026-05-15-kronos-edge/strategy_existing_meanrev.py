"""
Port of WolfPack's existing mean_reversion.py logic to a standalone backtest harness.

This is the strategy that earned +$3,372 in 28 trades over Apr 6-10 per the audit
note inline in mean_reversion.py. Default TRENDING preset:
  - mean_period: 20
  - threshold_atr_mult: 3.0
  - stop_atr_mult: 1.0
  - short-only

Plus liquidity sweep filter (price wicked above local high then closed below).
Take-profit = revert to SMA(20). Stop = entry + 1.0 ATR.

Testing on BTC/ETH/LINK/DOGE 1h 90d.
Outputs per-symbol P&L + aggregate basket + rolling 30d windows.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT", "DOGEUSDT"]
FEE_PER_LEG = 0.00035
SLIPPAGE = 0.00050
ROUND_TRIP = (FEE_PER_LEG + SLIPPAGE) * 2

MEAN_PERIOD = 20
THRESHOLD_ATR_MULT = 3.0
STOP_ATR_MULT = 1.0
SWEEP_LOOKBACK = 5
HOLD_BARS_MAX = 48  # safety timeout (mean_reversion.py uses ATR-based exits, we add a hold cap)


def atr_series(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder ATR."""
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    atr = np.zeros_like(close)
    atr[:period] = np.mean(tr[:period])
    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def backtest_meanrev(candles: pd.DataFrame, symbol: str,
                     short_only: bool = True, long_only: bool = False,
                     use_sweep_filter: bool = True) -> tuple[list, dict]:
    close = candles["close"].values
    open_ = candles["open"].values
    high = candles["high"].values
    low = candles["low"].values
    ts = candles["timestamps"].values
    n = len(candles)
    atr = atr_series(high, low, close, 14)
    sma = pd.Series(close).rolling(MEAN_PERIOD).mean().values
    trades = []
    next_free = max(MEAN_PERIOD, 15) + 1
    for i in range(next_free, n - HOLD_BARS_MAX):
        if i < next_free:
            continue
        if math.isnan(sma[i]) or atr[i] <= 0:
            continue
        distance = (close[i] - sma[i]) / atr[i]
        # Local high/low for sweep filter (excluding the last SWEEP_LOOKBACK bars)
        window_start = max(0, i - MEAN_PERIOD)
        block_highs = high[window_start:i + 1]
        block_lows = low[window_start:i + 1]
        if len(block_highs) <= SWEEP_LOOKBACK:
            continue
        local_high = np.max(block_highs[:-SWEEP_LOOKBACK])
        local_low = np.min(block_lows[:-SWEEP_LOOKBACK])
        recent = candles.iloc[i - SWEEP_LOOKBACK + 1: i + 1]

        signal = 0
        # SHORT: distance > +threshold (price extended above mean), optional sweep filter
        if (not long_only) and distance > THRESHOLD_ATR_MULT:
            swept_local = bool(((recent["high"] > local_high) & (recent["close"] < local_high)).any())
            if (not use_sweep_filter) or swept_local:
                signal = -1
        # LONG: distance < -threshold (price extended below mean)
        if signal == 0 and (not short_only) and distance < -THRESHOLD_ATR_MULT:
            swept_local = bool(((recent["low"] < local_low) & (recent["close"] > local_low)).any())
            if (not use_sweep_filter) or swept_local:
                signal = 1
        if signal == 0:
            continue

        entry_idx = i + 1
        if entry_idx >= n - 1:
            continue
        entry = open_[entry_idx]
        if signal == -1:
            tp_price = sma[i]  # revert to mean
            sl_price = entry + atr[i] * STOP_ATR_MULT
        else:
            tp_price = sma[i]
            sl_price = entry - atr[i] * STOP_ATR_MULT
        exit_idx = None; exit_price = None; reason = None
        for k in range(entry_idx, min(entry_idx + HOLD_BARS_MAX, n)):
            if signal == -1:
                # SHORT: stop is above entry, TP is below entry
                if high[k] >= sl_price:
                    exit_idx, exit_price, reason = k, sl_price, "sl"; break
                if low[k] <= tp_price:
                    exit_idx, exit_price, reason = k, tp_price, "tp"; break
            else:
                # LONG: stop is below entry, TP is above entry
                if low[k] <= sl_price:
                    exit_idx, exit_price, reason = k, sl_price, "sl"; break
                if high[k] >= tp_price:
                    exit_idx, exit_price, reason = k, tp_price, "tp"; break
        if exit_idx is None:
            exit_idx = min(entry_idx + HOLD_BARS_MAX - 1, n - 1)
            exit_price = close[exit_idx]
            reason = "timeout"
        gross = (entry - exit_price) / entry if signal == -1 else (exit_price - entry) / entry
        net = gross - ROUND_TRIP
        trades.append({
            "symbol": symbol,
            "direction": "short" if signal == -1 else "long",
            "entry_ts": ts[entry_idx], "exit_ts": ts[exit_idx],
            "entry": float(entry), "exit": float(exit_price),
            "distance_atr": round(float(distance), 3),
            "atr_at_entry": round(float(atr[i]), 6),
            "sma_at_entry": round(float(sma[i]), 6),
            "tp_price": round(float(tp_price), 6),
            "sl_price": round(float(sl_price), 6),
            "gross_pct": round(float(gross) * 100, 3),
            "net_pct": round(float(net) * 100, 3),
            "reason": reason,
            "hold_bars": exit_idx - entry_idx + 1,
        })
        next_free = exit_idx + 1

    if not trades:
        return [], {"symbol": symbol, "n": 0, "hodl_pct": round((close[-1] / close[0] - 1) * 100, 3)}
    nets = np.array([t["net_pct"] for t in trades]) / 100
    eq = np.cumprod(1 + nets)
    sharpe = float(nets.mean() / nets.std() * math.sqrt(365)) if nets.std() > 0 else float("nan")
    mdd = float(((eq / np.maximum.accumulate(eq)) - 1).min())
    return trades, {
        "symbol": symbol, "n": len(trades),
        "win_rate": round(float((nets > 0).mean()) * 100, 2),
        "avg_net_pct": round(float(nets.mean()) * 100, 4),
        "total_pct": round(float(eq[-1] - 1) * 100, 3),
        "max_dd_pct": round(mdd * 100, 3),
        "sharpe": round(sharpe, 3),
        "hodl_pct": round((close[-1] / close[0] - 1) * 100, 3),
        "tp_rate": round(sum(1 for t in trades if t["reason"] == "tp") / len(trades) * 100, 1),
        "sl_rate": round(sum(1 for t in trades if t["reason"] == "sl") / len(trades) * 100, 1),
        "timeout_rate": round(sum(1 for t in trades if t["reason"] == "timeout") / len(trades) * 100, 1),
    }


def main() -> int:
    summary = []
    all_trades = []
    for symbol in SYMBOLS:
        csv = DATA / f"{symbol}_1h_90d.csv"
        if not csv.exists():
            continue
        candles = pd.read_csv(csv, parse_dates=["timestamps"]).sort_values("timestamps").reset_index(drop=True)
        # Run THREE variants for clarity:
        # 1. SHORT-only with sweep filter (the production mean_reversion preset)
        # 2. SHORT-only WITHOUT sweep filter (raw extension fade)
        # 3. SHORT+LONG with sweep filter (the unrestricted strategy)
        for label, kw in [
            ("short_with_sweep", {"short_only": True, "use_sweep_filter": True}),
            ("short_no_sweep",   {"short_only": True, "use_sweep_filter": False}),
            ("both_with_sweep",  {"short_only": False, "use_sweep_filter": True}),
        ]:
            trades, summ = backtest_meanrev(candles, symbol, **kw)
            summ["variant"] = label
            summary.append(summ)
            for t in trades:
                t["variant"] = label
                all_trades.append(t)

    summ_df = pd.DataFrame(summary)
    trades_df = pd.DataFrame(all_trades)
    summ_df.to_csv(RESULTS / "existing_meanrev_summary.csv", index=False)
    trades_df.to_csv(RESULTS / "existing_meanrev_trades.csv", index=False)

    print(f"\n=== Existing WolfPack mean_reversion.py logic — 90d 1h ===")
    print(f"Params: mean_period={MEAN_PERIOD}, threshold_atr_mult={THRESHOLD_ATR_MULT}, stop_atr_mult={STOP_ATR_MULT}")
    print(f"Costs: round-trip {ROUND_TRIP*100:.3f}%\n")
    cols = ["symbol", "variant", "n", "win_rate", "avg_net_pct", "total_pct", "hodl_pct",
            "max_dd_pct", "sharpe", "tp_rate", "sl_rate", "timeout_rate"]
    print(summ_df[cols].sort_values(["variant", "symbol"]).to_string(index=False))

    print(f"\n--- Per-variant basket totals (sum across symbols, equal-weight 1/{len(SYMBOLS)}) ---")
    for v, grp in summ_df.groupby("variant"):
        total_n = grp["n"].sum()
        if total_n == 0:
            print(f"{v}: no trades")
            continue
        sub = trades_df[trades_df["variant"] == v]
        nets = sub["net_pct"].values / 100
        basket_avg = float(nets.mean()) * 100 if len(nets) else 0
        basket_total_eq = float(np.cumprod(1 + nets)[-1] - 1) * 100 if len(nets) else 0
        wr = float((nets > 0).mean()) * 100 if len(nets) else 0
        print(f"  {v}: n={total_n}, basket_avg_net_pct={basket_avg:.3f}, basket_compounded={basket_total_eq:.2f}%, win_rate={wr:.1f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
