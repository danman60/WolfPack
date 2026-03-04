"""Pool Screening — scores Uniswap V3 pools for LP opportunity quality.

Ported from PoolParty's poolScreening.ts scoring algorithm.
Scores pools 0-100 based on volume/TVL ratio, momentum, fee tier,
impermanent loss risk, and pool age.
"""

import math
from dataclasses import dataclass, field


@dataclass
class PoolScreeningInput:
    """Input data for scoring a single pool."""

    pool_id: str
    token0_symbol: str
    token1_symbol: str
    fee_tier: int  # 100, 500, 3000, 10000
    tvl_usd: float
    volume_usd_24h: float
    volume_trend: str = "flat"  # "rising" | "flat" | "falling"
    pool_age_days: int | None = None


@dataclass
class PoolScreeningResult:
    """Scored result for a pool."""

    pool_id: str
    pair: str
    score: int  # 0-100
    recommendation: str  # "Enter" | "Consider" | "Caution" | "Avoid"
    breakdown: dict = field(default_factory=dict)


def _score_volume_to_tvl(volume_24h: float, tvl: float) -> int:
    """Score volume/TVL ratio on a 0-10 scale."""
    if tvl <= 0 or volume_24h <= 0:
        return 0
    ratio = volume_24h / tvl
    if ratio > 1.0:
        return 10
    if ratio > 0.5:
        return 9
    if ratio > 0.3:
        return 7
    if ratio > 0.15:
        return 5
    if ratio > 0.05:
        return 3
    return 1


def _momentum_bonus(trend: str) -> int:
    """Momentum score: +10 rising, 0 flat, -10 falling."""
    if trend == "rising":
        return 10
    if trend == "falling":
        return -10
    return 0


def _fee_tier_bonus(fee_tier: int) -> int:
    """Fee tier compatibility bonus."""
    if fee_tier == 10000:
        return 5
    if fee_tier == 3000:
        return 2
    if fee_tier == 500:
        return 1
    return 0


def _il_penalty() -> int:
    """Impermanent loss penalty at 10% price move.

    For standard xy=k pools, IL at 10% move is ~0.057 (5.7%).
    This is in the -15 penalty bracket (>= 0.05).
    """
    r = 1.1  # 10% price move
    il = 2 * math.sqrt(r) / (1 + r) - 1
    il_abs = abs(il)
    if il_abs >= 0.10:
        return -30
    if il_abs >= 0.05:
        return -15
    if il_abs >= 0.02:
        return -5
    return 0


def _pool_age_bonus(age_days: int | None) -> int:
    """Age bonus for established pools."""
    if age_days is None:
        return 0
    if age_days > 180:
        return 5
    if age_days > 90:
        return 3
    if age_days > 30:
        return 1
    return 0


def screen_pool(pool: PoolScreeningInput) -> PoolScreeningResult:
    """Score a single pool. Returns 0-100 score with recommendation."""
    pair = f"{pool.token0_symbol}/{pool.token1_symbol}"

    vtv_score = _score_volume_to_tvl(pool.volume_usd_24h, pool.tvl_usd)
    vtv_points = vtv_score * 8  # 0-80

    momentum = _momentum_bonus(pool.volume_trend)
    fee_bonus = _fee_tier_bonus(pool.fee_tier)
    il_pen = _il_penalty()
    age_bonus = _pool_age_bonus(pool.pool_age_days)

    raw_score = vtv_points + momentum + fee_bonus + il_pen + age_bonus
    score = max(0, min(100, raw_score))

    if score >= 85:
        rec = "Enter"
    elif score >= 70:
        rec = "Consider"
    elif score >= 55:
        rec = "Caution"
    else:
        rec = "Avoid"

    return PoolScreeningResult(
        pool_id=pool.pool_id,
        pair=pair,
        score=score,
        recommendation=rec,
        breakdown={
            "volume_tvl_points": vtv_points,
            "volume_tvl_ratio": round(pool.volume_usd_24h / pool.tvl_usd, 4) if pool.tvl_usd > 0 else 0,
            "momentum_points": momentum,
            "fee_tier_bonus": fee_bonus,
            "il_penalty": il_pen,
            "age_bonus": age_bonus,
        },
    )
