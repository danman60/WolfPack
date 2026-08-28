"""
Strategy: "Short the rally" — short-only momentum-fade.

Entry: 24h rally ≥ X% AND RSI(14) ≥ R AND price > SMA(20) + K*std
Exit: TP at -Y% from entry, SL at +Z%, timeout at H bars (first to trigger wins)
Symbols: BTC, ETH, LINK, DOGE 1h
Costs: 0.085% round-trip (3.5 bps fee + 5 bps slip per leg)
Validation: 60d in-sample to pick best config per symbol, 30d OOS to verify.

Walk-forward: also runs 3 sequential folds for stability check.
"""
from __future__ import annotations

import math
from itertools import product
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

GRID = {
    "rally_lookback": [4, 6, 12],     # shorter lookback → more fires
    "rally_thr_pct": [1.0, 1.5, 2.5], # lower thresholds → many more fires
    "rsi_thr": [55, 60, 65, 70],
    "tp_pct": [1.0, 1.5, 2.0, 3.0],
    "sl_pct": [1.5, 2.5, 4.0],
    "hold_bars": [6, 12, 24],
}


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    diff = np.diff(close, prepend=close[0])
    gain = np.where(diff > 0, diff, 0.0)
    loss = np.where(diff < 0, -diff, 0.0)
    # Wilder smoothing
    avg_gain = np.zeros_like(close)
    avg_loss = np.zeros_like(close)
    avg_gain[:period] = np.mean(gain[:period])
    avg_loss[:period] = np.mean(loss[:period])
    for i in range(period, len(close)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period
    rs = avg_gain / np.maximum(avg_loss, 1e-12)
    return 100 - (100 / (1 + rs))


def backtest(candles: pd.DataFrame, rally_lb: int, rally_thr: float, rsi_thr: float,
             tp_pct: float, sl_pct: float, hold_bars: int) -> dict:
    """Run vectorized short-only backtest. Returns metrics dict."""
    close = candles["close"].values
    open_ = candles["open"].values
    high = candles["high"].values
    low = candles["low"].values
    n = len(candles)
    rsi_v = rsi(close, 14)

    trades = []
    next_free = max(rally_lb, 20)
    for i in range(max(rally_lb, 20), n - hold_bars):
        if i < next_free:
            continue
        # Rally check: close[i] / close[i-rally_lb] - 1
        rally = close[i] / close[i - rally_lb] - 1.0
        if rally < rally_thr / 100.0:
            continue
        if rsi_v[i] < rsi_thr:
            continue
        # Enter SHORT at next bar's open
        entry_idx = i + 1
        if entry_idx >= n - 1:
            continue
        entry = open_[entry_idx]
        tp_price = entry * (1 - tp_pct / 100.0)
        sl_price = entry * (1 + sl_pct / 100.0)

        # Walk forward, first-touch logic on intrabar
        exit_idx = None
        exit_price = None
        exit_reason = None
        for k in range(entry_idx, min(entry_idx + hold_bars, n)):
            bar_high = high[k]
            bar_low = low[k]
            # Short: SL is up, TP is down. If both could trigger same bar, assume worst (SL first).
            if bar_high >= sl_price:
                exit_idx = k
                exit_price = sl_price
                exit_reason = "sl"
                break
            if bar_low <= tp_price:
                exit_idx = k
                exit_price = tp_price
                exit_reason = "tp"
                break
        if exit_idx is None:
            exit_idx = entry_idx + hold_bars - 1
            exit_idx = min(exit_idx, n - 1)
            exit_price = close[exit_idx]
            exit_reason = "timeout"

        gross = (entry - exit_price) / entry  # short pnl
        net = gross - ROUND_TRIP
        trades.append({"entry_idx": entry_idx, "exit_idx": exit_idx,
                       "gross": gross, "net": net, "reason": exit_reason})
        next_free = exit_idx + 1

    if not trades:
        return {"n": 0, "total_pct": 0.0, "win_rate": float("nan"), "sharpe": float("nan"),
                "tp_rate": 0.0, "sl_rate": 0.0, "timeout_rate": 0.0, "max_dd_pct": 0.0}
    nets = np.array([t["net"] for t in trades])
    eq = np.cumprod(1 + nets)
    sharpe = float(nets.mean() / nets.std() * math.sqrt(365)) if nets.std() > 0 else float("nan")
    mdd = float(((eq / np.maximum.accumulate(eq)) - 1).min())
    reasons = [t["reason"] for t in trades]
    return {
        "n": len(trades),
        "win_rate": round(float((nets > 0).mean()) * 100, 2),
        "avg_net_pct": round(float(nets.mean()) * 100, 4),
        "total_pct": round(float(eq[-1] - 1) * 100, 3),
        "max_dd_pct": round(mdd * 100, 3),
        "sharpe": round(sharpe, 3),
        "tp_rate": round(reasons.count("tp") / len(reasons) * 100, 1),
        "sl_rate": round(reasons.count("sl") / len(reasons) * 100, 1),
        "timeout_rate": round(reasons.count("timeout") / len(reasons) * 100, 1),
    }


def grid_sweep(candles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rl, rt, rs_, tp, sl, hb in product(
        GRID["rally_lookback"], GRID["rally_thr_pct"], GRID["rsi_thr"],
        GRID["tp_pct"], GRID["sl_pct"], GRID["hold_bars"]):
        m = backtest(candles, rl, rt, rs_, tp, sl, hb)
        m.update({"rally_lb": rl, "rally_thr": rt, "rsi_thr": rs_,
                  "tp_pct": tp, "sl_pct": sl, "hold_bars": hb})
        rows.append(m)
    return pd.DataFrame(rows)


def main() -> int:
    all_full = []
    all_oos = []
    walkforward = []
    for symbol in SYMBOLS:
        csv = DATA / f"{symbol}_1h_90d.csv"
        if not csv.exists():
            print(f"missing {csv.name}")
            continue
        candles = pd.read_csv(csv, parse_dates=["timestamps"]).sort_values("timestamps").reset_index(drop=True)
        hodl_full = (candles["close"].iloc[-1] / candles["close"].iloc[0] - 1) * 100

        # === FULL-WINDOW SWEEP ===
        sweep = grid_sweep(candles)
        sweep["symbol"] = symbol
        best_full = sweep.sort_values("sharpe", ascending=False).head(1).iloc[0]
        all_full.append(sweep)

        # === IS/OOS split ===
        cut = int(len(candles) * 2 / 3)
        ins = candles.iloc[:cut].reset_index(drop=True)
        oos = candles.iloc[cut:].reset_index(drop=True)
        hodl_oos = (oos["close"].iloc[-1] / oos["close"].iloc[0] - 1) * 100
        is_sweep = grid_sweep(ins).sort_values("sharpe", ascending=False)
        # Take best config from IS that has n >= 5 (we need at least some trades to trust)
        is_best = is_sweep[is_sweep["n"] >= 5].head(1)
        if len(is_best) == 0:
            print(f"{symbol}: IS produced no config with n≥5")
            continue
        is_best_row = is_best.iloc[0]
        oos_m = backtest(oos, int(is_best_row["rally_lb"]), float(is_best_row["rally_thr"]),
                         float(is_best_row["rsi_thr"]), float(is_best_row["tp_pct"]),
                         float(is_best_row["sl_pct"]), int(is_best_row["hold_bars"]))
        all_oos.append({
            "symbol": symbol,
            "is_n": int(is_best_row["n"]),
            "is_total_pct": float(is_best_row["total_pct"]),
            "is_sharpe": float(is_best_row["sharpe"]),
            "is_win_rate": float(is_best_row["win_rate"]),
            "oos_n": oos_m["n"],
            "oos_total_pct": oos_m["total_pct"],
            "oos_sharpe": oos_m["sharpe"],
            "oos_win_rate": oos_m["win_rate"],
            "oos_hodl_pct": round(hodl_oos, 3),
            "best_rally_lb": int(is_best_row["rally_lb"]),
            "best_rally_thr": float(is_best_row["rally_thr"]),
            "best_rsi_thr": float(is_best_row["rsi_thr"]),
            "best_tp_pct": float(is_best_row["tp_pct"]),
            "best_sl_pct": float(is_best_row["sl_pct"]),
            "best_hold_bars": int(is_best_row["hold_bars"]),
        })

        # === WALK-FORWARD: 3 folds ===
        N = len(candles)
        fold_size = N // 4
        # Fold1: train [0, fold_size*2], test [fold_size*2, fold_size*3]
        # Fold2: train [fold_size, fold_size*3], test [fold_size*3, N]
        # Fold3: train [0, fold_size*3], test [fold_size*3, N]
        folds = [
            (0, fold_size * 2, fold_size * 2, fold_size * 3),
            (fold_size, fold_size * 3, fold_size * 3, N),
            (0, fold_size * 3, fold_size * 3, N),
        ]
        for fi, (t0, t1, e0, e1) in enumerate(folds):
            train_df = candles.iloc[t0:t1].reset_index(drop=True)
            test_df = candles.iloc[e0:e1].reset_index(drop=True)
            train_sweep = grid_sweep(train_df).sort_values("sharpe", ascending=False)
            tb = train_sweep[train_sweep["n"] >= 3].head(1)
            if len(tb) == 0:
                continue
            tb_row = tb.iloc[0]
            tm = backtest(test_df, int(tb_row["rally_lb"]), float(tb_row["rally_thr"]),
                          float(tb_row["rsi_thr"]), float(tb_row["tp_pct"]),
                          float(tb_row["sl_pct"]), int(tb_row["hold_bars"]))
            walkforward.append({
                "symbol": symbol, "fold": fi + 1,
                "train_n": int(tb_row["n"]), "train_total_pct": float(tb_row["total_pct"]), "train_sharpe": float(tb_row["sharpe"]),
                "test_n": tm["n"], "test_total_pct": tm["total_pct"], "test_sharpe": tm["sharpe"],
            })

    # Save
    full_df = pd.concat(all_full, ignore_index=True)
    oos_df = pd.DataFrame(all_oos)
    wf_df = pd.DataFrame(walkforward)
    full_df.to_csv(RESULTS / "short_rally_sweep_full.csv", index=False)
    oos_df.to_csv(RESULTS / "short_rally_oos.csv", index=False)
    wf_df.to_csv(RESULTS / "short_rally_walkforward.csv", index=False)

    print("\n=== BEST CONFIG PER SYMBOL (full 90d sweep, sorted by Sharpe) ===")
    best = full_df.sort_values(["symbol", "sharpe"], ascending=[True, False]).groupby("symbol").head(1)
    print(best[["symbol", "rally_lb", "rally_thr", "rsi_thr", "tp_pct", "sl_pct", "hold_bars",
                "n", "win_rate", "total_pct", "sharpe", "tp_rate", "sl_rate", "timeout_rate"]].to_string(index=False))

    print("\n=== IN-SAMPLE → OUT-OF-SAMPLE (60d / 30d split) ===")
    print(oos_df[["symbol", "is_n", "is_total_pct", "is_sharpe", "is_win_rate",
                  "oos_n", "oos_total_pct", "oos_sharpe", "oos_win_rate", "oos_hodl_pct"]].to_string(index=False))

    print("\n=== WALK-FORWARD (3 folds per symbol) ===")
    print(wf_df.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
