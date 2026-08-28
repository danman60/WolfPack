"""Fetch DOGE/USDT 90d 1h to match existing BTC/ETH/LINK data."""
from __future__ import annotations
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(exist_ok=True)

def fetch(symbol, interval, days):
    interval_ms = {"1h": 3600_000}[interval]
    end = datetime.now(timezone.utc)
    start_ms = int((end - timedelta(days=days)).timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    all_rows = []
    cursor = start_ms
    while cursor < end_ms:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&startTime={cursor}&endTime={end_ms}&limit=1000"
        chunk = json.loads(urlopen(url, timeout=20).read())
        if not chunk:
            break
        all_rows.extend(chunk)
        cursor = chunk[-1][0] + interval_ms
        if len(chunk) < 1000:
            break
        time.sleep(0.1)
    rows = [{
        "timestamps": pd.Timestamp(int(k[0]), unit="ms", tz="UTC"),
        "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
        "close": float(k[4]), "volume": float(k[5]), "amount": float(k[7])
    } for k in all_rows]
    df = pd.DataFrame(rows)
    out = OUT / f"{symbol}_{interval}_{days}d.csv"
    df.to_csv(out, index=False)
    print(f"{symbol} {interval}: rows={len(df)} span={df['timestamps'].iloc[0]} → {df['timestamps'].iloc[-1]}")

if __name__ == "__main__":
    fetch("DOGEUSDT", "1h", 90)
