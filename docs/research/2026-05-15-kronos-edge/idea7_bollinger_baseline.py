"""
Idea #7 — Bollinger / z-score mean-reversion baselines, with optional Kronos filter.

Three variants, all on the same 90d BTC/ETH/LINK 1h data:

A. **Classical z-score MR** — entry when z-score of close vs N-bar mean exceeds threshold
   (long if z < -threshold, short if z > +threshold). Hold for fixed bars or until z mean-reverts.
B. **Vol-normalized MR** — same signal but position sized inversely to realized volatility.
C. **Kronos-gated MR** — fire the MR signal only when Kronos's 24h forecast agrees with the
   intended direction (long-MR only fires if Kronos also predicts up; short-MR only fires if
   Kronos also predicts down). Tests whether Kronos as a *filter* salvages MR on crypto perps.

Compares all three vs HODL.

Sweep grid:
  lookback (z-score window): [20, 50, 100]
  threshold:                 [1.5, 2.0, 2.5]
  hold_bars:                 [12, 24]
  exit:                      "z_neutral" or "fixed_bars"
"""
from __future__ import annotations

import math
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
PRED_DIR = HERE / "predictions"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
TF = "1h"

LOOKBACKS = [20, 50, 100]
THRESHOLDS_Z = [1.5, 2.0, 2.5]
HOLD_BARS = [12, 24]

FEE_PER_LEG = 0.00035
SLIPPAGE = 0.00050
ROUND_TRIP_COST = (FEE_PER_LEG + SLIPPAGE) * 2


def load_candles(symbol: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{symbol}_{TF}_90d.csv", parse_dates=["timestamps"])
    df = df.sort_values("timestamps").reset_index(drop=True)
    df["log_ret_1"] = np.log(df["close"]).diff()
    return df


def load_kronos_signal(symbol: str) -> pd.DataFrame | None:
    """Per-anchor predicted 24h cumulative return (sign = Kronos direction)."""
    path = PRED_DIR / f"{symbol}_{TF}_kronos-small.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    horizon = df["offset"].max() + 1
    p0 = df[df["offset"] == 0][["anchor_ts", "pred_c"]].rename(columns={"pred_c": "pred_c0"})
    pn = df[df["offset"] == horizon - 1][["anchor_ts", "pred_c"]].rename(columns={"pred_c": "pred_cN"})
    s = p0.merge(pn, on="anchor_ts")
    s["pred_24h_dir"] = np.sign(s["pred_cN"] / s["pred_c0"] - 1)
    s["anchor_ts"] = pd.to_datetime(s["anchor_ts"], utc=True)
    return s[["anchor_ts", "pred_24h_dir"]]


def backtest(candles: pd.DataFrame, lookback: int, thr: float, hold: int,
             kronos: pd.DataFrame | None, variant: str) -> dict:
    """Vectorized non-overlapping backtest."""
    px = candles["close"].values
    ts = candles["timestamps"].values

    # Z-score of close vs rolling mean
    mean = candles["close"].rolling(lookback).mean().values
    std = candles["close"].rolling(lookback).std().values
    z = (px - mean) / std

    # Vol-norm sizing
    realized_vol = candles["log_ret_1"].rolling(lookback).std().values  # per-bar vol

    # Kronos lookup as a {ts → dir} map for fast iteration
    k_map = {}
    if kronos is not None:
        for _, row in kronos.iterrows():
            k_map[pd.Timestamp(row["anchor_ts"]).tz_localize(None)] = row["pred_24h_dir"]

    chosen = []
    n = len(candles)
    next_free = lookback
    trades = []
    for i in range(lookback, n - hold):
        if i < next_free:
            continue
        zi = z[i]
        if math.isnan(zi):
            continue
        signal = 0
        if zi <= -thr:
            signal = 1   # long the dip
        elif zi >= thr:
            signal = -1  # short the rip
        if signal == 0:
            continue

        if variant == "kronos_gated":
            anchor_ts = pd.Timestamp(ts[i]).tz_localize(None)
            k_dir = k_map.get(anchor_ts, None)
            if k_dir is None or np.sign(k_dir) != signal:
                continue

        entry = px[i]
        exit_px = px[i + hold]
        gross = signal * (exit_px / entry - 1.0)

        if variant == "vol_norm":
            # Scale position by 1 / vol so each trade ~ equal risk
            target_risk = 0.01  # 1% per trade
            size = target_risk / max(realized_vol[i], 1e-6)
            size = float(np.clip(size, 0.1, 5.0))
        else:
            size = 1.0

        net = gross * size - ROUND_TRIP_COST * size
        trades.append({"signal": signal, "gross": gross, "net": net, "size": size})
        next_free = i + hold

    if not trades:
        return {"n_trades": 0}
    tdf = pd.DataFrame(trades)
    eq = (1 + tdf["net"]).cumprod()
    total = float(eq.iloc[-1] - 1)
    mdd = float(((eq / eq.cummax()) - 1).min())
    sharpe = float(tdf["net"].mean() / tdf["net"].std() * math.sqrt(365 * 24 / hold)) if tdf["net"].std() > 0 else float("nan")
    return {
        "n_trades": int(len(tdf)),
        "win_rate": round(float((tdf["net"] > 0).mean()) * 100, 2),
        "avg_net_pct": round(float(tdf["net"].mean()) * 100, 4),
        "total_ret_pct": round(total * 100, 3),
        "max_dd_pct": round(mdd * 100, 3),
        "sharpe": round(sharpe, 3),
        "avg_size": round(float(tdf["size"].mean()), 3),
    }


def main() -> int:
    rows = []
    for symbol in SYMBOLS:
        candles = load_candles(symbol)
        kronos = load_kronos_signal(symbol)
        hodl_ret = (candles["close"].iloc[-1] / candles["close"].iloc[100] - 1) * 100  # from end of first lookback window

        for variant in ["classical", "vol_norm"] + (["kronos_gated"] if kronos is not None else []):
            for lookback, thr, hold in product(LOOKBACKS, THRESHOLDS_Z, HOLD_BARS):
                r = backtest(candles, lookback, thr, hold, kronos, variant)
                r["symbol"] = symbol
                r["variant"] = variant
                r["lookback"] = lookback
                r["thr"] = thr
                r["hold"] = hold
                r["hodl_pct"] = round(float(hodl_ret), 3)
                rows.append(r)

    out_df = pd.DataFrame(rows)
    cols = ["symbol", "variant", "lookback", "thr", "hold", "n_trades", "win_rate",
            "avg_net_pct", "total_ret_pct", "hodl_pct", "max_dd_pct", "sharpe", "avg_size"]
    out_df = out_df[cols].sort_values(["symbol", "variant", "sharpe"], ascending=[True, True, False])
    out_path = RESULTS_DIR / "idea7_bollinger_baseline.csv"
    out_df.to_csv(out_path, index=False)

    # Best per (symbol, variant)
    best = out_df.groupby(["symbol", "variant"]).head(1).reset_index(drop=True)
    print("\nBest config per (symbol, variant):\n")
    print(best.to_string(index=False))
    print(f"\nFull sweep → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
