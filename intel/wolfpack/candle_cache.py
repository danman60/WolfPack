"""Candle cache — retrieves candles from DB cache or exchange, fills gaps."""

import logging

from wolfpack.exchanges.base import Candle, ExchangeAdapter
from wolfpack.exchanges.hyperliquid import HyperliquidExchange
from wolfpack.exchanges.dydx import DydxExchange

logger = logging.getLogger(__name__)

EXCHANGE_FACTORIES: dict[str, type[ExchangeAdapter]] = {
    "hyperliquid": HyperliquidExchange,
    "dydx": DydxExchange,
}

INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


async def get_candles(
    exchange: str,
    symbol: str,
    interval: str,
    start_time: int,
    end_time: int,
) -> list[Candle]:
    """Get candles from cache, fill gaps from exchange.

    Args:
        exchange: Exchange ID (hyperliquid, dydx)
        symbol: Asset symbol (BTC, ETH, etc.)
        interval: Candle interval (1h, 4h, 1d, etc.)
        start_time: Start epoch ms
        end_time: End epoch ms

    Returns:
        Sorted list of Candle objects covering [start_time, end_time]
    """
    from wolfpack.db import get_cached_candles, store_candles

    # 1. Load cached candles
    cached = get_cached_candles(exchange, symbol, interval, start_time, end_time)
    cached_ts = {c["timestamp"] for c in cached}

    # 2. Determine expected timestamps
    step = INTERVAL_MS.get(interval, 3_600_000)
    expected_ts = set()
    t = start_time
    while t <= end_time:
        expected_ts.add(t)
        t += step

    missing_ts = expected_ts - cached_ts

    if not missing_ts:
        # All cached — convert to Candle objects
        return _rows_to_candles(cached)

    logger.info(f"Cache miss: {len(missing_ts)} candles to fetch for {symbol}/{interval}")

    # 3. Fetch missing from exchange in batches
    adapter_cls = EXCHANGE_FACTORIES.get(exchange)
    if adapter_cls is None:
        raise ValueError(f"Unknown exchange: {exchange}")

    adapter = adapter_cls()
    fetched: list[Candle] = []

    sorted_missing = sorted(missing_ts)
    batch_size = 1000
    for i in range(0, len(sorted_missing), batch_size):
        batch_start = sorted_missing[i]
        batch_end = sorted_missing[min(i + batch_size - 1, len(sorted_missing) - 1)]
        limit = (batch_end - batch_start) // step + 2  # +2 for boundary safety

        try:
            batch = await adapter.get_candles(symbol, interval, limit=min(limit, 5000))
            # Filter to only candles in our range
            for c in batch:
                if start_time <= c.timestamp <= end_time and c.timestamp in missing_ts:
                    fetched.append(c)
        except Exception as e:
            logger.error(f"Failed to fetch candles batch: {e}")

    # 4. Store newly fetched candles
    if fetched:
        rows = [
            {
                "exchange_id": exchange,
                "symbol": symbol,
                "interval": interval,
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in fetched
        ]
        store_candles(rows)

    # 5. Merge and return
    all_candles = _rows_to_candles(cached) + fetched
    all_candles.sort(key=lambda c: c.timestamp)

    # Deduplicate by timestamp
    seen: set[int] = set()
    deduped: list[Candle] = []
    for c in all_candles:
        if c.timestamp not in seen:
            seen.add(c.timestamp)
            deduped.append(c)

    return deduped


def _rows_to_candles(rows: list[dict]) -> list[Candle]:
    return [
        Candle(
            timestamp=r["timestamp"],
            open=r["open"],
            high=r["high"],
            low=r["low"],
            close=r["close"],
            volume=r["volume"],
        )
        for r in rows
    ]
