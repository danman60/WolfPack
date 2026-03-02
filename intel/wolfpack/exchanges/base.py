"""Abstract exchange adapter — contract for Hyperliquid and dYdX."""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

ExchangeId = Literal["hyperliquid", "dydx"]


class Candle(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class FundingRate(BaseModel):
    symbol: str
    rate: float
    next_funding_time: int


class OrderbookLevel(BaseModel):
    price: float
    size: float


class Orderbook(BaseModel):
    symbol: str
    bids: list[OrderbookLevel]
    asks: list[OrderbookLevel]
    timestamp: int


class MarketInfo(BaseModel):
    symbol: str
    base_asset: str
    last_price: float
    volume_24h: float
    open_interest: float
    funding_rate: float
    max_leverage: int


class ExchangeAdapter(ABC):
    """Unified interface for fetching market data from any supported exchange."""

    @property
    @abstractmethod
    def id(self) -> ExchangeId: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def get_markets(self) -> list[MarketInfo]: ...

    @abstractmethod
    async def get_candles(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> list[Candle]: ...

    @abstractmethod
    async def get_funding_rates(self) -> list[FundingRate]: ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Orderbook: ...
