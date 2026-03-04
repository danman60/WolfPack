"""Whale Tracker — detect large trades and liquidations from Hyperliquid.

Uses Hyperliquid REST API to fetch recent trades and filter for whale-size activity.
"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"
TIMEOUT = 8.0
WHALE_THRESHOLD_USD = 100_000  # $100K+ = whale trade


class WhaleTrackerOutput(BaseModel):
    whale_buy_volume_usd: float
    whale_sell_volume_usd: float
    net_whale_direction: str  # "bullish" / "bearish" / "neutral"
    whale_trade_count: int
    large_liquidations: list[dict[str, Any]]
    whale_bias_score: float  # -1 to +1


def _neutral_output() -> WhaleTrackerOutput:
    return WhaleTrackerOutput(
        whale_buy_volume_usd=0,
        whale_sell_volume_usd=0,
        net_whale_direction="neutral",
        whale_trade_count=0,
        large_liquidations=[],
        whale_bias_score=0.0,
    )


class WhaleTracker:
    """Tracks whale activity on Hyperliquid via recent trades."""

    async def analyze(self, symbol: str = "BTC") -> WhaleTrackerOutput:
        try:
            trades = await self._fetch_recent_trades(symbol)
        except Exception as e:
            logger.warning(f"[whale] Failed to fetch trades for {symbol}: {e}")
            return _neutral_output()

        if not trades:
            return _neutral_output()

        whale_buys = 0.0
        whale_sells = 0.0
        whale_count = 0

        for t in trades:
            try:
                px = float(t.get("px", 0))
                sz = float(t.get("sz", 0))
                notional = px * sz
                side = t.get("side", "").upper()

                if notional >= WHALE_THRESHOLD_USD:
                    whale_count += 1
                    if side == "B" or side == "BUY":
                        whale_buys += notional
                    else:
                        whale_sells += notional
            except (ValueError, TypeError):
                continue

        total = whale_buys + whale_sells
        if total > 0:
            bias = (whale_buys - whale_sells) / total  # -1 to +1
        else:
            bias = 0.0

        if bias > 0.2:
            direction = "bullish"
        elif bias < -0.2:
            direction = "bearish"
        else:
            direction = "neutral"

        return WhaleTrackerOutput(
            whale_buy_volume_usd=round(whale_buys, 2),
            whale_sell_volume_usd=round(whale_sells, 2),
            net_whale_direction=direction,
            whale_trade_count=whale_count,
            large_liquidations=[],  # Liquidation feed requires WebSocket — skip for now
            whale_bias_score=round(bias, 3),
        )

    async def _fetch_recent_trades(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch recent trades for a symbol from Hyperliquid."""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                HYPERLIQUID_URL,
                json={"type": "recentTrades", "coin": symbol},
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
