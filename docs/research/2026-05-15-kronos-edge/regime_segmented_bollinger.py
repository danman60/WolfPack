"""
Regime-segmented Bollinger vol-norm MR — does the strategy work in any specific regime?

Regime classifier: 200-bar trailing log return at trade entry.
  BULL    : 200-bar return > +5%
  BEAR    : 200-bar return < -5%
  SIDEWAYS: between

Applies the L=100 thr=2.5 hold=24 vol_norm config to FULL history and reports
PnL per regime bucket.
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

FEE_PER_LEG = 0.00035
SLIPPAGE = 0.00050
ROUND_TRIP_COST = (FEE_PER_LEG + SLIPPAGE) * 2

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
LOOKBACK = 100
THR = 2.5
HOLD = 24
REGIME_WINDOW = 200
BULL_THR = 0.05
BEAR_THR = -0.05


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
    df["regime_ret"] = (df["close"] / df["close"].shift(REGIME_WINDOW) - 1)
    return df


def classify(reg_ret: float) -> str:
    if math.isnan(reg_ret):
        return "UNKNOWN"
    if reg_ret > BULL_THR:
        return "BULL"
    if reg_ret < BEAR_THR:
        return "BEAR"
    return "SIDEWAYS"


def bollinger_trades_with_regime(candles: pd.DataFrame) -> pd.DataFrame:
    px = candles["close"].values
    ts = candles["timestamps"].values
    mean = candles["close"].rolling(LOOKBACK).mean().values
    std = candles["close"].rolling(LOOKBACK).std().values
    z = (px - mean) / std
    rvol = candles["log_ret_1"].rolling(LOOKBACK).std().values
    reg = candles["regime_ret"].values

    rows = []
    next_free = max(LOOKBACK, REGIME_WINDOW)
    for i in range(max(LOOKBACK, REGIME_WINDOW), len(candles) - HOLD):
        if i < next_free or math.isnan(z[i]):
            continue
        signal = 1 if z[i] <= -THR else (-1 if z[i] >= THR else 0)
        if signal == 0:
            continue
        entry = px[i]
        exit_px = px[i + HOLD]
        gross = signal * (exit_px / entry - 1.0)
        size = float(np.clip(0.01 / max(rvol[i], 1e-6), 0.1, 5.0))
        net = gross * size - ROUND_TRIP_COST * size
        rows.append({
            "ts": ts[i],
            "signal": signal,
            "regime": classify(reg[i]),
            "regime_ret": reg[i],
            "gross_pct": gross * 100,
            "net_pct": net * 100,
            "size": size,
        })
        next_free = i + HOLD
    return pd.DataFrame(rows)


def main() -> int:
    all_rows = []
    for symbol in SYMBOLS:
        df = load_full_history(symbol)
        trades = bollinger_trades_with_regime(df)
        # Also segment by signal direction (long vs short)
        for regime in ["BULL", "BEAR", "SIDEWAYS"]:
            for direction_label, sig_filter in [("ALL", None), ("LONG", 1), ("SHORT", -1)]:
                sub = trades[trades["regime"] == regime]
                if sig_filter is not None:
                    sub = sub[sub["signal"] == sig_filter]
                if len(sub) == 0:
                    continue
                net = sub["net_pct"].values / 100
                eq = (1 + net).cumprod()
                sharpe = float(net.mean() / net.std() * math.sqrt(365)) if net.std() > 0 else float("nan")
                all_rows.append({
                    "symbol": symbol,
                    "regime": regime,
                    "direction": direction_label,
                    "n": int(len(sub)),
                    "win_rate": round(float((net > 0).mean()) * 100, 2),
                    "avg_net_pct": round(float(net.mean()) * 100, 4),
                    "total_ret_pct": round(float(eq[-1] - 1) * 100, 3),
                    "sharpe": round(sharpe, 3),
                })

    out = pd.DataFrame(all_rows)
    out_path = RESULTS_DIR / "regime_segmented_bollinger.csv"
    out.to_csv(out_path, index=False)
    print(out.to_string(index=False))
    print(f"\n→ {out_path}")

    print("\n\n=== ALL-direction view (one row per (symbol, regime)) ===")
    short = out[out["direction"] == "ALL"][["symbol", "regime", "n", "win_rate", "avg_net_pct", "total_ret_pct", "sharpe"]]
    print(short.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
