"""Momentum Buckets — Discrete price bucketing trend filter.

Inspired by Polymarket bot's noise-reduction technique: instead of comparing
raw prices (noisy), bucket into discrete percentage steps and detect
monotonic movement across buckets. This eliminates tick-level whipsaw
while preserving genuine momentum shifts.

Outputs a MomentumBucketsOutput with trend direction, strength, and
a conviction-weighted momentum score suitable for consumption by LLM agents
and the RegimeMomentumStrategy.
"""

from enum import Enum
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from wolfpack.exchanges.base import Candle


class BucketTrend(str, Enum):
    STRONG_UP = "strong_up"
    UP = "up"
    NEUTRAL = "neutral"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


BUCKET_SIZE = Literal["tight", "normal", "wide"]


class BucketWindow(BaseModel):
    """Analysis of a single lookback window."""
    timeframe: str
    bucket_pct: float = Field(description="Bucket size as % of price")
    trend: BucketTrend
    consecutive_moves: int = Field(description="Consecutive same-direction bucket changes")
    bucket_velocity: float = Field(
        description="Buckets moved per bar (positive=up, negative=down)"
    )
    price_in_bucket_pct: float = Field(
        description="Where price sits within current bucket [0=bottom, 1=top]"
    )


class MomentumBucketsOutput(BaseModel):
    asset: str
    primary_trend: BucketTrend
    momentum_score: float = Field(
        ge=-1.0, le=1.0,
        description="Weighted momentum: -1 strong bearish, +1 strong bullish",
    )
    conviction: float = Field(
        ge=0.0, le=1.0,
        description="How confident we are in the trend signal",
    )
    windows: list[BucketWindow]
    adaptive_bucket_pct: float = Field(
        description="Auto-selected bucket size based on recent volatility",
    )
    regime_hint: str = Field(
        description="Suggested regime overlay: trending, choppy, breakout",
    )


# ---------------------------------------------------------------------------
# Core bucketing logic
# ---------------------------------------------------------------------------

def _auto_bucket_size(closes: np.ndarray, atr_period: int = 14) -> float:
    """Pick bucket size as a percentage of price, scaled to recent volatility.

    Low vol → tighter buckets (0.3%) to catch subtle moves.
    High vol → wider buckets (1.5%) to filter noise.
    """
    if len(closes) < atr_period + 1:
        return 0.005  # default 0.5%

    # Simplified ATR from close-to-close changes
    abs_returns = np.abs(np.diff(closes[-atr_period - 1:])) / closes[-atr_period - 1:-1]
    avg_return = np.mean(abs_returns)

    # Map avg bar return to bucket size:
    # ~0.1% avg return → 0.3% bucket (tight, low vol)
    # ~0.5% avg return → 0.75% bucket (normal)
    # ~1.5%+ avg return → 1.5% bucket (wide, high vol)
    bucket_pct = np.clip(avg_return * 1.5, 0.003, 0.015)
    return float(bucket_pct)


def _bucket_price(price: float, bucket_pct: float) -> float:
    """Round price down to nearest bucket."""
    step = price * bucket_pct
    if step <= 0:
        return price
    return np.floor(price / step) * step


def _analyze_window(
    closes: np.ndarray,
    bucket_pct: float,
    lookback: int,
    tf_label: str,
) -> BucketWindow:
    """Analyze a single lookback window of close prices."""
    window = closes[-lookback:] if len(closes) >= lookback else closes

    if len(window) < 3:
        return BucketWindow(
            timeframe=tf_label,
            bucket_pct=round(bucket_pct * 100, 3),
            trend=BucketTrend.NEUTRAL,
            consecutive_moves=0,
            bucket_velocity=0.0,
            price_in_bucket_pct=0.5,
        )

    # Bucket each close price
    bucketed = np.array([_bucket_price(p, bucket_pct) for p in window])

    # Detect bucket transitions
    transitions = np.diff(bucketed)  # positive = moved up a bucket, negative = down

    # Count consecutive same-direction moves from the end
    consecutive = 0
    if len(transitions) > 0:
        last_sign = np.sign(transitions[-1])
        if last_sign != 0:
            for i in range(len(transitions) - 1, -1, -1):
                if np.sign(transitions[i]) == last_sign:
                    consecutive += 1
                else:
                    break

    # Bucket velocity: net bucket moves per bar over the window
    nonzero_transitions = transitions[transitions != 0]
    if len(nonzero_transitions) > 0:
        # Net direction of bucket moves / total bars
        net_moves = np.sum(np.sign(nonzero_transitions))
        velocity = net_moves / len(transitions)
    else:
        velocity = 0.0

    # Where price sits within its current bucket [0=bottom, 1=top]
    step = window[-1] * bucket_pct
    if step > 0:
        bucket_floor = _bucket_price(window[-1], bucket_pct)
        in_bucket = (window[-1] - bucket_floor) / step
        in_bucket = float(np.clip(in_bucket, 0.0, 1.0))
    else:
        in_bucket = 0.5

    # Classify trend
    if consecutive >= 4 and velocity > 0.3:
        trend = BucketTrend.STRONG_UP
    elif consecutive >= 2 and velocity > 0.1:
        trend = BucketTrend.UP
    elif consecutive >= 4 and velocity < -0.3:
        trend = BucketTrend.STRONG_DOWN
    elif consecutive >= 2 and velocity < -0.1:
        trend = BucketTrend.DOWN
    else:
        trend = BucketTrend.NEUTRAL

    return BucketWindow(
        timeframe=tf_label,
        bucket_pct=round(bucket_pct * 100, 3),
        trend=trend,
        consecutive_moves=consecutive,
        bucket_velocity=round(float(velocity), 4),
        price_in_bucket_pct=round(in_bucket, 4),
    )


# ---------------------------------------------------------------------------
# Multi-window analysis
# ---------------------------------------------------------------------------

# Lookback windows and their weights for the composite score
_WINDOWS = [
    ("5bar", 5, 0.20),    # Very short-term — captures fresh momentum shifts
    ("13bar", 13, 0.35),  # Medium — Fibonacci-ish, good for swing detection
    ("34bar", 34, 0.30),  # Longer swing — confirms vs noise
    ("55bar", 55, 0.15),  # Background trend confirmation
]

_TREND_SCORES = {
    BucketTrend.STRONG_UP: 1.0,
    BucketTrend.UP: 0.5,
    BucketTrend.NEUTRAL: 0.0,
    BucketTrend.DOWN: -0.5,
    BucketTrend.STRONG_DOWN: -1.0,
}


class MomentumBuckets:
    """Discrete price bucketing momentum detector.

    Analyzes multiple lookback windows with auto-adaptive bucket sizing.
    Produces a composite momentum score and regime hint consumed by
    LLM agents and quantitative strategies.
    """

    def __init__(self, bucket_pct_override: float | None = None):
        """
        Args:
            bucket_pct_override: Force a specific bucket size (e.g. 0.005 = 0.5%).
                                 If None, auto-selects based on recent volatility.
        """
        self._bucket_override = bucket_pct_override

    def analyze(
        self,
        candles: list[Candle],
        asset: str = "BTC",
    ) -> MomentumBucketsOutput:
        """Run momentum bucket analysis on candle data.

        Args:
            candles: List of Candle objects (at least 10 needed, 60+ ideal).
            asset: Asset symbol for the output label.

        Returns:
            MomentumBucketsOutput with trend, momentum score, conviction,
            and per-window breakdowns.
        """
        closes = np.array([c.close for c in candles], dtype=np.float64)

        if len(closes) < 5:
            return self._neutral_output(asset, 0.5)

        # Auto-select or use override bucket size
        bucket_pct = self._bucket_override or _auto_bucket_size(closes)

        # Analyze each window
        windows: list[BucketWindow] = []
        for label, lookback, _ in _WINDOWS:
            if len(closes) >= min(lookback, 5):
                w = _analyze_window(closes, bucket_pct, lookback, label)
                windows.append(w)

        if not windows:
            return self._neutral_output(asset, bucket_pct)

        # Composite momentum score: weighted average of window trends
        weighted_score = 0.0
        total_weight = 0.0
        for window, (_, _, weight) in zip(windows, _WINDOWS[: len(windows)]):
            score = _TREND_SCORES[window.trend]
            # Amplify by velocity magnitude (strong moves get more weight)
            amplified = score * (1.0 + min(abs(window.bucket_velocity), 0.5))
            weighted_score += weight * amplified
            total_weight += weight

        if total_weight > 0:
            momentum_score = weighted_score / total_weight
        else:
            momentum_score = 0.0

        momentum_score = float(np.clip(momentum_score, -1.0, 1.0))

        # Conviction: how aligned are the windows?
        trends = [_TREND_SCORES[w.trend] for w in windows]
        if len(trends) > 1:
            signs = [np.sign(t) for t in trends if t != 0]
            if signs and all(s == signs[0] for s in signs):
                # All windows agree on direction
                alignment = 1.0
            elif signs:
                # Partial agreement
                most_common = max(set(signs), key=signs.count)
                alignment = signs.count(most_common) / len(signs)
            else:
                alignment = 0.3  # All neutral
        else:
            alignment = 0.5

        # Factor in consecutive moves from the primary window (13bar)
        primary = windows[1] if len(windows) > 1 else windows[0]
        consecutive_factor = min(primary.consecutive_moves / 5.0, 1.0)

        conviction = float(np.clip(
            0.5 * alignment + 0.3 * consecutive_factor + 0.2 * abs(momentum_score),
            0.0,
            1.0,
        ))

        # Primary trend from the most-weighted window with a clear signal
        primary_trend = BucketTrend.NEUTRAL
        for w in windows:
            if w.trend != BucketTrend.NEUTRAL:
                primary_trend = w.trend
                break

        # Regime hint based on bucket behavior
        regime_hint = self._derive_regime_hint(windows, momentum_score)

        return MomentumBucketsOutput(
            asset=asset,
            primary_trend=primary_trend,
            momentum_score=round(momentum_score, 4),
            conviction=round(conviction, 4),
            windows=windows,
            adaptive_bucket_pct=round(bucket_pct * 100, 3),
            regime_hint=regime_hint,
        )

    def _derive_regime_hint(
        self, windows: list[BucketWindow], momentum_score: float
    ) -> str:
        """Infer regime from bucket patterns."""
        if not windows:
            return "insufficient_data"

        velocities = [abs(w.bucket_velocity) for w in windows]
        avg_velocity = np.mean(velocities)

        # High velocity + strong score = trending
        if avg_velocity > 0.2 and abs(momentum_score) > 0.4:
            return "trending"

        # Low velocity + low score = choppy
        if avg_velocity < 0.1 and abs(momentum_score) < 0.2:
            return "choppy"

        # Short windows strong, long windows flat = potential breakout
        if len(windows) >= 3:
            short_vel = abs(windows[0].bucket_velocity)
            long_vel = abs(windows[-1].bucket_velocity)
            if short_vel > 0.3 and long_vel < 0.1:
                return "breakout"

        return "transitional"

    def _neutral_output(self, asset: str, bucket_pct: float) -> MomentumBucketsOutput:
        return MomentumBucketsOutput(
            asset=asset,
            primary_trend=BucketTrend.NEUTRAL,
            momentum_score=0.0,
            conviction=0.0,
            windows=[],
            adaptive_bucket_pct=round(bucket_pct * 100, 3),
            regime_hint="insufficient_data",
        )
