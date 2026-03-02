"""dYdX v4 exchange adapter using the Indexer REST API."""

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


class DydxExchange(ExchangeAdapter):
    @property
    def id(self) -> ExchangeId:
        return "dydx"

    @property
    def name(self) -> str:
        return "dYdX"

    async def get_markets(self) -> list[MarketInfo]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/perpetualMarkets", timeout=10)
            data = resp.json()
        markets = data.get("markets", {})
        return [
            MarketInfo(
                symbol=str(info.get("ticker", k)),
                base_asset=str(info.get("ticker", k)).replace("-USD", ""),
                last_price=float(info.get("oraclePrice", 0)),
                volume_24h=float(info.get("volume24H", 0)),
                open_interest=float(info.get("openInterest", 0)),
                funding_rate=0,
                max_leverage=20,
            )
            for k, info in markets.items()
        ]

    async def get_candles(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> list[Candle]:
        resolution = INTERVAL_MAP.get(interval, "1HOUR")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/candles/perpetualMarkets/{symbol}",
                params={"resolution": resolution, "limit": limit},
                timeout=10,
            )
            data = resp.json()
        return [
            Candle(
                timestamp=_parse_ts(c.get("startedAt", "")),
                open=float(c["open"]),
                high=float(c["high"]),
                low=float(c["low"]),
                close=float(c["close"]),
                volume=float(c.get("baseTokenVolume", 0)),
            )
            for c in data.get("candles", [])
        ]

    async def get_funding_rates(self) -> list[FundingRate]:
        markets = await self.get_markets()
        rates: list[FundingRate] = []
        async with httpx.AsyncClient() as client:
            for m in markets[:10]:
                try:
                    resp = await client.get(
                        f"{BASE_URL}/historicalFunding/{m.symbol}",
                        params={"limit": 1},
                        timeout=5,
                    )
                    data = resp.json()
                    latest = (data.get("historicalFunding") or [None])[0]
                    rates.append(
                        FundingRate(
                            symbol=m.symbol,
                            rate=float(latest["rate"]) if latest else 0,
                            next_funding_time=_now_ms() + 3_600_000,
                        )
                    )
                except Exception:
                    rates.append(
                        FundingRate(symbol=m.symbol, rate=0, next_funding_time=_now_ms() + 3_600_000)
                    )
        return rates

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Orderbook:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/orderbooks/perpetualMarket/{symbol}", timeout=10
            )
            data = resp.json()
        return Orderbook(
            symbol=symbol,
            bids=[
                OrderbookLevel(price=float(b["price"]), size=float(b["size"]))
                for b in (data.get("bids") or [])[:depth]
            ],
            asks=[
                OrderbookLevel(price=float(a["price"]), size=float(a["size"]))
                for a in (data.get("asks") or [])[:depth]
            ],
            timestamp=_now_ms(),
        )


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


def _parse_ts(iso_str: str) -> int:
    from datetime import datetime, timezone
    try:
        return int(datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return _now_ms()
