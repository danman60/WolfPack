"""LP Position Monitor — fetches pool state from subgraph and feeds to paper engine."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Out-of-range debounce (same as regime router)
OOR_DEBOUNCE_TICKS = 3


@dataclass
class PoolState:
    """Current state of a Uniswap V3 pool from subgraph."""
    pool_address: str
    current_tick: int
    sqrt_price: str
    liquidity: str
    tvl_usd: float
    volume_usd_24h: float
    token0_symbol: str
    token1_symbol: str
    fee_tier: int
    token0_price_usd: float = 0.0
    token1_price_usd: float = 0.0


class LPPositionMonitor:
    """Monitors LP positions by fetching pool data from the existing subgraph endpoints."""

    def __init__(self):
        self._last_fetch: dict[str, float] = {}  # pool_address -> timestamp

    async def fetch_pool_state(self, pool_address: str) -> Optional[PoolState]:
        """Fetch current pool state from the existing /pools/detail endpoint."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "http://localhost:8000/pools/detail",
                    params={"pool_id": pool_address},
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    logger.warning(f"Pool detail fetch failed: {resp.status_code}")
                    return None

                data = resp.json()
                pool = data.get("pool")
                if not pool:
                    return None

                # Compute 24h volume from poolDayData
                day_data = pool.get("poolDayData", [])
                vol_24h = float(day_data[0].get("volumeUSD", 0)) if day_data else 0

                return PoolState(
                    pool_address=pool["id"],
                    current_tick=int(pool.get("tick", 0)),
                    sqrt_price=pool.get("sqrtPrice", "0"),
                    liquidity=pool.get("liquidity", "0"),
                    tvl_usd=float(pool.get("totalValueLockedUSD", 0)),
                    volume_usd_24h=vol_24h,
                    token0_symbol=pool["token0"]["symbol"],
                    token1_symbol=pool["token1"]["symbol"],
                    fee_tier=int(pool.get("feeTier", 3000)),
                    token0_price_usd=float(pool.get("token0PriceUSD", 0)),
                    token1_price_usd=float(pool.get("token1PriceUSD", 0)),
                )
        except Exception as e:
            logger.warning(f"Failed to fetch pool state for {pool_address}: {e}")
            return None

    def compute_price_ratio(self, sqrt_price_x96: str, token0_decimals: int = 18, token1_decimals: int = 18) -> float:
        """Convert sqrtPriceX96 to token0/token1 price ratio.
        
        sqrtPriceX96 is Q64.96 fixed-point representation of sqrt(price).
        price = (sqrtPrice / 2^96)^2
        Then adjust for token decimals.
        """
        try:
            sqrt_price = int(sqrt_price_x96)
            if sqrt_price <= 0:
                return 0.0
            price = (sqrt_price / (2**96)) ** 2
            # Adjust for decimals: multiply by 10^(decimals0 - decimals1)
            decimal_adjustment = 10 ** (token0_decimals - token1_decimals)
            price *= decimal_adjustment
            return price
        except Exception:
            return 0.0

    def check_alerts(self, positions: list) -> list[dict]:
        """Check for out-of-range and IL alerts. Returns list of alert dicts."""
        alerts = []
        for pos in positions:
            # Out of range alert (debounced)
            if pos.out_of_range_ticks == OOR_DEBOUNCE_TICKS:
                alerts.append({
                    "type": "out_of_range",
                    "position_id": pos.position_id,
                    "pair": f"{pos.token0_symbol}/{pos.token1_symbol}",
                    "current_tick": pos.current_tick,
                    "range": [pos.tick_lower, pos.tick_upper],
                    "message": f"LP OUT OF RANGE: {pos.token0_symbol}/{pos.token1_symbol} — tick {pos.current_tick} outside [{pos.tick_lower}, {pos.tick_upper}]",
                })

            # IL warning at 3%
            if abs(pos.il_pct) >= 3.0:
                alerts.append({
                    "type": "il_warning",
                    "position_id": pos.position_id,
                    "pair": f"{pos.token0_symbol}/{pos.token1_symbol}",
                    "il_pct": pos.il_pct,
                    "message": f"LP IL WARNING: {pos.token0_symbol}/{pos.token1_symbol} — IL at {pos.il_pct:.1f}%",
                })

        return alerts

    def get_pool_states_for_positions(self, engine) -> dict[str, PoolState]:
        """Fetch pool states for all active positions in the engine.
        
        Returns dict mapping pool_address to PoolState.
        """
        pool_addresses = [p.pool_address for p in engine.portfolio.positions if p.status == "active"]
        return {addr: addr for addr in pool_addresses}  # placeholder - async fetch would go here
