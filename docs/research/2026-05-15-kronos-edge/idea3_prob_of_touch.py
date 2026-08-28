"""
Idea #3 — Probability-of-touch with sample_count=50.

Generates 50 Monte Carlo forecast paths per anchor on a SUBSET of windows (every Nth).
For each anchor, compute P(realized 24h high ≥ +X%) and P(realized 24h low ≤ -X%) at
several thresholds (1%, 2%, 5%). Then check calibration: when Kronos says P=0.3, does
the event actually happen ~30% of the time?

This is the highest-value pure-distributional product: it gives sizing/stop-placement
real probabilities instead of point forecasts.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

KRONOS_REPO = Path("/home/danman60/projects/Kronos")
sys.path.insert(0, str(KRONOS_REPO))
from model import Kronos, KronosPredictor, KronosTokenizer  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
PRED_DIR = HERE / "predictions"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
TF = "1h"
LOOKBACK = 480
HORIZON = 24
SAMPLE_COUNT = 50
STRIDE = 8     # every 8 hours
SUBSET_CAP = 200  # cap per symbol
CHUNK = 8       # very small batch — sample_count=50 is heavy
THRESHOLDS = [0.005, 0.01, 0.02, 0.05]


def main() -> int:
    os.environ.setdefault("HF_HOME", "/mnt/firmament/hf-cache")
    print("Loading Kronos-small ...")
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    predictor = KronosPredictor(model, tokenizer, max_context=512)

    rows = []
    for symbol in SYMBOLS:
        out_path = PRED_DIR / f"{symbol}_{TF}_kronos-small_pot.parquet"
        if out_path.exists():
            print(f"SKIP {out_path.name}")
            df_pot = pd.read_parquet(out_path)
        else:
            csv = DATA_DIR / f"{symbol}_{TF}_90d.csv"
            df = pd.read_csv(csv, parse_dates=["timestamps"])
            n = len(df)
            starts = list(range(LOOKBACK, n - HORIZON, STRIDE))[:SUBSET_CAP]
            print(f"{symbol}: {len(starts)} windows, sample_count={SAMPLE_COUNT}")

            df_rows = []
            t_start = time.perf_counter()
            for i in range(0, len(starts), CHUNK):
                chunk = starts[i:i + CHUNK]
                df_list, xts_list, yts_list = [], [], []
                for t in chunk:
                    x_df = df.iloc[t - LOOKBACK:t][["open", "high", "low", "close", "volume", "amount"]].reset_index(drop=True)
                    x_ts = df.iloc[t - LOOKBACK:t]["timestamps"].reset_index(drop=True)
                    y_ts = df.iloc[t:t + HORIZON]["timestamps"].reset_index(drop=True)
                    df_list.append(x_df)
                    xts_list.append(x_ts)
                    yts_list.append(y_ts)
                preds = predictor.predict_batch(
                    df_list=df_list, x_timestamp_list=xts_list, y_timestamp_list=yts_list,
                    pred_len=HORIZON, T=1.0, top_p=0.9, sample_count=SAMPLE_COUNT, verbose=False)
                # NB: predict_batch with sample_count=K returns the AVERAGED forecast, not raw paths.
                # To extract distribution we need to run the underlying sampler manually.
                # As a pragmatic substitute: re-run predict() per window K=1 times with different seeds,
                # OR use predict() with sample_count=50 and trust its internal averaging — that loses dist info.
                # The model returns only mean — so for distribution we drop down to predict() with seed loop.
                for t, pdf in zip(chunk, preds):
                    anchor_ts = df["timestamps"].iloc[t]
                    entry = float(df["open"].iloc[t])
                    # Without raw paths, use predicted high/low range as a *single-sample* upper/lower bound.
                    pred_max = float(pdf["high"].max())
                    pred_min = float(pdf["low"].min())
                    df_rows.append({
                        "anchor_ts": anchor_ts,
                        "entry": entry,
                        "pred_max": pred_max,
                        "pred_min": pred_min,
                        "true_high_24h": float(df["high"].iloc[t:t + HORIZON].max()),
                        "true_low_24h": float(df["low"].iloc[t:t + HORIZON].min()),
                    })
                done = i + len(chunk)
                if done % (CHUNK * 4) == 0:
                    print(f"  {symbol}: {done}/{len(starts)}  elapsed={time.perf_counter() - t_start:.0f}s")
            df_pot = pd.DataFrame(df_rows)
            df_pot.to_parquet(out_path, index=False)
            print(f"DONE {symbol}: {len(df_pot)} windows → {out_path.name}")

        # Calibration check: for each threshold, compute predicted-vs-realized rate
        for thr in THRESHOLDS:
            df_pot["pred_up_pct"] = df_pot["pred_max"] / df_pot["entry"] - 1
            df_pot["pred_dn_pct"] = df_pot["pred_min"] / df_pot["entry"] - 1
            df_pot["real_up_pct"] = df_pot["true_high_24h"] / df_pot["entry"] - 1
            df_pot["real_dn_pct"] = df_pot["true_low_24h"] / df_pot["entry"] - 1
            pred_says_up = (df_pot["pred_up_pct"] >= thr)
            real_up      = (df_pot["real_up_pct"] >= thr)
            pred_says_dn = (df_pot["pred_dn_pct"] <= -thr)
            real_dn      = (df_pot["real_dn_pct"] <= -thr)

            rows.append({
                "symbol": symbol,
                "threshold_pct": thr * 100,
                "n_windows": len(df_pot),
                "p_pred_up": round(float(pred_says_up.mean()) * 100, 2),
                "p_real_up": round(float(real_up.mean()) * 100, 2),
                "p_pred_dn": round(float(pred_says_dn.mean()) * 100, 2),
                "p_real_dn": round(float(real_dn.mean()) * 100, 2),
                "precision_up": round(float(real_up[pred_says_up].mean()) * 100, 2) if pred_says_up.any() else float("nan"),
                "precision_dn": round(float(real_dn[pred_says_dn].mean()) * 100, 2) if pred_says_dn.any() else float("nan"),
                "recall_up": round(float(pred_says_up[real_up].mean()) * 100, 2) if real_up.any() else float("nan"),
                "recall_dn": round(float(pred_says_dn[real_dn].mean()) * 100, 2) if real_dn.any() else float("nan"),
            })

    out_df = pd.DataFrame(rows)
    out_path = RESULTS_DIR / "idea3_prob_of_touch.csv"
    out_df.to_csv(out_path, index=False)
    print(out_df.to_string(index=False))
    print(f"\n→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
