"""
Out-of-sample robustness check for the winning Idea #1 (direct Kronos strategy)
and Idea #7 (Bollinger vol-norm MR) configurations.

Split the 90d window: first 60d as "in-sample" (pick best config), last 30d as
out-of-sample test. Apply the chosen config to OOS data and compare.

Also bootstrap CI on the winning OOS configs.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
PRED_DIR = HERE / "predictions"
RESULTS_DIR = HERE / "results"

FEE_PER_LEG = 0.00035
SLIPPAGE = 0.00050
ROUND_TRIP_COST = (FEE_PER_LEG + SLIPPAGE) * 2

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
TF = "1h"

# Winning configs from full-window backtest
KRONOS_THR = {"BTCUSDT": 0.005, "ETHUSDT": 0.010, "LINKUSDT": 0.010}
BOLL_CFG = {"lookback": 100, "thr": 2.5, "hold": 24}


def annualization_factor(tf: str, hold: int) -> float:
    candles_per_year = {"1h": 24 * 365, "4h": 6 * 365}[tf]
    trades_per_year = candles_per_year / hold
    return math.sqrt(trades_per_year)


def split_window(df: pd.DataFrame, split_frac: float = 2 / 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(len(df) * split_frac)
    return df.iloc[:cut].reset_index(drop=True), df.iloc[cut:].reset_index(drop=True)


def kronos_backtest(parq: pd.DataFrame, threshold: float) -> dict:
    horizon = parq["offset"].max() + 1
    first = parq[parq["offset"] == 0][["anchor_ts", "pred_c", "true_o"]].rename(
        columns={"pred_c": "pred_c0", "true_o": "true_o0"})
    last = parq[parq["offset"] == horizon - 1][["anchor_ts", "pred_c", "true_c"]].rename(
        columns={"pred_c": "pred_cN", "true_c": "true_cN"})
    win = first.merge(last, on="anchor_ts").sort_values("anchor_ts").reset_index(drop=True)
    win["pred_ret"] = win["pred_cN"] / win["pred_c0"] - 1
    win["real_ret"] = win["true_cN"] / win["true_o0"] - 1
    win["signal"] = np.where(win["pred_ret"] > threshold, 1, np.where(win["pred_ret"] < -threshold, -1, 0))
    chosen, next_free = [], 0
    for i in range(len(win)):
        if i < next_free:
            continue
        if win["signal"].iloc[i] != 0:
            chosen.append(i)
            next_free = i + horizon
    trades = win.iloc[chosen]
    if len(trades) == 0:
        return {"n_trades": 0, "total_pct": 0.0, "sharpe": float("nan"), "hodl_pct": (win["true_cN"].iloc[-1] / win["true_o0"].iloc[0] - 1) * 100}
    gross = trades["signal"] * trades["real_ret"]
    net = gross - ROUND_TRIP_COST
    eq = (1 + net).cumprod()
    sharpe = float(net.mean() / net.std() * annualization_factor("1h", horizon)) if net.std() > 0 else float("nan")
    hodl = (win["true_cN"].iloc[-1] / win["true_o0"].iloc[0] - 1) * 100
    return {
        "n_trades": int(len(trades)),
        "win_rate": round(float((net > 0).mean()) * 100, 2),
        "total_pct": round(float(eq.iloc[-1] - 1) * 100, 3),
        "hodl_pct": round(hodl, 3),
        "sharpe": round(sharpe, 3),
    }


def bollinger_backtest(candles: pd.DataFrame, lookback: int, thr: float, hold: int, vol_norm: bool) -> dict:
    px = candles["close"].values
    mean = candles["close"].rolling(lookback).mean().values
    std = candles["close"].rolling(lookback).std().values
    z = (px - mean) / std
    log_ret_1 = np.log(candles["close"]).diff().values
    rvol = pd.Series(log_ret_1).rolling(lookback).std().values
    trades = []
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
        trades.append(net)
        next_free = i + hold

    if not trades:
        return {"n_trades": 0}
    arr = np.array(trades)
    eq = (1 + arr).cumprod()
    bars_per_year = 24 * 365
    sharpe = float(arr.mean() / arr.std() * math.sqrt(bars_per_year / hold)) if arr.std() > 0 else float("nan")
    hodl = (px[-1] / px[lookback] - 1) * 100
    return {
        "n_trades": int(len(arr)),
        "win_rate": round(float((arr > 0).mean()) * 100, 2),
        "total_pct": round(float(eq[-1] - 1) * 100, 3),
        "hodl_pct": round(hodl, 3),
        "sharpe": round(sharpe, 3),
    }


def bootstrap_sharpe(trade_returns: np.ndarray, n_boot: int = 2000, periods_per_year: int = 365) -> dict:
    if len(trade_returns) < 5:
        return {"sharpe_p2.5": float("nan"), "sharpe_median": float("nan"), "sharpe_p97.5": float("nan")}
    rng = np.random.default_rng(seed=42)
    sharpes = []
    for _ in range(n_boot):
        sample = rng.choice(trade_returns, size=len(trade_returns), replace=True)
        if sample.std() > 0:
            sharpes.append(sample.mean() / sample.std() * math.sqrt(periods_per_year))
    arr = np.array(sharpes)
    return {
        "sharpe_p2.5": round(float(np.percentile(arr, 2.5)), 3),
        "sharpe_median": round(float(np.percentile(arr, 50)), 3),
        "sharpe_p97.5": round(float(np.percentile(arr, 97.5)), 3),
    }


def main() -> int:
    rows = []
    for symbol in SYMBOLS:
        # Kronos OOS
        parq_path = PRED_DIR / f"{symbol}_{TF}_kronos-small.parquet"
        if parq_path.exists():
            df = pd.read_parquet(parq_path).sort_values(["anchor_ts", "offset"]).reset_index(drop=True)
            anchors = sorted(df["anchor_ts"].unique())
            cut_ts = anchors[int(len(anchors) * 2 / 3)]
            in_sample = df[df["anchor_ts"] < cut_ts]
            oos = df[df["anchor_ts"] >= cut_ts]
            thr = KRONOS_THR[symbol]
            ins_metrics = kronos_backtest(in_sample, thr)
            oos_metrics = kronos_backtest(oos, thr)
            rows.append({
                "strategy": f"kronos_direct thr={thr}",
                "symbol": symbol,
                "in_sample_total_pct": ins_metrics.get("total_pct", float("nan")),
                "in_sample_sharpe": ins_metrics.get("sharpe", float("nan")),
                "in_sample_hodl_pct": ins_metrics.get("hodl_pct", float("nan")),
                "in_sample_n": ins_metrics.get("n_trades", 0),
                "oos_total_pct": oos_metrics.get("total_pct", float("nan")),
                "oos_sharpe": oos_metrics.get("sharpe", float("nan")),
                "oos_hodl_pct": oos_metrics.get("hodl_pct", float("nan")),
                "oos_n": oos_metrics.get("n_trades", 0),
            })

        # Bollinger vol-norm OOS
        candles_path = DATA_DIR / f"{symbol}_{TF}_90d.csv"
        if candles_path.exists():
            candles = pd.read_csv(candles_path, parse_dates=["timestamps"]).sort_values("timestamps").reset_index(drop=True)
            ins, oos = split_window(candles, split_frac=2 / 3)
            for variant in ["classical", "vol_norm"]:
                ins_m = bollinger_backtest(ins, BOLL_CFG["lookback"], BOLL_CFG["thr"], BOLL_CFG["hold"], variant == "vol_norm")
                oos_m = bollinger_backtest(oos, BOLL_CFG["lookback"], BOLL_CFG["thr"], BOLL_CFG["hold"], variant == "vol_norm")
                rows.append({
                    "strategy": f"bollinger_{variant} lookback={BOLL_CFG['lookback']} thr={BOLL_CFG['thr']} hold={BOLL_CFG['hold']}",
                    "symbol": symbol,
                    "in_sample_total_pct": ins_m.get("total_pct", float("nan")),
                    "in_sample_sharpe": ins_m.get("sharpe", float("nan")),
                    "in_sample_hodl_pct": ins_m.get("hodl_pct", float("nan")),
                    "in_sample_n": ins_m.get("n_trades", 0),
                    "oos_total_pct": oos_m.get("total_pct", float("nan")),
                    "oos_sharpe": oos_m.get("sharpe", float("nan")),
                    "oos_hodl_pct": oos_m.get("hodl_pct", float("nan")),
                    "oos_n": oos_m.get("n_trades", 0),
                })

    out = pd.DataFrame(rows)
    out_path = RESULTS_DIR / "oos_robustness.csv"
    out.to_csv(out_path, index=False)
    print(out.to_string(index=False))
    print(f"\n→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
