"""
Idea #4 — Tokenizer perplexity anomaly signal.

Uses ONLY the Kronos tokenizer (16 MB), not the transformer. The tokenizer quantises
OHLCV into a discrete vocab. Per-candle reconstruction error from encode→decode is a
proxy for how "anomalous" each candle is relative to the model's learned distribution.

Hypothesis: high-anomaly candles precede or coincide with regime shifts and predict
forward volatility (or in extreme cases, mean reversion / trend continuation).

Procedure:
- Encode rolling 480-candle windows, take per-step reconstruction error on the last candle.
- Build a per-anchor "surprisal" series.
- Test: does forward volatility / forward return correlate with surprisal?
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
from model import KronosTokenizer  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
RESULTS_DIR = HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
TF = "1h"
WINDOW = 480
FWD_LOOKAHEAD = 24  # measure forward vol/return over the next 24h


def main() -> int:
    os.environ.setdefault("HF_HOME", "/mnt/firmament/hf-cache")
    print("Loading tokenizer ...")
    tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    tok = tok.to(device).eval()

    all_rows = []
    for symbol in SYMBOLS:
        csv = DATA_DIR / f"{symbol}_{TF}_90d.csv"
        df = pd.read_csv(csv, parse_dates=["timestamps"])
        if len(df) < WINDOW + FWD_LOOKAHEAD:
            print(f"skip {symbol} — not enough data")
            continue

        feats = df[["open", "high", "low", "close", "volume", "amount"]].values.astype(np.float32)
        # Normalize per window (Kronos does its own normalization, but we mirror the predictor's clip=5 z-scoring)
        # Easiest: piggyback on KronosPredictor's preprocessing logic — replicate inline.
        per_candle_err = []
        n = len(df)
        ts_out = []

        t0 = time.perf_counter()
        for t in range(WINDOW, n - FWD_LOOKAHEAD):
            x = feats[t - WINDOW:t]
            mu = x.mean(axis=0, keepdims=True)
            sd = x.std(axis=0, keepdims=True) + 1e-9
            xz = np.clip((x - mu) / sd, -5, 5)
            xt = torch.from_numpy(xz).unsqueeze(0).to(device)

            with torch.no_grad():
                # Encode → decode roundtrip. Per-candle reconstruction error = surprisal proxy.
                # tokenizer.encode returns indices (possibly a tuple when half=True), tokenizer.decode reverses it.
                try:
                    indices = tok.encode(xt, half=True)
                    recon = tok.decode(indices, half=True)
                    # err on the LAST candle only (the newest one — that's our surprisal data point)
                    err = float(((recon[0, -1, :] - xt[0, -1, :]) ** 2).mean().item())
                except Exception as e:
                    if t == WINDOW:
                        print(f"Tokenizer encode/decode failed: {e}")
                    err = float("nan")

            per_candle_err.append(err)
            ts_out.append(df["timestamps"].iloc[t])

        elapsed = time.perf_counter() - t0
        print(f"{symbol}: {len(per_candle_err)} candles encoded in {elapsed:.1f}s")

        out = pd.DataFrame({"anchor_ts": ts_out, "surprisal": per_candle_err})
        # Forward stats
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        # Forward 24h return and realized vol (std of log returns)
        fwd_ret = []
        fwd_vol = []
        for t in range(WINDOW, n - FWD_LOOKAHEAD):
            fwd_ret.append(closes[t + FWD_LOOKAHEAD - 1] / closes[t] - 1)
            log_ret = np.diff(np.log(closes[t:t + FWD_LOOKAHEAD]))
            fwd_vol.append(float(np.std(log_ret)))
        out["fwd_ret"] = fwd_ret
        out["fwd_vol"] = fwd_vol

        # Bucket by surprisal quantile
        out["bucket"] = pd.qcut(out["surprisal"], q=5, labels=["p0_20", "p20_40", "p40_60", "p60_80", "p80_100"], duplicates="drop")
        agg = out.groupby("bucket", observed=True).agg(
            n=("surprisal", "size"),
            mean_surprisal=("surprisal", "mean"),
            mean_fwd_ret_pct=("fwd_ret", lambda x: x.mean() * 100),
            abs_fwd_ret_pct=("fwd_ret", lambda x: x.abs().mean() * 100),
            mean_fwd_vol=("fwd_vol", "mean"),
            fwd_long_winrate=("fwd_ret", lambda x: (x > 0).mean() * 100),
        ).reset_index()
        agg["symbol"] = symbol
        all_rows.append(agg)

    final = pd.concat(all_rows, ignore_index=True)[["symbol", "bucket", "n", "mean_surprisal",
                                                     "mean_fwd_ret_pct", "abs_fwd_ret_pct",
                                                     "mean_fwd_vol", "fwd_long_winrate"]]
    out_path = RESULTS_DIR / "idea4_tokenizer_perplexity.csv"
    final.to_csv(out_path, index=False)
    print(final.to_string(index=False))
    print(f"\n→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
