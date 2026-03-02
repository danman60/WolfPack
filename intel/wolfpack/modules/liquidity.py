"""Liquidity & Slippage Intel — Orderbook depth analysis, slippage estimation, and trade gating."""

from typing import Literal

import numpy as np
from pydantic import BaseModel

from wolfpack.exchanges.base import Orderbook


LiquidityHealth = Literal["healthy", "thin", "dangerous"]


class LiquidityOutput(BaseModel):
    asset: str
    mid_price: float
    spread_bps: float
    depth_bid_usd: float
    depth_ask_usd: float
    estimated_slippage_bps: float
    estimated_impact_bps: float
    liquidity_health: LiquidityHealth
    trade_allowed: bool
    recommended_size_adjustment: float
    reason: str


class LiquidityIntel:
    """Analyzes orderbook for liquidity health, slippage estimation, and trade gating.

    Key computations:
    - Spread in basis points from best bid/ask
    - Depth within 50 bps of mid on each side
    - Slippage via VWAP book-walking for intended order size
    - Impact estimate at 40% of slippage
    - Health classification with hard blocks and size adjustments
    """

    def __init__(self, depth_band_bps: float = 50.0, impact_factor: float = 0.4):
        self.depth_band_bps = depth_band_bps
        self.impact_factor = impact_factor

    def analyze(self, orderbook: Orderbook, order_size_usd: float = 50_000.0) -> LiquidityOutput:
        asset = orderbook.symbol

        # --- Mid price and spread ---
        if not orderbook.bids or not orderbook.asks:
            return self._empty_output(asset, "No bids or asks in orderbook")

        best_bid = orderbook.bids[0].price
        best_ask = orderbook.asks[0].price

        if best_bid <= 0 or best_ask <= 0:
            return self._empty_output(asset, "Invalid bid/ask prices")

        mid_price = (best_bid + best_ask) / 2.0
        spread_bps = (best_ask - best_bid) / mid_price * 10_000

        # --- Depth within band ---
        band_fraction = self.depth_band_bps / 10_000
        bid_floor = mid_price * (1 - band_fraction)
        ask_ceiling = mid_price * (1 + band_fraction)

        depth_bid_usd = sum(
            lvl.price * lvl.size
            for lvl in orderbook.bids
            if lvl.price >= bid_floor
        )
        depth_ask_usd = sum(
            lvl.price * lvl.size
            for lvl in orderbook.asks
            if lvl.price <= ask_ceiling
        )

        # --- Slippage: walk the book for intended size ---
        slippage_bps = self._estimate_slippage(orderbook.asks, order_size_usd, mid_price)

        # --- Impact estimate ---
        impact_bps = slippage_bps * self.impact_factor

        # --- Health classification ---
        min_depth = min(depth_bid_usd, depth_ask_usd)

        if min_depth < 100_000 or spread_bps > 8.0:
            health: LiquidityHealth = "dangerous"
            trade_allowed = False
            size_adj = 0.0
            reason = self._build_reason(health, min_depth, spread_bps, order_size_usd)
        elif min_depth < 500_000 or spread_bps > 3.0:
            health = "thin"
            trade_allowed = True
            # Scale down: ratio of available depth to ideal, capped at 0.5
            size_adj = round(np.clip(min_depth / 500_000, 0.25, 0.75), 2)
            reason = self._build_reason(health, min_depth, spread_bps, order_size_usd)
        else:
            health = "healthy"
            trade_allowed = True
            size_adj = 1.0
            reason = f"Sufficient depth for ${order_size_usd:,.0f} order. Spread normal."

        return LiquidityOutput(
            asset=asset,
            mid_price=round(mid_price, 2),
            spread_bps=round(spread_bps, 2),
            depth_bid_usd=round(depth_bid_usd, 2),
            depth_ask_usd=round(depth_ask_usd, 2),
            estimated_slippage_bps=round(slippage_bps, 2),
            estimated_impact_bps=round(impact_bps, 2),
            liquidity_health=health,
            trade_allowed=trade_allowed,
            recommended_size_adjustment=size_adj,
            reason=reason,
        )

    def _estimate_slippage(self, asks: list, target_usd: float, mid: float) -> float:
        """Walk the ask side to compute VWAP, return slippage vs mid in bps."""
        if not asks or target_usd <= 0 or mid <= 0:
            return 0.0

        filled_usd = 0.0
        filled_qty = 0.0

        for level in asks:
            level_usd = level.price * level.size
            remaining = target_usd - filled_usd

            if remaining <= 0:
                break

            take_usd = min(level_usd, remaining)
            take_qty = take_usd / level.price
            filled_usd += take_usd
            filled_qty += take_qty

        if filled_qty <= 0:
            return 0.0

        vwap = filled_usd / filled_qty
        slippage_bps = (vwap - mid) / mid * 10_000
        return max(slippage_bps, 0.0)

    def _build_reason(
        self, health: LiquidityHealth, min_depth: float, spread_bps: float, order_size: float
    ) -> str:
        parts = []
        if health == "dangerous":
            parts.append("BLOCKED:")
        else:
            parts.append("CAUTION:")

        if min_depth < 100_000:
            parts.append(f"Min depth ${min_depth:,.0f} below $100K floor.")
        elif min_depth < 500_000:
            parts.append(f"Min depth ${min_depth:,.0f} below $500K threshold.")

        if spread_bps > 8.0:
            parts.append(f"Spread {spread_bps:.1f} bps exceeds 8 bps hard limit.")
        elif spread_bps > 3.0:
            parts.append(f"Spread {spread_bps:.1f} bps above 3 bps soft limit.")

        return " ".join(parts)

    def _empty_output(self, asset: str, reason: str) -> LiquidityOutput:
        return LiquidityOutput(
            asset=asset,
            mid_price=0.0,
            spread_bps=0.0,
            depth_bid_usd=0.0,
            depth_ask_usd=0.0,
            estimated_slippage_bps=0.0,
            estimated_impact_bps=0.0,
            liquidity_health="dangerous",
            trade_allowed=False,
            recommended_size_adjustment=0.0,
            reason=reason,
        )
