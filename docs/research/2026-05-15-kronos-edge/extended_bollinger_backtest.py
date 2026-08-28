"""
Extended Bollinger vol-norm MR backtest on full available history (2017/2019 → present).

Uses the train+val+eval pickles fetched for fine-tuning (so we don't re-fetch). Runs
the winning config (lookback=100, thr=2.5, hold=24, vol_norm) across the entire
history per symbol, broken into yearly buckets for regime / sample-size visibility.

Also runs a coarse param sweep on the FULL history to test whether the winning 90d
config remains optimal across years (or whether it's a 2026-window artifact).
"""
from __future__ import annotations

import math
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FT_DIR = HERE / "finetune"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

FEE_PER_LEG = 0.00035
SLIPPAGE = 0.00050
ROUND_TRIP_COST = (FEE_PER_LEG + SLIPPAGE) * 2

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]


def load_full_history(symbol: str) -> pd.DataFrame:
    chunks = []
    for name in ["train_data.pkl", "val_data.pkl", "eval_data.pkl"]:
        with open(FT_DIR / name, "rb") as f:
            d = pickle.load(f)
        if symbol in d:
            chunks.append(d[symbol])
    df = pd.concat(chunks).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df = df.rename(columns={"vol": "volume", "amt": "amount"})
    df = df.reset_index().rename(columns={"datetime": "timestamps"})
    df["log_ret_1"] = np.log(df["close"]).diff()
    return df


def bollinger_trades(candles: pd.DataFrame, lookback: int, thr: float, hold: int, vol_norm: bool) -> pd.DataFrame:
    px = candles["close"].values
    ts = candles["timestamps"].values
    mean = candles["close"].rolling(lookback).mean().values
    std = candles["close"].rolling(lookback).std().values
    z = (px - mean) / std
    rvol = candles["log_ret_1"].rolling(lookback).std().values

    rows = []
    next_free = lookback
    for i in range(lookback, len(candles) - hold):
        if i < next_free or math.isnan(z[i]):
            continue
        signal = 1 if z[i] <= -thr else (-1 if z[i] >= thr else 0)
        if signal == 0:
            continue
        entry = px[i]
        exit_px = px[i + hold]
        gross = signal * (exit_px / entry - 1.0)
        size = float(np.clip(0.01 / max(rvol[i], 1e-6), 0.1, 5.0)) if vol_norm else 1.0
        net = gross * size - ROUND_TRIP_COST * size
        rows.append({
            "ts": ts[i],
            "signal": signal,
            "gross_pct": gross * 100,
            "net_pct": net * 100,
            "size": size,
        })
        next_free = i + hold
    return pd.DataFrame(rows)


def summarize(trades: pd.DataFrame, hodl_pct: float, label: str = "") -> dict:
    if len(trades) == 0:
        return {"label": label, "n": 0, "hodl_pct": round(hodl_pct, 3)}
    net = trades["net_pct"].values / 100
    eq = (1 + net).cumprod()
    sharpe = float(net.mean() / net.std() * math.sqrt(365 * 24 / 24)) if net.std() > 0 else float("nan")
    mdd = float(((eq / np.maximum.accumulate(eq)) - 1).min())
    return {
        "label": label,
        "n": int(len(trades)),
        "win_rate": round(float((net > 0).mean()) * 100, 2),
        "avg_net_pct": round(float(net.mean()) * 100, 4),
        "total_ret_pct": round(float(eq[-1] - 1) * 100, 3),
        "hodl_pct": round(hodl_pct, 3),
        "max_dd_pct": round(mdd * 100, 3),
        "sharpe": round(sharpe, 3),
    }


def main() -> int:
    yearly_rows = []
    sweep_rows = []
    for symbol in SYMBOLS:
        print(f"\n=== {symbol} ===")
        df = load_full_history(symbol)
        print(f"  rows={len(df)}  span={df['timestamps'].iloc[0]} → {df['timestamps'].iloc[-1]}")

        # Winning config full-history vol_norm
        trades = bollinger_trades(df, 100, 2.5, 24, vol_norm=True)
        hodl = (df["close"].iloc[-1] / df["close"].iloc[100] - 1) * 100
        full = summarize(trades, hodl, f"{symbol} vol_norm L=100 thr=2.5 H=24")
        print("  FULL HISTORY:", full)

        # Yearly breakdown
        if len(trades) > 0:
            trades["year"] = pd.to_datetime(trades["ts"]).dt.year
            for year, sub in trades.groupby("year"):
                # HODL benchmark per year
                year_candles = df[pd.to_datetime(df["timestamps"]).dt.year == year]
                if len(year_candles) < 2:
                    continue
                year_hodl = (year_candles["close"].iloc[-1] / year_candles["close"].iloc[0] - 1) * 100
                row = summarize(sub, year_hodl, f"{symbol} {year}")
                row["symbol"] = symbol
                row["year"] = int(year)
                yearly_rows.append(row)

        # Coarse param sweep on full history (smaller grid for speed)
        for lookback in [50, 100, 200]:
            for thr in [2.0, 2.5, 3.0]:
                for hold in [12, 24, 48]:
                    for vol_norm in [False, True]:
                        sub_trades = bollinger_trades(df, lookback, thr, hold, vol_norm)
                        if len(sub_trades) < 30:
                            continue
                        sub_hodl = (df["close"].iloc[-1] / df["close"].iloc[lookback] - 1) * 100
                        s = summarize(sub_trades, sub_hodl)
                        s["symbol"] = symbol
                        s["lookback"] = lookback
                        s["thr"] = thr
                        s["hold"] = hold
                        s["variant"] = "vol_norm" if vol_norm else "classical"
                        sweep_rows.append(s)

    yearly_df = pd.DataFrame(yearly_rows)
    sweep_df = pd.DataFrame(sweep_rows)

    yearly_path = RESULTS_DIR / "extended_bollinger_yearly.csv"
    sweep_path = RESULTS_DIR / "extended_bollinger_sweep.csv"
    yearly_df.to_csv(yearly_path, index=False)
    sweep_df.to_csv(sweep_path, index=False)

    print("\n\n=== YEARLY (winning config L=100 thr=2.5 hold=24 vol_norm) ===")
    print(yearly_df[["symbol", "year", "n", "win_rate", "total_ret_pct", "hodl_pct", "sharpe"]].to_string(index=False))

    print("\n=== BEST configs per symbol on full history (top 5 by Sharpe with n≥30) ===")
    if not sweep_df.empty:
        for symbol in SYMBOLS:
            sub = sweep_df[sweep_df["symbol"] == symbol].sort_values("sharpe", ascending=False).head(5)
            print(f"\n{symbol}:")
            print(sub[["variant", "lookback", "thr", "hold", "n", "win_rate", "total_ret_pct", "hodl_pct", "sharpe", "max_dd_pct"]].to_string(index=False))

    print(f"\n→ {yearly_path}")
    print(f"→ {sweep_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
