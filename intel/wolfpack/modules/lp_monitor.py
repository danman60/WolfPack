"""LP Position Monitor — fetches pool state from RPC + GeckoTerminal."""

import logging
import math
import httpx
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

RPC_URL = "https://ethereum-rpc.publicnode.com"
GECKO_BASE = "https://api.geckoterminal.com/api/v2"

OOR_DEBOUNCE_TICKS = 3


@dataclass
class PoolState:
    """Current state of a Uniswap V3 pool from RPC + GeckoTerminal."""
    pool_address: str
    current_tick: int
    sqrt_price_x96: int
    liquidity: int
    tvl_usd: float
    volume_usd_24h: float
    token0_symbol: str
    token1_symbol: str
    fee_tier: int
    token0_price_usd: float = 0.0
    token1_price_usd: float = 0.0

    @property
    def sqrt_price(self) -> str:
        """Backward-compat: old code references state.sqrt_price as string."""
        return str(self.sqrt_price_x96)


class LPPositionMonitor:
    """Monitors LP positions via direct RPC + GeckoTerminal (no subgraph)."""

    def __init__(self):
        self._pool_metadata: dict[str, dict] = {}  # cache token symbols, fee tier per pool

    async def fetch_pool_states(self, pool_addresses: list[str]) -> dict[str, PoolState]:
        """Fetch state for multiple pools. Returns {address: PoolState}."""
        if not pool_addresses:
            return {}

        results = {}

        # 1. Batch RPC for on-chain state (tick, sqrtPrice, liquidity)
        rpc_data = await self._batch_rpc(pool_addresses)

        # 2. GeckoTerminal for market data (TVL, volume, prices, metadata)
        gecko_data = await self._fetch_gecko(pool_addresses)

        # 3. Merge
        for addr in pool_addresses:
            rpc = rpc_data.get(addr, {})
            gecko = gecko_data.get(addr.lower(), {})

            if not rpc.get("tick") and not gecko:
                logger.warning(f"No data for pool {addr[:10]}...")
                continue

            # Get metadata (token symbols, fee tier) from gecko or cache
            attrs = gecko.get("attributes", {})

            token0_sym = self._pool_metadata.get(addr, {}).get("token0", "???")
            token1_sym = self._pool_metadata.get(addr, {}).get("token1", "???")
            fee_tier = self._pool_metadata.get(addr, {}).get("fee_tier", 3000)

            if attrs.get("name"):
                # Parse "WETH / USDC 0.05%" format
                name = attrs["name"]
                parts = name.split(" / ")
                if len(parts) >= 2:
                    token0_sym = parts[0].strip()
                    # token1 may have fee info: "USDC 0.05%"
                    t1_parts = parts[1].strip().split()
                    token1_sym = t1_parts[0]
                    if len(t1_parts) > 1:
                        try:
                            fee_pct = float(t1_parts[0].rstrip('%')) if '%' in t1_parts[-1] else float(t1_parts[-1].rstrip('%'))
                            fee_tier = int(fee_pct * 10000)
                        except Exception:
                            pass

                self._pool_metadata[addr] = {"token0": token0_sym, "token1": token1_sym, "fee_tier": fee_tier}

            volume_data = attrs.get("volume_usd", {})
            vol_24h = float(volume_data.get("h24", 0)) if isinstance(volume_data, dict) else 0

            results[addr] = PoolState(
                pool_address=addr,
                current_tick=rpc.get("tick", 0),
                sqrt_price_x96=rpc.get("sqrt_price_x96", 0),
                liquidity=rpc.get("liquidity", 0),
                tvl_usd=float(attrs.get("reserve_in_usd", 0) or 0),
                volume_usd_24h=vol_24h,
                token0_symbol=token0_sym,
                token1_symbol=token1_sym,
                fee_tier=fee_tier,
                token0_price_usd=float(attrs.get("base_token_price_usd", 0) or 0),
                token1_price_usd=float(attrs.get("quote_token_price_usd", 0) or 0),
            )

        return results

    # Keep the old single-pool method for backward compatibility
    async def fetch_pool_state(self, pool_address: str) -> Optional[PoolState]:
        """Fetch current pool state (single pool)."""
        states = await self.fetch_pool_states([pool_address])
        return states.get(pool_address)

    async def _batch_rpc(self, pool_addresses: list[str]) -> dict:
        """Batch JSON-RPC calls for slot0() and liquidity() on all pools."""
        calls = []
        for i, addr in enumerate(pool_addresses):
            # slot0() = 0x3850c7bd
            calls.append({
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": addr, "data": "0x3850c7bd"}, "latest"],
                "id": i * 2,
            })
            # liquidity() = 0x1a686502
            calls.append({
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": addr, "data": "0x1a686502"}, "latest"],
                "id": i * 2 + 1,
            })

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(RPC_URL, json=calls)
                if resp.status_code != 200:
                    logger.warning(f"RPC batch failed: {resp.status_code}")
                    return {}

                results_raw = resp.json()
                results_by_id = {r["id"]: r.get("result", "0x") for r in results_raw}

                parsed = {}
                for i, addr in enumerate(pool_addresses):
                    slot0_hex = results_by_id.get(i * 2, "0x")
                    liq_hex = results_by_id.get(i * 2 + 1, "0x")

                    try:
                        # slot0 returns: sqrtPriceX96 (uint160), tick (int24), ...
                        # sqrtPriceX96 is first 32 bytes, tick is next 32 bytes
                        if slot0_hex and len(slot0_hex) >= 130:  # 0x + 64 + 64
                            sqrt_price = int(slot0_hex[2:66], 16)
                            tick_raw = int(slot0_hex[66:130], 16)
                            # tick is int24, handle sign
                            if tick_raw >= 2**255:
                                tick_raw -= 2**256
                            tick = tick_raw
                        else:
                            sqrt_price = 0
                            tick = 0

                        liquidity = int(liq_hex, 16) if liq_hex and liq_hex != "0x" else 0

                        parsed[addr] = {
                            "sqrt_price_x96": sqrt_price,
                            "tick": tick,
                            "liquidity": liquidity,
                        }
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse RPC for {addr[:10]}: {e}")

                return parsed
        except Exception as e:
            logger.warning(f"RPC batch error: {e}")
            return {}

    async def _fetch_gecko(self, pool_addresses: list[str]) -> dict:
        """Fetch market data from GeckoTerminal multi-pool endpoint."""
        try:
            addrs = ",".join(pool_addresses)
            url = f"{GECKO_BASE}/networks/eth/pools/multi/{addrs}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                if resp.status_code != 200:
                    logger.warning(f"GeckoTerminal failed: {resp.status_code}")
                    return {}

                data = resp.json()
                pools = data.get("data", [])

                # Index by pool address (lowercased from the id field)
                result = {}
                for pool in pools:
                    # id format: "eth_0xaddress"
                    pool_id = pool.get("id", "")
                    addr = pool_id.split("_")[-1].lower() if "_" in pool_id else pool_id.lower()
                    result[addr] = pool

                return result
        except Exception as e:
            logger.warning(f"GeckoTerminal error: {e}")
            return {}

    def compute_price_ratio(self, sqrt_price_x96, token0_decimals: int = 18, token1_decimals: int = 6) -> float:
        """Convert sqrtPriceX96 to token0/token1 price ratio.

        Accepts int or str for backward compatibility.
        """
        try:
            val = int(sqrt_price_x96)
            if val <= 0:
                return 0.0
            price = (val / (2**96)) ** 2
            price *= 10 ** (token0_decimals - token1_decimals)
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
