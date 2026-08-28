"""
Idea #5 — Multi-timeframe coherence.

Hypothesis: when the 1h forecast direction agrees with the 4h forecast direction at the
same anchor time, the trade has higher conviction and out-of-sample edge increases.

Procedure:
- Align 4h windows to 1h anchors by floor(anchor_ts) to 4h boundary.
- For each aligned pair, compute sign(pred_24h_ret_1h) and sign(pred_24h_ret_4h).
- Bucket trades by agree/disagree. Compute Sharpe + win rate per bucket.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PRED_DIR = HERE / "predictions"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
FEE_PER_LEG = 0.00035
SLIPPAGE = 0.00050
ROUND_TRIP_COST = (FEE_PER_LEG + SLIPPAGE) * 2


def load_summary(symbol: str, tf: str) -> pd.DataFrame:
    path = PRED_DIR / f"{symbol}_{tf}_kronos-small.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    horizon = df["offset"].max() + 1
    p0 = df[df["offset"] == 0][["anchor_ts", "pred_c", "true_c", "true_o"]].rename(
        columns={"pred_c": "pred_c0", "true_c": "true_c0", "true_o": "true_o0"})
    pn = df[df["offset"] == horizon - 1][["anchor_ts", "pred_c", "true_c"]].rename(
        columns={"pred_c": "pred_cN", "true_c": "true_cN"})
    s = p0.merge(pn, on="anchor_ts")
    s["pred_ret"] = s["pred_cN"] / s["pred_c0"] - 1
    s["real_ret"] = s["true_cN"] / s["true_o0"] - 1
    s["anchor_ts"] = pd.to_datetime(s["anchor_ts"], utc=True)
    return s.sort_values("anchor_ts").reset_index(drop=True)


def main() -> int:
    rows_out = []
    for symbol in SYMBOLS:
        h1 = load_summary(symbol, "1h")
        h4 = load_summary(symbol, "4h")
        if h1.empty or h4.empty:
            continue
        # Align: for each 1h anchor, the most recent 4h anchor at or before it
        h4 = h4.set_index("anchor_ts").sort_index()
        h1["aligned_4h_ts"] = h1["anchor_ts"].apply(
            lambda t: h4.index[h4.index <= t].max() if (h4.index <= t).any() else pd.NaT)
        h1 = h1.dropna(subset=["aligned_4h_ts"])
        h1["pred_ret_4h"] = h1["aligned_4h_ts"].map(h4["pred_ret"])
        h1["sign_1h"] = np.sign(h1["pred_ret"])
        h1["sign_4h"] = np.sign(h1["pred_ret_4h"])
        h1["agree"] = (h1["sign_1h"] == h1["sign_4h"]) & (h1["sign_1h"] != 0)
        # Trade direction = 1h sign when agree. Net pnl after costs.
        h1["trade_signal"] = np.where(h1["agree"], h1["sign_1h"], 0)
        h1["gross"] = h1["trade_signal"] * h1["real_ret"]
        h1["net"] = np.where(h1["trade_signal"] != 0, h1["gross"] - ROUND_TRIP_COST, 0)

        # Disagree-disagree bucket: take 1h direction only
        h1["disagree_signal"] = np.where(~h1["agree"] & (h1["sign_1h"] != 0), h1["sign_1h"], 0)
        h1["disagree_net"] = np.where(h1["disagree_signal"] != 0,
                                       h1["disagree_signal"] * h1["real_ret"] - ROUND_TRIP_COST, 0)

        # Non-overlap (every 24h)
        horizon = 24
        chosen = []
        next_free = 0
        for idx in range(len(h1)):
            if idx < next_free:
                continue
            if h1["trade_signal"].iloc[idx] != 0:
                chosen.append(idx)
                next_free = idx + horizon
        agree_trades = h1.iloc[chosen]

        chosen_d = []
        next_free = 0
        for idx in range(len(h1)):
            if idx < next_free:
                continue
            if h1["disagree_signal"].iloc[idx] != 0:
                chosen_d.append(idx)
                next_free = idx + horizon
        disagree_trades = h1.iloc[chosen_d]

        for label, t in [("agree", agree_trades), ("disagree", disagree_trades)]:
            if len(t) == 0:
                continue
            net = t["net"] if label == "agree" else t["disagree_net"]
            eq = (1 + net).cumprod()
            sharpe = (net.mean() / net.std() * np.sqrt(365)) if net.std() > 0 else float("nan")
            rows_out.append({
                "symbol": symbol,
                "bucket": label,
                "n_trades": int(len(t)),
                "win_rate": round(float((net > 0).mean()) * 100, 2),
                "avg_net_pct": round(float(net.mean()) * 100, 4),
                "total_ret_pct": round(float(eq.iloc[-1] - 1) * 100, 3),
                "sharpe": round(float(sharpe), 3),
            })

    out_df = pd.DataFrame(rows_out)
    out_path = RESULTS_DIR / "idea5_mtf_coherence.csv"
    out_df.to_csv(out_path, index=False)
    print(out_df.to_string(index=False))
    print(f"\n→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
