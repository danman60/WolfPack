"""Hyperliquid exchange adapter using their REST info API."""

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

BASE_URL = "https://api.hyperliquid.xyz"


class HyperliquidExchange(ExchangeAdapter):
    @property
    def id(self) -> ExchangeId:
        return "hyperliquid"

    @property
    def name(self) -> str:
        return "Hyperliquid"

    async def get_markets(self) -> list[MarketInfo]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/info", json={"type": "meta"}, timeout=10
            )
            data = resp.json()
        return [
            MarketInfo(
                symbol=m["name"],
                base_asset=m["name"],
                last_price=0,
                volume_24h=0,
                open_interest=0,
                funding_rate=float(m.get("funding", 0)),
                max_leverage=int(m.get("maxLeverage", 50)),
            )
            for m in data.get("universe", [])
        ]

    async def get_candles(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> list[Candle]:
        start_time = _now_ms() - limit * _interval_ms(interval)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/info",
                json={
                    "type": "candleSnapshot",
                    "req": {"coin": symbol, "interval": interval, "startTime": start_time},
                },
                timeout=10,
            )
            data = resp.json()
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
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/info", json={"type": "meta"}, timeout=10
            )
            data = resp.json()
        return [
            FundingRate(
                symbol=m["name"],
                rate=float(m.get("funding", 0)),
                next_funding_time=_now_ms() + 3600_000,
            )
            for m in data.get("universe", [])
        ]

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Orderbook:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/info",
                json={"type": "l2Book", "coin": symbol, "nSigFigs": 5},
                timeout=10,
            )
            data = resp.json()
        levels = data.get("levels", [[], []])
        return Orderbook(
            symbol=symbol,
            bids=[
                OrderbookLevel(price=float(l["px"]), size=float(l["sz"]))
                for l in levels[0][:depth]
            ],
            asks=[
                OrderbookLevel(price=float(l["px"]), size=float(l["sz"]))
                for l in levels[1][:depth]
            ],
            timestamp=_now_ms(),
        )


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


def _interval_ms(interval: str) -> int:
    units = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
    return units.get(interval, 3_600_000)
