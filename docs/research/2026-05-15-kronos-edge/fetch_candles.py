"""
Fetch 90 days of BTC/ETH/LINK 1h + 4h klines from Binance public API.
Saves per-symbol/per-tf CSV to data/.

Schema matches what Kronos expects: timestamps + open/high/low/close/volume/amount.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

OUT_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "LINKUSDT"]
INTERVALS = ["1h", "4h"]
DAYS = 90

# Binance public klines, limit max 1000 per call. For 90d * 24h = 2160 candles, 3 calls per symbol.
BASE = "https://api.binance.com/api/v3/klines"


def fetch_one(symbol: str, interval: str, start_ms: int, end_ms: int) -> list[list]:
    url = f"{BASE}?symbol={symbol}&interval={interval}&startTime={start_ms}&endTime={end_ms}&limit=1000"
    with urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def fetch_paginated(symbol: str, interval: str, days: int) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    interval_ms = {"1h": 3600_000, "4h": 14400_000, "5m": 300_000}[interval]
    all_rows: list[list] = []
    cursor = start_ms
    while cursor < end_ms:
        chunk = fetch_one(symbol, interval, cursor, end_ms)
        if not chunk:
            break
        all_rows.extend(chunk)
        cursor = chunk[-1][0] + interval_ms
        time.sleep(0.1)  # respect rate limit

    rows = []
    for k in all_rows:
        rows.append({
            "timestamps": pd.Timestamp(int(k[0]), unit="ms", tz="UTC"),
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "volume": float(k[5]),
            "amount": float(k[7]),
        })
    return pd.DataFrame(rows)


def main() -> int:
    for symbol in SYMBOLS:
        for interval in INTERVALS:
            out_path = OUT_DIR / f"{symbol}_{interval}_{DAYS}d.csv"
            df = fetch_paginated(symbol, interval, DAYS)
            df.to_csv(out_path, index=False)
            print(f"{symbol:>10s} {interval:>3s}  rows={len(df):>5d}  span={df['timestamps'].iloc[0]} → {df['timestamps'].iloc[-1]}  → {out_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
