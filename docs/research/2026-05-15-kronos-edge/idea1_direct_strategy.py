"""
Idea #1 — Direct Kronos-as-strategy backtest.

Signal: at each anchor t, compute predicted 24h cumulative return =
        pred_c[horizon-1] / pred_c[0] - 1.
        Long if > +threshold, Short if < -threshold, else flat.

Hold for `horizon` candles (24h on 1h, 96h on 4h). Apply fees + slippage.
Compare to HODL.

Metrics: total return, Sharpe (annualized), max drawdown, win rate, # trades.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PRED_DIR = HERE / "predictions"
DATA_DIR = HERE / "data"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Cost model (rough Hyperliquid perps)
FEE_PER_LEG = 0.00035   # 3.5 bps maker+taker blended estimate
SLIPPAGE = 0.00050      # 5 bps per leg pessimistic
ROUND_TRIP_COST = (FEE_PER_LEG + SLIPPAGE) * 2

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
TIMEFRAMES = ["1h", "4h"]
THRESHOLDS = [0.0, 0.002, 0.005, 0.010, 0.015, 0.025]


def annualization_factor(tf: str, horizon: int) -> float:
    # Trades fire every `horizon` candles → trades/year
    candles_per_year = {"1h": 24 * 365, "4h": 6 * 365}[tf]
    trades_per_year = candles_per_year / horizon
    return math.sqrt(trades_per_year)


def backtest(df: pd.DataFrame, tf: str, threshold: float) -> dict:
    """Vectorized backtest. Non-overlapping trades."""
    # One row per anchor, columns include the predicted last close (offset = horizon-1) and true last close
    anchors = df["anchor_ts"].unique()
    horizon = df["offset"].max() + 1

    # Pivot: per anchor, get pred_c[0], pred_c[-1], true_c[0], true_c[-1]
    first = df[df["offset"] == 0][["anchor_ts", "pred_c", "true_c", "true_o"]].rename(
        columns={"pred_c": "pred_c0", "true_c": "true_c0", "true_o": "true_o0"})
    last = df[df["offset"] == horizon - 1][["anchor_ts", "pred_c", "true_c"]].rename(
        columns={"pred_c": "pred_cN", "true_c": "true_cN"})
    win = first.merge(last, on="anchor_ts").sort_values("anchor_ts").reset_index(drop=True)

    # Predicted cumulative return (close-to-close over horizon)
    win["pred_ret"] = win["pred_cN"] / win["pred_c0"] - 1.0
    # Realized cumulative return — using true_o0 as entry (next-bar open after signal), true_cN as exit
    win["real_ret"] = win["true_cN"] / win["true_o0"] - 1.0

    # Signal
    win["signal"] = 0
    win.loc[win["pred_ret"] > threshold, "signal"] = 1
    win.loc[win["pred_ret"] < -threshold, "signal"] = -1

    # Non-overlap: a trade at anchor t occupies anchors [t, t+horizon-1]. Greedy non-overlap.
    chosen = []
    next_free = 0
    for idx in range(len(win)):
        if idx < next_free:
            continue
        if win["signal"].iloc[idx] != 0:
            chosen.append(idx)
            next_free = idx + horizon
    trades = win.iloc[chosen].copy().reset_index(drop=True)
    # PnL per trade
    trades["gross"] = trades["signal"] * trades["real_ret"]
    trades["net"] = trades["gross"] - ROUND_TRIP_COST
    # Equity curve
    if len(trades) == 0:
        return {
            "threshold": threshold, "n_trades": 0,
            "total_ret_pct": 0.0, "win_rate": float("nan"),
            "sharpe": float("nan"), "max_dd_pct": 0.0,
            "avg_net_per_trade_pct": float("nan"),
            "hodl_total_pct": (win["true_cN"].iloc[-1] / win["true_o0"].iloc[0] - 1.0) * 100,
        }

    eq = (1 + trades["net"]).cumprod()
    total_ret = float(eq.iloc[-1] - 1.0)
    max_dd = float(((eq / eq.cummax()) - 1.0).min())
    win_rate = float((trades["net"] > 0).mean())
    sharpe = float(trades["net"].mean() / trades["net"].std() * annualization_factor(tf, horizon)) if trades["net"].std() > 0 else float("nan")
    hodl_total = (win["true_cN"].iloc[-1] / win["true_o0"].iloc[0] - 1.0)
    avg_net = float(trades["net"].mean())
    return {
        "threshold": threshold,
        "n_trades": int(len(trades)),
        "total_ret_pct": round(total_ret * 100, 3),
        "hodl_total_pct": round(hodl_total * 100, 3),
        "win_rate": round(win_rate * 100, 2),
        "sharpe": round(sharpe, 3),
        "max_dd_pct": round(max_dd * 100, 3),
        "avg_net_per_trade_pct": round(avg_net * 100, 4),
    }


def main() -> int:
    rows = []
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            path = PRED_DIR / f"{symbol}_{tf}_kronos-small.parquet"
            if not path.exists():
                print(f"missing {path.name}")
                continue
            df = pd.read_parquet(path)
            for thr in THRESHOLDS:
                r = backtest(df, tf, thr)
                r["symbol"] = symbol
                r["tf"] = tf
                rows.append(r)

    out_df = pd.DataFrame(rows)[["symbol", "tf", "threshold", "n_trades", "total_ret_pct",
                                  "hodl_total_pct", "win_rate", "sharpe", "max_dd_pct",
                                  "avg_net_per_trade_pct"]]
    out_path = RESULTS_DIR / "idea1_direct_strategy.csv"
    out_df.to_csv(out_path, index=False)
    print(out_df.to_string(index=False))
    print(f"\n→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
