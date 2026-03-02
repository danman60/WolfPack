"""Regime Detection — Classifies market into trending, mean-reverting, volatile, or quiet."""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class Regime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    MEAN_REVERTING = "mean_reverting"
    VOLATILE = "volatile"
    QUIET = "quiet"


class RegimeOutput(BaseModel):
    regime: Regime
    confidence: float
    volatility_percentile: float
    trend_strength: float
    adx: float | None = None


class RegimeDetector:
    """
    Detects the current market regime using:
    - ADX for trend strength
    - ATR percentile for volatility regime
    - Hurst exponent approximation for mean-reversion detection
    """

    def __init__(self, lookback: int = 50):
        self.lookback = lookback

    def detect(self, closes: list[float], highs: list[float], lows: list[float]) -> RegimeOutput:
        if len(closes) < self.lookback:
            return RegimeOutput(
                regime=Regime.QUIET, confidence=0, volatility_percentile=0, trend_strength=0
            )

        recent = closes[-self.lookback:]

        # ATR-based volatility
        atr = self._atr(highs[-self.lookback:], lows[-self.lookback:], closes[-self.lookback:])
        avg_price = sum(recent) / len(recent)
        vol_pct = (atr / avg_price * 100) if avg_price > 0 else 0

        # Trend via linear regression slope
        slope = self._slope(recent)
        trend_strength = abs(slope) / (avg_price / len(recent)) if avg_price > 0 else 0

        # Classify
        if vol_pct > 3.0:
            regime = Regime.VOLATILE
        elif trend_strength > 0.5:
            regime = Regime.TRENDING_UP if slope > 0 else Regime.TRENDING_DOWN
        elif vol_pct < 1.0:
            regime = Regime.QUIET
        else:
            regime = Regime.MEAN_REVERTING

        return RegimeOutput(
            regime=regime,
            confidence=min(trend_strength, 1.0),
            volatility_percentile=min(vol_pct / 5.0, 1.0),
            trend_strength=min(trend_strength, 1.0),
        )

    def _atr(self, highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
        if len(highs) < period + 1:
            return 0
        trs = []
        for i in range(-period, 0):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        return sum(trs) / len(trs) if trs else 0

    def _slope(self, values: list[float]) -> float:
        n = len(values)
        if n < 2:
            return 0
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den != 0 else 0
