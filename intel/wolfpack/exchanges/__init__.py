from wolfpack.exchanges.base import ExchangeAdapter, ExchangeId
from wolfpack.exchanges.hyperliquid import HyperliquidExchange
from wolfpack.exchanges.dydx import DydxExchange
from wolfpack.exchanges.kraken import KrakenExchange


def get_exchange(exchange_id: ExchangeId) -> ExchangeAdapter:
    """Factory to get exchange adapter by ID."""
    adapters: dict[ExchangeId, type[ExchangeAdapter]] = {
        "hyperliquid": HyperliquidExchange,
        "dydx": DydxExchange,
        "kraken": KrakenExchange,
    }
    cls = adapters.get(exchange_id)
    if cls is None:
        raise ValueError(f"Unknown exchange: {exchange_id}")
    return cls()


__all__ = ["ExchangeAdapter", "ExchangeId", "get_exchange", "HyperliquidExchange", "DydxExchange", "KrakenExchange"]
