"""Hyperliquid exchange adapter using their REST info API."""

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

BASE_URL = "https://api.hyperliquid.xyz"

# Simple TTL cache
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTLS = {
    "meta": 300,
    "metaAndAssetCtxs": 60,
    "candles": 10,
    "l2Book": 2,
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


class HyperliquidExchange(ExchangeAdapter):
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10)
        return self._client

    async def _post(self, payload: dict) -> dict | list:
        client = await self._get_client()
        resp = await client.post(f"{BASE_URL}/info", json=payload)
        resp.raise_for_status()
        return resp.json()

    @property
    def id(self) -> ExchangeId:
        return "hyperliquid"

    @property
    def name(self) -> str:
        return "Hyperliquid"

    async def get_meta_and_contexts(self) -> tuple[list[dict], list[dict]]:
        """Fetch metaAndAssetCtxs — market metadata + live context (funding, OI, mark price)."""
        cache_key = "metaAndAssetCtxs"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore

        data = await self._post({"type": "metaAndAssetCtxs"})
        meta = data[0] if isinstance(data, list) and len(data) > 0 else {}
        contexts = data[1] if isinstance(data, list) and len(data) > 1 else []
        universe = meta.get("universe", [])
        result = (universe, contexts)
        _cache_set(cache_key, result)
        return result

    async def get_markets(self) -> list[MarketInfo]:
        universe, contexts = await self.get_meta_and_contexts()
        markets = []
        for i, m in enumerate(universe):
            ctx = contexts[i] if i < len(contexts) else {}
            markets.append(
                MarketInfo(
                    symbol=m["name"],
                    base_asset=m["name"],
                    last_price=float(ctx.get("markPx", 0)),
                    volume_24h=float(ctx.get("dayNtlVlm", 0)),
                    open_interest=float(ctx.get("openInterest", 0)),
                    funding_rate=float(ctx.get("funding", 0)),
                    max_leverage=int(m.get("maxLeverage", 50)),
                )
            )
        return markets

    async def get_candles(
        self, symbol: str, interval: str = "1h", limit: int = 100, start_time: int | None = None
    ) -> list[Candle]:
        if start_time is None:
            start_time = _now_ms() - limit * _interval_ms(interval)
        data = await self._post({
            "type": "candleSnapshot",
            "req": {"coin": symbol, "interval": interval, "startTime": start_time},
        })
        return [
            Candle(
                timestamp=int(c["t"]),
                open=float(c["o"]),
                high=float(c["h"]),
                low=float(c["l"]),
                close=float(c["c"]),
                volume=float(c["v"]),
            )
            for c in (data if isinstance(data, list) else [])
        ]

    async def get_funding_rates(self) -> list[FundingRate]:
        universe, contexts = await self.get_meta_and_contexts()
        rates = []
        for i, m in enumerate(universe):
            ctx = contexts[i] if i < len(contexts) else {}
            rates.append(
                FundingRate(
                    symbol=m["name"],
                    rate=float(ctx.get("funding", 0)),
                    next_funding_time=_now_ms() + 3600_000,
                )
            )
        return rates

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Orderbook:
        data = await self._post({"type": "l2Book", "coin": symbol, "nSigFigs": 5})
        levels = data.get("levels", [[], []]) if isinstance(data, dict) else [[], []]
        return Orderbook(
            symbol=symbol,
            bids=[
                OrderbookLevel(price=float(lv["px"]), size=float(lv["sz"]))
                for lv in levels[0][:depth]
            ],
            asks=[
                OrderbookLevel(price=float(lv["px"]), size=float(lv["sz"]))
                for lv in levels[1][:depth]
            ],
            timestamp=_now_ms(),
        )

    async def get_user_state(self, wallet: str) -> dict:
        """Fetch clearinghouse state for a wallet (positions, margin, account value)."""
        data = await self._post({"type": "clearinghouseState", "user": wallet})
        return data if isinstance(data, dict) else {}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _interval_ms(interval: str) -> int:
    units = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
        "1d": 86_400_000,
    }
    return units.get(interval, 3_600_000)
