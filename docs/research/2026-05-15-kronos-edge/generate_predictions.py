"""
Generate Kronos prediction database.

For each anchor candle t in the dataset:
- predicts the next `horizon` candles given prior `lookback` candles
- stores forecast OHLCV in long format (anchor_ts, offset, ...)
- also stores realized truth alongside (so analyses don't need separate joins)

Output: predictions/<symbol>_<tf>_kronos-small.parquet
        Long format: anchor_ts, offset_idx, symbol, tf,
                     pred_o/h/l/c/v, true_o/h/l/c/v

Sampling: sample_count=4 for main pass (averages 4 paths for stable median forecast).
A separate script `prob_of_touch.py` re-runs sample_count=50 on a subset for distributional analysis.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import torch

# Path setup — let us import Kronos's model module
KRONOS_REPO = Path("/home/danman60/projects/Kronos")
sys.path.insert(0, str(KRONOS_REPO))
from model import Kronos, KronosPredictor, KronosTokenizer  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
PRED_DIR = HERE / "predictions"
PRED_DIR.mkdir(exist_ok=True)

# Plan per timeframe
PLAN = {
    "1h": {"lookback": 480, "horizon": 24, "stride": 1},
    "4h": {"lookback": 256, "horizon": 24, "stride": 1},
}
SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
SAMPLE_COUNT = 4
CHUNK = 32  # batch size for predict_batch — keeps VRAM happy on 3060
T = 1.0
TOP_P = 0.9


def load_models():
    os.environ.setdefault("HF_HOME", "/mnt/firmament/hf-cache")
    print("Loading Kronos-small + tokenizer ...")
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    predictor = KronosPredictor(model, tokenizer, max_context=512)
    print(f"  device={predictor.device}")
    return predictor


def generate_for(predictor: KronosPredictor, symbol: str, tf: str) -> None:
    out_path = PRED_DIR / f"{symbol}_{tf}_kronos-small.parquet"
    if out_path.exists():
        print(f"SKIP {out_path.name} (exists)")
        return

    plan = PLAN[tf]
    lookback = plan["lookback"]
    horizon = plan["horizon"]
    stride = plan["stride"]

    src = DATA_DIR / f"{symbol}_{tf}_90d.csv"
    df = pd.read_csv(src, parse_dates=["timestamps"])
    n = len(df)

    # Build window indices: anchor index t is the FIRST predicted candle.
    # x = df[t-lookback : t]
    # y_ts = df[t : t+horizon]
    starts = list(range(lookback, n - horizon, stride))
    print(f"{symbol} {tf}: n={n} windows={len(starts)} lookback={lookback} horizon={horizon}")

    all_rows = []
    t_start = time.perf_counter()
    last_log = t_start

    for i in range(0, len(starts), CHUNK):
        chunk_starts = starts[i:i + CHUNK]
        df_list, xts_list, yts_list = [], [], []
        for t in chunk_starts:
            x_df = df.iloc[t - lookback:t][["open", "high", "low", "close", "volume", "amount"]].reset_index(drop=True)
            x_ts = df.iloc[t - lookback:t]["timestamps"].reset_index(drop=True)
            y_ts = df.iloc[t:t + horizon]["timestamps"].reset_index(drop=True)
            df_list.append(x_df)
            xts_list.append(x_ts)
            yts_list.append(y_ts)

        pred_list = predictor.predict_batch(
            df_list=df_list,
            x_timestamp_list=xts_list,
            y_timestamp_list=yts_list,
            pred_len=horizon,
            T=T,
            top_p=TOP_P,
            sample_count=SAMPLE_COUNT,
            verbose=False,
        )

        for t, pred_df in zip(chunk_starts, pred_list):
            anchor_ts = df["timestamps"].iloc[t]
            true_block = df.iloc[t:t + horizon][["open", "high", "low", "close", "volume"]].reset_index(drop=True)
            for off in range(horizon):
                all_rows.append({
                    "anchor_ts": anchor_ts,
                    "offset": off,
                    "symbol": symbol,
                    "tf": tf,
                    "pred_o": float(pred_df["open"].iloc[off]),
                    "pred_h": float(pred_df["high"].iloc[off]),
                    "pred_l": float(pred_df["low"].iloc[off]),
                    "pred_c": float(pred_df["close"].iloc[off]),
                    "pred_v": float(pred_df["volume"].iloc[off]),
                    "true_o": float(true_block["open"].iloc[off]),
                    "true_h": float(true_block["high"].iloc[off]),
                    "true_l": float(true_block["low"].iloc[off]),
                    "true_c": float(true_block["close"].iloc[off]),
                    "true_v": float(true_block["volume"].iloc[off]),
                })

        now = time.perf_counter()
        done = i + len(chunk_starts)
        rate = done / (now - t_start)
        eta_s = (len(starts) - done) / rate if rate > 0 else 0
        if now - last_log > 10:
            print(f"  {symbol} {tf}  {done}/{len(starts)}  rate={rate:.1f}/s  eta={eta_s:.0f}s")
            last_log = now

    elapsed = time.perf_counter() - t_start
    out_df = pd.DataFrame(all_rows)
    # Defensive: try parquet, fall back to pickle so the work is never lost
    try:
        out_df.to_parquet(out_path, index=False)
    except Exception as e:
        fallback = out_path.with_suffix(".pkl")
        out_df.to_pickle(fallback)
        print(f"  parquet failed ({e}) — wrote pickle: {fallback.name}")
    print(f"DONE {symbol} {tf}: {len(starts)} windows in {elapsed:.0f}s → {out_path.name} ({len(out_df)} rows)")


def main() -> int:
    predictor = load_models()
    for symbol in SYMBOLS:
        for tf in ["1h", "4h"]:
            generate_for(predictor, symbol, tf)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
