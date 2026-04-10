"""Structural Levels — Multi-timeframe structural price levels and sweep detection.

Computes prior session levels (day/week/overnight), swing points,
sweep detection, and nearest S/R from candle history.
"""

from datetime import datetime, timezone

import numpy as np
from pydantic import BaseModel

from wolfpack.exchanges.base import Candle


class StructuralLevels(BaseModel):
    # Prior session levels (based on UTC day boundaries)
    prior_day_high: float
    prior_day_low: float
    prior_week_high: float
    prior_week_low: float
    overnight_high: float  # 00:00-08:00 UTC range
    overnight_low: float

    # Swing points (local extremes with N-bar confirmation)
    swing_highs: list[float]  # most recent 5, sorted desc
    swing_lows: list[float]   # most recent 5, sorted asc

    # Sweep detection
    swept_level: float | None = None
    swept_direction: str | None = None  # "above" or "below"
    swept_level_type: str | None = None  # e.g. "prior_day_high", "swing_high"

    # Current price context
    nearest_resistance: float
    nearest_support: float
    distance_to_resistance_pct: float
    distance_to_support_pct: float


# Module-level cache: symbol -> (last_candle_timestamp, StructuralLevels)
_level_cache: dict[str, tuple[int, StructuralLevels]] = {}


class StructuralLevelsModule:
    """Computes and caches multi-timeframe structural price levels."""

    def __init__(self, swing_n: int = 3):
        self.swing_n = swing_n

    def analyze(self, candles_1h: list[Candle], symbol: str) -> StructuralLevels | None:
        if len(candles_1h) < 50:
            return None

        latest_ts = candles_1h[-1].timestamp
        if symbol in _level_cache and _level_cache[symbol][0] == latest_ts:
            return _level_cache[symbol][1]

        result = self._compute(candles_1h)
        if result:
            _level_cache[symbol] = (latest_ts, result)
        return result

    def _compute(self, candles: list[Candle]) -> StructuralLevels | None:
        current_price = candles[-1].close

        # Group candles by UTC date
        by_date: dict[str, list[Candle]] = {}
        for c in candles:
            dt = datetime.fromtimestamp(c.timestamp / 1000 if c.timestamp > 1e12 else c.timestamp, tz=timezone.utc)
            key = dt.strftime("%Y-%m-%d")
            by_date.setdefault(key, []).append(c)

        sorted_dates = sorted(by_date.keys())

        # Prior day H/L
        if len(sorted_dates) >= 2:
            prev_day = by_date[sorted_dates[-2]]
            prior_day_high = max(c.high for c in prev_day)
            prior_day_low = min(c.low for c in prev_day)
        else:
            prior_day_high = current_price
            prior_day_low = current_price

        # Prior week H/L — group by ISO week
        by_week: dict[str, list[Candle]] = {}
        for c in candles:
            dt = datetime.fromtimestamp(c.timestamp / 1000 if c.timestamp > 1e12 else c.timestamp, tz=timezone.utc)
            key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
            by_week.setdefault(key, []).append(c)

        sorted_weeks = sorted(by_week.keys())
        if len(sorted_weeks) >= 2:
            prev_week = by_week[sorted_weeks[-2]]
            prior_week_high = max(c.high for c in prev_week)
            prior_week_low = min(c.low for c in prev_week)
        else:
            prior_week_high = prior_day_high
            prior_week_low = prior_day_low

        # Overnight H/L (00:00-08:00 UTC for current day)
        current_day_key = sorted_dates[-1]
        current_day_candles = by_date[current_day_key]
        overnight = [
            c for c in current_day_candles
            if datetime.fromtimestamp(
                c.timestamp / 1000 if c.timestamp > 1e12 else c.timestamp, tz=timezone.utc
            ).hour < 8
        ]
        if overnight:
            overnight_high = max(c.high for c in overnight)
            overnight_low = min(c.low for c in overnight)
        else:
            overnight_high = current_price
            overnight_low = current_price

        # Swing points from last 100 bars
        lookback = min(100, len(candles))
        recent = candles[-lookback:]
        swing_highs = self._find_swing_highs(recent)
        swing_lows = self._find_swing_lows(recent)

        # All structural levels for sweep detection and S/R
        all_levels: dict[str, float] = {
            "prior_day_high": prior_day_high,
            "prior_day_low": prior_day_low,
            "prior_week_high": prior_week_high,
            "prior_week_low": prior_week_low,
        }
        for i, sh in enumerate(swing_highs):
            all_levels[f"swing_high_{i}"] = sh
        for i, sl in enumerate(swing_lows):
            all_levels[f"swing_low_{i}"] = sl

        # Sweep detection on current candle
        swept_level, swept_direction, swept_level_type = self._detect_sweep(
            candles[-1], all_levels
        )

        # Nearest S/R
        above = [v for v in all_levels.values() if v > current_price]
        below = [v for v in all_levels.values() if v < current_price]

        nearest_resistance = min(above) if above else current_price * 1.01
        nearest_support = max(below) if below else current_price * 0.99

        dist_res = (nearest_resistance - current_price) / current_price * 100
        dist_sup = (current_price - nearest_support) / current_price * 100

        return StructuralLevels(
            prior_day_high=round(prior_day_high, 2),
            prior_day_low=round(prior_day_low, 2),
            prior_week_high=round(prior_week_high, 2),
            prior_week_low=round(prior_week_low, 2),
            overnight_high=round(overnight_high, 2),
            overnight_low=round(overnight_low, 2),
            swing_highs=[round(x, 2) for x in swing_highs[:5]],
            swing_lows=[round(x, 2) for x in swing_lows[:5]],
            swept_level=round(swept_level, 2) if swept_level else None,
            swept_direction=swept_direction,
            swept_level_type=swept_level_type,
            nearest_resistance=round(nearest_resistance, 2),
            nearest_support=round(nearest_support, 2),
            distance_to_resistance_pct=round(dist_res, 4),
            distance_to_support_pct=round(dist_sup, 4),
        )

    def _find_swing_highs(self, candles: list[Candle]) -> list[float]:
        """Find swing highs: candle whose high > N candles on each side."""
        n = self.swing_n
        results: list[float] = []
        for i in range(n, len(candles) - n):
            high = candles[i].high
            is_swing = True
            for j in range(1, n + 1):
                if candles[i - j].high >= high or candles[i + j].high >= high:
                    is_swing = False
                    break
            if is_swing:
                results.append(high)
        # Most recent 5, sorted desc
        return sorted(results[-5:], reverse=True)

    def _find_swing_lows(self, candles: list[Candle]) -> list[float]:
        """Find swing lows: candle whose low < N candles on each side."""
        n = self.swing_n
        results: list[float] = []
        for i in range(n, len(candles) - n):
            low = candles[i].low
            is_swing = True
            for j in range(1, n + 1):
                if candles[i - j].low <= low or candles[i + j].low <= low:
                    is_swing = False
                    break
            if is_swing:
                results.append(low)
        # Most recent 5, sorted asc
        return sorted(results[-5:])

    def _detect_sweep(
        self, candle: Candle, levels: dict[str, float]
    ) -> tuple[float | None, str | None, str | None]:
        """Check if current candle swept a structural level and closed back inside."""
        for name, level in levels.items():
            # Sweep above: wick above level but close below
            if candle.high > level > candle.close and "high" in name:
                return level, "above", name.split("_")[0] + "_" + name.split("_")[1] if "_" in name else name
            # Sweep below: wick below level but close above
            if candle.low < level < candle.close and "low" in name:
                return level, "below", name.split("_")[0] + "_" + name.split("_")[1] if "_" in name else name
        return None, None, None
