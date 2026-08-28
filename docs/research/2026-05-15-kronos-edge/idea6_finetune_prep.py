"""
Idea #6 — Fine-tune preparation: fetch extended history + build train/val pickle.

90 days × 3 symbols isn't enough training data to fine-tune a 25M-param model without
catastrophic overfit. Pull max-history 1h candles from Binance (typically since 2017-2020
for these pairs) and split chronologically into train/val. Evaluation is reserved for
the recent 90-day window in `data/` that we already fetched.

Output:
  finetune/train_data.pkl    dict{symbol: pd.DataFrame[open,high,low,close,vol,amt]} indexed by datetime
  finetune/val_data.pkl      same shape, later date range
  finetune/eval_data.pkl     last 90 days (held out from training; for offline eval)
"""
from __future__ import annotations

import json
import pickle
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

HERE = Path(__file__).resolve().parent
FT_DIR = HERE / "finetune"
FT_DIR.mkdir(exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
INTERVAL = "1h"
INTERVAL_MS = 3600_000

# Train/val/eval split (chronological)
EVAL_DAYS = 90       # most-recent 90d reserved for evaluation (matches our predictions/ set)
VAL_DAYS = 180       # 6 months of val just before eval
# Train = everything before val window


def fetch_chunk(symbol: str, start_ms: int, end_ms: int) -> list[list]:
    url = (f"https://api.binance.com/api/v3/klines"
           f"?symbol={symbol}&interval={INTERVAL}&startTime={start_ms}&endTime={end_ms}&limit=1000")
    with urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def fetch_all_history(symbol: str) -> pd.DataFrame:
    # Binance returns at most 1000 per call. Walk from 2017-01-01 to now.
    start = int(datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    all_rows = []
    cursor = start
    while cursor < end:
        chunk = fetch_chunk(symbol, cursor, end)
        if not chunk:
            cursor += INTERVAL_MS * 1000
            continue
        all_rows.extend(chunk)
        cursor = chunk[-1][0] + INTERVAL_MS
        if len(chunk) < 1000:
            break
        time.sleep(0.08)

    rows = []
    for k in all_rows:
        rows.append({
            "datetime": pd.Timestamp(int(k[0]), unit="ms", tz="UTC").tz_convert(None),
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "vol":    float(k[5]),
            "amt":    float(k[7]),
        })
    df = pd.DataFrame(rows).drop_duplicates(subset=["datetime"]).sort_values("datetime").set_index("datetime")
    return df


def main() -> int:
    end = datetime.now(timezone.utc).replace(tzinfo=None)
    eval_start = end - timedelta(days=EVAL_DAYS)
    val_start = eval_start - timedelta(days=VAL_DAYS)

    train_data: dict[str, pd.DataFrame] = {}
    val_data: dict[str, pd.DataFrame] = {}
    eval_data: dict[str, pd.DataFrame] = {}

    for symbol in SYMBOLS:
        print(f"Fetching {symbol} full 1h history ...")
        df = fetch_all_history(symbol)
        print(f"  {symbol}: rows={len(df)}  span={df.index.min()} → {df.index.max()}")
        train_data[symbol] = df[df.index < val_start]
        val_data[symbol] = df[(df.index >= val_start) & (df.index < eval_start)]
        eval_data[symbol] = df[df.index >= eval_start]
        print(f"    train={len(train_data[symbol])}  val={len(val_data[symbol])}  eval={len(eval_data[symbol])}")

    with open(FT_DIR / "train_data.pkl", "wb") as f:
        pickle.dump(train_data, f)
    with open(FT_DIR / "val_data.pkl", "wb") as f:
        pickle.dump(val_data, f)
    with open(FT_DIR / "eval_data.pkl", "wb") as f:
        pickle.dump(eval_data, f)
    print(f"\nWrote train/val/eval pickles to {FT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
