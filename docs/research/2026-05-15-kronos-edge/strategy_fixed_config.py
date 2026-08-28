"""
Single FIXED config applied uniformly across BTC/ETH/LINK/DOGE.

Avoids per-symbol overfitting. Pick a reasonable, generic short-only momentum-fade
config and test whether it has positive expectancy on the basket as a whole.

Config rationale:
- rally_lookback=4 (4h surge), rally_thr=2.0% — moderate trigger, fires ~1-2/day
- rsi_thr=65 — not extreme, captures most rallies
- tp_pct=1.5, sl_pct=2.5 — 1.67:1 reward:risk
- hold_bars=12 — 12h max hold
- Short-only

Outputs:
- per-symbol P&L, trade count, win rate, drawdown
- aggregate basket P&L if traded with equal sizing
- rolling 14-day P&L curve
- trade-by-trade log
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

# THE FIXED CONFIG — no per-symbol tuning
CFG = {
    "rally_lookback": 4,
    "rally_thr_pct": 2.0,
    "rsi_thr": 65,
    "tp_pct": 1.5,
    "sl_pct": 2.5,
    "hold_bars": 12,
}


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    diff = np.diff(close, prepend=close[0])
    gain = np.where(diff > 0, diff, 0.0)
    loss = np.where(diff < 0, -diff, 0.0)
    avg_g = np.zeros_like(close)
    avg_l = np.zeros_like(close)
    avg_g[:period] = np.mean(gain[:period])
    avg_l[:period] = np.mean(loss[:period])
    for i in range(period, len(close)):
        avg_g[i] = (avg_g[i - 1] * (period - 1) + gain[i]) / period
        avg_l[i] = (avg_l[i - 1] * (period - 1) + loss[i]) / period
    rs = avg_g / np.maximum(avg_l, 1e-12)
    return 100 - (100 / (1 + rs))


def backtest(candles: pd.DataFrame, cfg: dict, symbol: str) -> tuple[list, dict]:
    close = candles["close"].values
    open_ = candles["open"].values
    high = candles["high"].values
    low = candles["low"].values
    ts = candles["timestamps"].values
    n = len(candles)
    rsi_v = rsi(close, 14)
    rl = cfg["rally_lookback"]; rt = cfg["rally_thr_pct"] / 100
    rsi_thr = cfg["rsi_thr"]; tp = cfg["tp_pct"] / 100; sl = cfg["sl_pct"] / 100
    hb = cfg["hold_bars"]
    trades = []
    next_free = max(rl, 20)
    for i in range(max(rl, 20), n - hb):
        if i < next_free:
            continue
        rally = close[i] / close[i - rl] - 1
        if rally < rt:
            continue
        if rsi_v[i] < rsi_thr:
            continue
        entry_idx = i + 1
        if entry_idx >= n - 1:
            continue
        entry = open_[entry_idx]
        tp_price = entry * (1 - tp)
        sl_price = entry * (1 + sl)
        exit_idx = None; exit_price = None; reason = None
        for k in range(entry_idx, min(entry_idx + hb, n)):
            if high[k] >= sl_price:
                exit_idx, exit_price, reason = k, sl_price, "sl"
                break
            if low[k] <= tp_price:
                exit_idx, exit_price, reason = k, tp_price, "tp"
                break
        if exit_idx is None:
            exit_idx = min(entry_idx + hb - 1, n - 1)
            exit_price = close[exit_idx]
            reason = "timeout"
        gross = (entry - exit_price) / entry
        net = gross - ROUND_TRIP
        trades.append({
            "symbol": symbol,
            "entry_ts": ts[entry_idx], "exit_ts": ts[exit_idx],
            "entry": entry, "exit": exit_price,
            "rsi_at_entry": float(rsi_v[i]),
            "rally_at_entry_pct": round(rally * 100, 3),
            "gross_pct": round(gross * 100, 3),
            "net_pct": round(net * 100, 3),
            "reason": reason,
            "hold_bars_actual": exit_idx - entry_idx + 1,
        })
        next_free = exit_idx + 1

    if not trades:
        return [], {"symbol": symbol, "n": 0}
    nets = np.array([t["net_pct"] for t in trades]) / 100
    eq = np.cumprod(1 + nets)
    sharpe = float(nets.mean() / nets.std() * math.sqrt(365)) if nets.std() > 0 else float("nan")
    mdd = float(((eq / np.maximum.accumulate(eq)) - 1).min())
    hodl = (close[-1] / close[0] - 1) * 100
    return trades, {
        "symbol": symbol, "n": len(trades),
        "win_rate": round(float((nets > 0).mean()) * 100, 2),
        "avg_net_pct": round(float(nets.mean()) * 100, 4),
        "total_pct": round(float(eq[-1] - 1) * 100, 3),
        "max_dd_pct": round(mdd * 100, 3),
        "sharpe": round(sharpe, 3),
        "hodl_pct": round(float(hodl), 3),
        "tp_rate": round(sum(1 for t in trades if t["reason"] == "tp") / len(trades) * 100, 1),
        "sl_rate": round(sum(1 for t in trades if t["reason"] == "sl") / len(trades) * 100, 1),
        "timeout_rate": round(sum(1 for t in trades if t["reason"] == "timeout") / len(trades) * 100, 1),
    }


def rolling_windows(candles: pd.DataFrame, window_days: int = 30) -> list[pd.DataFrame]:
    """Slice into sequential non-overlapping windows."""
    bars = window_days * 24  # 1h
    out = []
    for start in range(0, len(candles) - bars + 1, bars):
        out.append(candles.iloc[start:start + bars].reset_index(drop=True))
    return out


def main() -> int:
    summary_rows = []
    rolling_rows = []
    all_trades = []
    for symbol in SYMBOLS:
        csv = DATA / f"{symbol}_1h_90d.csv"
        if not csv.exists():
            continue
        candles = pd.read_csv(csv, parse_dates=["timestamps"]).sort_values("timestamps").reset_index(drop=True)
        trades, summ = backtest(candles, CFG, symbol)
        summary_rows.append(summ)
        all_trades.extend(trades)

        # Rolling 30-day windows
        for wi, w in enumerate(rolling_windows(candles, 30)):
            wt, ws = backtest(w, CFG, symbol)
            if ws.get("n", 0) > 0:
                ws["window"] = wi
                ws["window_start"] = w["timestamps"].iloc[0]
                ws["window_end"] = w["timestamps"].iloc[-1]
                rolling_rows.append(ws)

    summ_df = pd.DataFrame(summary_rows)
    roll_df = pd.DataFrame(rolling_rows)
    trades_df = pd.DataFrame(all_trades)

    # Basket P&L: equal-weighted across all 4 symbols, no compounding
    basket_pnl = trades_df["net_pct"].sum() / len(SYMBOLS) if not trades_df.empty else 0.0

    summ_df.to_csv(RESULTS / "fixed_config_summary.csv", index=False)
    roll_df.to_csv(RESULTS / "fixed_config_rolling30d.csv", index=False)
    trades_df.to_csv(RESULTS / "fixed_config_trades.csv", index=False)

    print(f"\n=== FIXED CONFIG: {CFG} ===\n")
    print("--- Per-symbol full 90d ---")
    print(summ_df.to_string(index=False))

    print(f"\n--- Aggregate basket (equal-weight across {len(SYMBOLS)} symbols) ---")
    print(f"total trades: {len(trades_df)}")
    if not trades_df.empty:
        nets = trades_df["net_pct"].values / 100
        eq = np.cumprod(1 + nets)
        sharpe = float(nets.mean() / nets.std() * math.sqrt(365)) if nets.std() > 0 else float("nan")
        print(f"avg net per trade: {nets.mean()*100:.4f}%")
        print(f"win rate: {(nets > 0).mean()*100:.2f}%")
        print(f"total compounded (single-track): {(eq[-1]-1)*100:.3f}%")
        print(f"avg-weighted basket pnl (equal 1/{len(SYMBOLS)} sizing): {basket_pnl:.3f}%")
        print(f"sharpe: {sharpe:.3f}")
        print(f"exit reason mix: tp={(trades_df['reason']=='tp').mean()*100:.1f}%, sl={(trades_df['reason']=='sl').mean()*100:.1f}%, timeout={(trades_df['reason']=='timeout').mean()*100:.1f}%")

    print(f"\n--- Rolling 30d windows (1 window = 30 days, 3 windows fit in 90d) ---")
    if not roll_df.empty:
        print(roll_df[["symbol", "window", "n", "win_rate", "total_pct", "hodl_pct", "sharpe"]].to_string(index=False))
        print(f"\n--- Rolling window aggregate by window ---")
        agg = roll_df.groupby("window").agg(
            n_trades_total=("n", "sum"),
            mean_total_pct=("total_pct", "mean"),
            n_positive_symbols=("total_pct", lambda x: int((x > 0).sum())),
        ).reset_index()
        print(agg.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
