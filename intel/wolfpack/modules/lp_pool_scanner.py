"""LP Pool Scanner — discovers and ranks Uniswap V3 pools by projected yield."""

import logging
import re
import httpx
from dataclasses import dataclass
from typing import Optional

from wolfpack.config import settings

logger = logging.getLogger(__name__)

GECKO_BASE = "https://api.geckoterminal.com/api/v2"

_CHAIN_GECKO_NETWORK = {
    "arbitrum": "arbitrum",
    "ethereum": "eth",
}
MIN_TVL_USD = 1_000_000        # ignore pools below $1M TVL
MIN_VOLUME_24H = 100_000       # ignore pools below $100K daily volume
MAX_POOLS_TO_TRACK = 10        # top N pools to consider
SCAN_INTERVAL_CYCLES = 6       # scan every 6 cycles (3 hours at 30-min cron)


@dataclass
class PoolCandidate:
    address: str
    name: str                   # "WETH / USDC 0.05%"
    token0_symbol: str
    token1_symbol: str
    fee_tier_pct: float         # 0.05, 0.3, 1.0
    tvl_usd: float
    volume_24h: float
    fee_apr: float              # (volume_24h * fee_pct / tvl) * 365
    volume_trend: str           # "rising", "flat", "falling"
    il_risk: str                # "low", "medium", "high"
    score: float                # composite 0-100


class LPPoolScanner:
    def __init__(self):
        self._last_scan_cycle: int = 0
        self._cycle_count: int = 0
        self._candidates: list[PoolCandidate] = []
        self._pool_history: dict[str, list[float]] = {}  # address -> last N APRs

    def should_scan(self) -> bool:
        """Check if it's time for a new scan."""
        self._cycle_count += 1
        return self._cycle_count - self._last_scan_cycle >= SCAN_INTERVAL_CYCLES

    async def scan(self) -> list[PoolCandidate]:
        """Scan top Uniswap V3 pools and rank by projected yield."""
        self._last_scan_cycle = self._cycle_count

        try:
            # Fetch top pools from GeckoTerminal (sorted by volume desc)
            pools = await self._fetch_top_pools()

            candidates = []
            for pool in pools:
                attrs = pool.get("attributes", {})

                name = attrs.get("name", "")
                tvl = float(attrs.get("reserve_in_usd", 0) or 0)
                vol_data = attrs.get("volume_usd", {})
                vol_24h = float(vol_data.get("h24", 0)) if isinstance(vol_data, dict) else 0

                # Skip low-quality pools
                if tvl < MIN_TVL_USD or vol_24h < MIN_VOLUME_24H:
                    continue

                # Parse fee tier from name (e.g., "WETH / USDC 0.05%")
                fee_pct = self._parse_fee_tier(name)

                # Compute fee APR
                if tvl > 0:
                    daily_fees = vol_24h * (fee_pct / 100)
                    fee_apr = (daily_fees / tvl) * 365 * 100  # as percentage
                else:
                    fee_apr = 0

                # Volume trend (compare h24 vs h6*4)
                vol_6h = float(vol_data.get("h6", 0)) if isinstance(vol_data, dict) else 0
                if vol_6h > 0:
                    projected_24h = vol_6h * 4
                    if vol_24h > projected_24h * 1.1:
                        trend = "rising"
                    elif vol_24h < projected_24h * 0.9:
                        trend = "falling"
                    else:
                        trend = "flat"
                else:
                    trend = "flat"

                # IL risk classification
                il_risk = self._classify_il_risk(name)

                # Composite score
                score = self._compute_score(fee_apr, tvl, trend, il_risk)

                # Extract address from pool id (format: "eth_0xaddress")
                pool_id = pool.get("id", "")
                address = pool_id.split("_")[-1] if "_" in pool_id else pool_id

                # Parse token symbols
                parts = name.split(" / ") if " / " in name else name.split("/")
                t0 = parts[0].strip() if len(parts) >= 1 else "???"
                t1 = parts[1].strip().split()[0] if len(parts) >= 2 else "???"

                candidates.append(PoolCandidate(
                    address=address,
                    name=name,
                    token0_symbol=t0,
                    token1_symbol=t1,
                    fee_tier_pct=fee_pct,
                    tvl_usd=tvl,
                    volume_24h=vol_24h,
                    fee_apr=round(fee_apr, 2),
                    volume_trend=trend,
                    il_risk=il_risk,
                    score=round(score, 1),
                ))

                # Track APR history
                if address not in self._pool_history:
                    self._pool_history[address] = []
                self._pool_history[address].append(fee_apr)
                # Keep last 24 data points (72 hours at 3h intervals)
                if len(self._pool_history[address]) > 24:
                    self._pool_history[address] = self._pool_history[address][-24:]

            # Sort by score descending
            candidates.sort(key=lambda c: c.score, reverse=True)
            self._candidates = candidates[:MAX_POOLS_TO_TRACK]

            logger.info(f"[lp-scanner] Scanned {len(pools)} pools, {len(candidates)} qualified, top {len(self._candidates)} tracked")
            for c in self._candidates[:5]:
                logger.info(f"[lp-scanner]   {c.name} APR={c.fee_apr:.1f}% tvl=${c.tvl_usd:,.0f} score={c.score}")

            return self._candidates

        except Exception as e:
            logger.warning(f"[lp-scanner] Scan failed: {e}")
            return self._candidates  # return cached

    def get_candidates(self) -> list[PoolCandidate]:
        """Get current ranked pool candidates."""
        return self._candidates

    def get_apr_trend(self, address: str) -> str:
        """Check if a pool's APR is trending down."""
        history = self._pool_history.get(address, [])
        if len(history) < 3:
            return "insufficient_data"
        recent = sum(history[-3:]) / 3
        older = sum(history[:-3]) / max(len(history) - 3, 1)
        if older > 0:
            change = (recent - older) / older
            if change < -0.20:
                return "declining"
            elif change > 0.20:
                return "improving"
        return "stable"

    async def _fetch_top_pools(self) -> list:
        """Fetch top Uniswap V3 Ethereum pools from GeckoTerminal."""
        try:
            network = _CHAIN_GECKO_NETWORK.get(settings.lp_chain, "arbitrum")
            url = f"{GECKO_BASE}/networks/{network}/dexes/uniswap_v3/pools"
            params = {"page": 1, "sort": "h24_volume_usd_desc"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params, headers={"Accept": "application/json"})
                if resp.status_code != 200:
                    logger.warning(f"[lp-scanner] GeckoTerminal top pools failed: {resp.status_code}")
                    return []
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.warning(f"[lp-scanner] Fetch error: {e}")
            return []

    def _parse_fee_tier(self, name: str) -> float:
        """Extract fee tier percentage from pool name like 'WETH / USDC 0.05%'."""
        match = re.search(r'(\d+\.?\d*)%', name)
        if match:
            return float(match.group(1))
        return 0.3  # default

    def _classify_il_risk(self, name: str) -> str:
        """Classify IL risk based on token pair."""
        stables = {"USDC", "USDT", "DAI", "FRAX", "LUSD", "TUSD", "BUSD", "GUSD", "USDP"}
        majors = {"WETH", "ETH", "WBTC", "BTC"}

        name_upper = name.upper()
        tokens = [t.strip().split()[0] for t in name_upper.split("/")]

        if all(t in stables for t in tokens):
            return "low"
        if all(t in (stables | majors) for t in tokens):
            return "medium"
        return "high"

    def _compute_score(self, fee_apr: float, tvl: float, trend: str, il_risk: str) -> float:
        """Composite score 0-100."""
        # APR component (0-50): higher APR = better, capped at 100% APR
        apr_score = min(fee_apr / 100 * 50, 50)

        # TVL component (0-20): prefer larger pools (more stable)
        if tvl >= 100_000_000:
            tvl_score = 20
        elif tvl >= 10_000_000:
            tvl_score = 15
        elif tvl >= 1_000_000:
            tvl_score = 10
        else:
            tvl_score = 5

        # Trend component (0-15)
        trend_score = {"rising": 15, "flat": 8, "falling": 0}.get(trend, 5)

        # IL risk component (0-15): lower risk = better
        il_score = {"low": 15, "medium": 10, "high": 3}.get(il_risk, 5)

        return apr_score + tvl_score + trend_score + il_score
