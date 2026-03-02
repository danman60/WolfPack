"""Liquidity & Slippage Intel — Orderbook depth analysis and slippage estimation."""

from pydantic import BaseModel

from wolfpack.exchanges.base import Orderbook


class LiquidityOutput(BaseModel):
    bid_depth_usd: float
    ask_depth_usd: float
    spread_bps: float
    imbalance_ratio: float  # >1 = buy pressure, <1 = sell pressure
    estimated_slippage_10k: float  # Estimated slippage for $10k order in bps


class LiquidityIntel:
    """Analyzes orderbook for liquidity health and slippage estimation."""

    def analyze(self, orderbook: Orderbook) -> LiquidityOutput:
        bid_depth = sum(b.price * b.size for b in orderbook.bids)
        ask_depth = sum(a.price * a.size for a in orderbook.asks)

        best_bid = orderbook.bids[0].price if orderbook.bids else 0
        best_ask = orderbook.asks[0].price if orderbook.asks else 0
        mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else 1

        spread_bps = ((best_ask - best_bid) / mid * 10_000) if mid > 0 else 0
        imbalance = bid_depth / ask_depth if ask_depth > 0 else 1

        # Estimate slippage for a $10k market buy
        slippage = self._estimate_slippage(orderbook.asks, 10_000, mid)

        return LiquidityOutput(
            bid_depth_usd=round(bid_depth, 2),
            ask_depth_usd=round(ask_depth, 2),
            spread_bps=round(spread_bps, 2),
            imbalance_ratio=round(imbalance, 3),
            estimated_slippage_10k=round(slippage, 2),
        )

    def _estimate_slippage(self, asks: list, target_usd: float, mid: float) -> float:
        """Walk the ask side to estimate slippage for a given notional."""
        filled = 0.0
        cost = 0.0
        for level in asks:
            available = level.price * level.size
            take = min(available, target_usd - filled)
            cost += take * (level.price / mid - 1) if mid > 0 else 0
            filled += take
            if filled >= target_usd:
                break
        return (cost / target_usd * 10_000) if target_usd > 0 else 0
