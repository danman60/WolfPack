"""dYdX v4 exchange adapter using the Indexer REST API."""

import asyncio
import logging
import time

import httpx

from wolfpack.exchanges.base import (
    ExchangeAdapter,
    ExchangeId,
    Candle,
    FundingRate,
    MarketInfo,
    Orderbook,
    OrderbookLevel,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://indexer.dydx.trade/v4"

INTERVAL_MAP = {
    "1m": "1MIN",
    "5m": "5MINS",
    "15m": "15MINS",
    "30m": "30MINS",
    "1h": "1HOUR",
    "4h": "4HOURS",
    "1d": "1DAY",
}

# Simple TTL cache (matches hyperliquid.py pattern)
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTLS = {
    "markets": 300,
    "candles": 10,
    "funding": 60,
    "orderbook": 2,
}


def _cache_get(key: str) -> object | None:
    if key in _cache:
        ts, data = _cache[key]
        ttl = _CACHE_TTLS.get(key.split(":")[0], 60)
        if time.time() - ts < ttl:
            return data
    return None


def _cache_set(key: str, data: object) -> None:
    _cache[key] = (time.time(), data)


class DydxExchange(ExchangeAdapter):
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10)
        return self._client

    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        client = await self._get_client()
        resp = await client.get(f"{BASE_URL}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    @property
    def id(self) -> ExchangeId:
        return "dydx"

    @property
    def name(self) -> str:
        return "dYdX"

    async def get_markets(self) -> list[MarketInfo]:
        cache_key = "markets"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore

        data = await self._get("/perpetualMarkets")
        markets_raw = data.get("markets", {}) if isinstance(data, dict) else {}
        result = [
            MarketInfo(
                symbol=str(info.get("ticker", k)),
                base_asset=str(info.get("ticker", k)).replace("-USD", ""),
                last_price=float(info.get("oraclePrice", 0)),
                volume_24h=float(info.get("volume24H", 0)),
                open_interest=float(info.get("openInterest", 0)),
                funding_rate=0,
                max_leverage=20,
            )
            for k, info in markets_raw.items()
        ]
        _cache_set(cache_key, result)
        return result

    async def get_candles(
        self, symbol: str, interval: str = "1h", limit: int = 100, start_time: int | None = None
    ) -> list[Candle]:
        cache_key = f"candles:{symbol}:{interval}:{limit}:{start_time}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore

        resolution = INTERVAL_MAP.get(interval, "1HOUR")
        params: dict[str, str | int] = {"resolution": resolution, "limit": limit}
        if start_time is not None:
            from datetime import datetime, timezone
            params["fromISO"] = datetime.fromtimestamp(start_time / 1000, tz=timezone.utc).isoformat()
        data = await self._get(
            f"/candles/perpetualMarkets/{symbol}",
            params=params,
        )
        result = [
            Candle(
                timestamp=_parse_ts(c.get("startedAt", "")),
                open=float(c["open"]),
                high=float(c["high"]),
                low=float(c["low"]),
                close=float(c["close"]),
                volume=float(c.get("baseTokenVolume", 0)),
            )
            for c in (data.get("candles", []) if isinstance(data, dict) else [])
        ]
        _cache_set(cache_key, result)
        return result

    async def get_funding_rates(self) -> list[FundingRate]:
        cache_key = "funding"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore

        markets = await self.get_markets()
        client = await self._get_client()

        # Fetch funding rates concurrently instead of sequentially
        async def _fetch_one(symbol: str) -> FundingRate:
            try:
                resp = await client.get(
                    f"{BASE_URL}/historicalFunding/{symbol}",
                    params={"limit": 1},
                    timeout=5,
                )
                data = resp.json()
                latest = (data.get("historicalFunding") or [None])[0]
                return FundingRate(
                    symbol=symbol,
                    rate=float(latest["rate"]) if latest else 0,
                    next_funding_time=_now_ms() + 3_600_000,
                )
            except Exception:
                return FundingRate(
                    symbol=symbol, rate=0, next_funding_time=_now_ms() + 3_600_000
                )

        tasks = [_fetch_one(m.symbol) for m in markets[:10]]
        result = await asyncio.gather(*tasks)
        rates = list(result)
        _cache_set(cache_key, rates)
        return rates

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Orderbook:
        cache_key = f"orderbook:{symbol}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore

        data = await self._get(f"/orderbooks/perpetualMarket/{symbol}")
        result = Orderbook(
            symbol=symbol,
            bids=[
                OrderbookLevel(price=float(b["price"]), size=float(b["size"]))
                for b in (data.get("bids") or [] if isinstance(data, dict) else [])[:depth]
            ],
            asks=[
                OrderbookLevel(price=float(a["price"]), size=float(a["size"]))
                for a in (data.get("asks") or [] if isinstance(data, dict) else [])[:depth]
            ],
            timestamp=_now_ms(),
        )
        _cache_set(cache_key, result)
        return result

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _parse_ts(iso_str: str) -> int:
    from datetime import datetime, timezone
    try:
        return int(datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return _now_ms()
