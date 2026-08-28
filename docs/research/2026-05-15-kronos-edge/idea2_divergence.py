"""
Idea #2 — Predict-vs-realize divergence signal.

Hypothesis: when realized price diverges materially from Kronos's forecast in the FIRST
few hours of a window, the residual itself carries forward-looking information (regime
shift / news event). Test: does a large early divergence predict the remainder of the
24h window's return direction?

Procedure per anchor t:
- After early_horizon (e.g. 4) candles, measure residual:
    residual = realized_return(0→early) - predicted_return(0→early)
- Forward look: what's the realized return from `early` to `horizon`?
- Bucket by |residual|. Compute mean forward return per bucket, sign coherence.

Output: results/idea2_divergence.csv
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
TIMEFRAMES = ["1h", "4h"]
EARLY = 4  # candles


def analyze(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    horizon = df["offset"].max() + 1
    # Pivot per anchor: prices at offset 0, EARLY-1, horizon-1
    p0 = df[df["offset"] == 0][["anchor_ts", "pred_c", "true_c", "true_o"]].rename(
        columns={"pred_c": "pred_c0", "true_c": "true_c0", "true_o": "true_o0"})
    pe = df[df["offset"] == EARLY - 1][["anchor_ts", "pred_c", "true_c"]].rename(
        columns={"pred_c": "pred_cE", "true_c": "true_cE"})
    pn = df[df["offset"] == horizon - 1][["anchor_ts", "pred_c", "true_c"]].rename(
        columns={"pred_c": "pred_cN", "true_c": "true_cN"})
    win = p0.merge(pe, on="anchor_ts").merge(pn, on="anchor_ts").sort_values("anchor_ts").reset_index(drop=True)

    win["pred_early_ret"] = win["pred_cE"] / win["pred_c0"] - 1
    win["real_early_ret"] = win["true_cE"] / win["true_o0"] - 1
    win["residual_early"] = win["real_early_ret"] - win["pred_early_ret"]
    # Forward look: E → N
    win["fwd_real_ret"] = win["true_cN"] / win["true_cE"] - 1

    # Bucket by residual magnitude and sign
    q = win["residual_early"].abs().quantile([0.5, 0.75, 0.90, 0.95]).to_list()
    out = []
    for label, lo, hi in [
        ("|res| < p50", 0, q[0]),
        ("p50 ≤ |res| < p75", q[0], q[1]),
        ("p75 ≤ |res| < p90", q[1], q[2]),
        ("p90 ≤ |res| < p95", q[2], q[3]),
        ("|res| ≥ p95", q[3], float("inf")),
    ]:
        mask = (win["residual_early"].abs() >= lo) & (win["residual_early"].abs() < hi)
        if mask.sum() == 0:
            continue
        sub = win[mask]
        # Test: does fwd return tend to follow residual direction, or revert against it?
        follow_mean = (np.sign(sub["residual_early"]) * sub["fwd_real_ret"]).mean()
        revert_mean = (-np.sign(sub["residual_early"]) * sub["fwd_real_ret"]).mean()
        out.append({
            "tf": tf,
            "bucket": label,
            "lo_abs_res": round(lo, 4),
            "hi_abs_res": round(hi, 4) if hi != float("inf") else None,
            "n": int(mask.sum()),
            "mean_fwd_ret_pct": round(sub["fwd_real_ret"].mean() * 100, 3),
            "follow_residual_pct": round(follow_mean * 100, 3),   # positive = momentum carries
            "revert_residual_pct": round(revert_mean * 100, 3),   # positive = mean reversion
            "fwd_win_rate_long": round((sub["fwd_real_ret"] > 0).mean() * 100, 2),
        })
    return pd.DataFrame(out)


def main() -> int:
    rows = []
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            path = PRED_DIR / f"{symbol}_{tf}_kronos-small.parquet"
            if not path.exists():
                print(f"missing {path.name}")
                continue
            df = pd.read_parquet(path)
            sub = analyze(df, tf)
            sub["symbol"] = symbol
            rows.append(sub)
    all_df = pd.concat(rows, ignore_index=True)[["symbol", "tf", "bucket", "n", "mean_fwd_ret_pct",
                                                  "follow_residual_pct", "revert_residual_pct",
                                                  "fwd_win_rate_long", "lo_abs_res", "hi_abs_res"]]
    out_path = RESULTS_DIR / "idea2_divergence.csv"
    all_df.to_csv(out_path, index=False)
    print(all_df.to_string(index=False))
    print(f"\n→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
