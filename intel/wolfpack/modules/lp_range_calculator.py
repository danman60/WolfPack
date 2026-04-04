"""LP Range Calculator — maps regime + volatility to optimal Uniswap V3 tick ranges."""

import math
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Fee tier → tick spacing
TICK_SPACING = {100: 1, 500: 10, 3000: 60, 10000: 200}

# Regime → range width as % of current price (min, max)
# Interpolated by volatility within the range
REGIME_RANGE_WIDTH = {
    "TRENDING":  (12.0, 20.0),   # wide — stay in range during moves
    "RANGING":   (3.0, 6.0),     # tight — maximize fee concentration
    "VOLATILE":  (25.0, 50.0),   # very wide or don't open
    "unknown":   (8.0, 15.0),    # moderate default
}

# Regime → directional skew factor (applied to ema_trend_score)
REGIME_SKEW = {
    "TRENDING":  0.3,   # skew range in trend direction
    "RANGING":   0.0,   # centered
    "VOLATILE":  0.0,   # centered
    "unknown":   0.0,
}

# Regime → position size as % of equity
REGIME_SIZE_PCT = {
    "TRENDING":  12.0,
    "RANGING":   15.0,   # tighter range = more capital efficient
    "VOLATILE":  5.0,    # minimal exposure
    "unknown":   10.0,
}


@dataclass
class RangeRecommendation:
    tick_lower: int
    tick_upper: int
    width_pct: float          # range width as % of price
    skew: float               # -1 to 1
    size_pct: float           # position size as % of equity
    regime: str               # macro regime that drove this
    confidence: float         # 0-1
    reason: str


class LPRangeCalculator:
    """Compute optimal tick range for LP positions based on regime and volatility."""

    def compute_range(
        self,
        current_tick: int,
        fee_tier: int,
        regime_macro: str,          # "TRENDING", "RANGING", "VOLATILE"
        vol_regime: str,            # "low", "normal", "elevated", "extreme"
        realized_vol_1d: float,     # annualized daily vol %
        ema_trend_score: float = 0, # -1 to 1, for directional skew
        confidence: float = 0.5,
    ) -> RangeRecommendation | None:
        """Compute optimal tick range.

        Returns None if VOLATILE + extreme vol (don't open).
        """
        # Don't open in extreme volatility
        if regime_macro == "VOLATILE" and vol_regime == "extreme":
            return None

        spacing = TICK_SPACING.get(fee_tier, 60)

        # Get base width range for this regime
        width_min, width_max = REGIME_RANGE_WIDTH.get(regime_macro, REGIME_RANGE_WIDTH["unknown"])

        # Interpolate by vol: low vol → narrow end, high vol → wide end
        vol_factor = _vol_interpolation(vol_regime, realized_vol_1d)
        width_pct = width_min + (width_max - width_min) * vol_factor

        # Convert width % to tick offset
        # width_pct% means price can move ±(width_pct/2)% and stay in range
        half_width_pct = width_pct / 2 / 100  # as decimal
        tick_offset = abs(int(math.log(1 + half_width_pct) / math.log(1.0001)))
        tick_offset = max(tick_offset, spacing)  # at least one tick spacing

        # Apply directional skew
        skew_factor = REGIME_SKEW.get(regime_macro, 0)
        skew = skew_factor * ema_trend_score  # -1 to 1 range
        skew_ticks = int(tick_offset * skew)

        center_tick = current_tick + skew_ticks
        tick_lower = _round_tick(center_tick - tick_offset, spacing)
        tick_upper = _round_tick(center_tick + tick_offset, spacing)

        # Ensure current tick is in range
        if tick_lower >= current_tick:
            tick_lower = _round_tick(current_tick - spacing, spacing)
        if tick_upper <= current_tick:
            tick_upper = _round_tick(current_tick + spacing, spacing)

        size_pct = REGIME_SIZE_PCT.get(regime_macro, 10.0)

        return RangeRecommendation(
            tick_lower=tick_lower,
            tick_upper=tick_upper,
            width_pct=round(width_pct, 1),
            skew=round(skew, 3),
            size_pct=size_pct,
            regime=regime_macro,
            confidence=confidence,
            reason=f"{regime_macro} regime, {vol_regime} vol, width={width_pct:.1f}%",
        )

    def should_update_range(
        self, current_lower: int, current_upper: int, recommended: RangeRecommendation, threshold_pct: float = 0.20
    ) -> bool:
        """Only recommend range change if new range differs significantly."""
        current_width = current_upper - current_lower
        new_width = recommended.tick_upper - recommended.tick_lower
        if current_width == 0:
            return True
        width_change = abs(new_width - current_width) / current_width
        return width_change > threshold_pct


def _vol_interpolation(vol_regime: str, realized_vol: float) -> float:
    """Map vol regime to 0-1 interpolation factor."""
    if vol_regime == "low":
        return 0.0
    elif vol_regime == "normal":
        return 0.3
    elif vol_regime == "elevated":
        return 0.7
    elif vol_regime == "extreme":
        return 1.0
    # Fallback: use raw vol
    return min(max(realized_vol / 100, 0), 1.0)


def _round_tick(tick: int, spacing: int) -> int:
    """Round tick to nearest valid tick spacing."""
    return round(tick / spacing) * spacing
