"""Mean Reversion Strategy -- fade moves from the mean, regime-adaptive.

Enters when price deviates N ATR units from SMA, targets a return to the mean.
The entry threshold and tuning auto-switch based on macro_regime:

  - RANGING  : threshold 1.5 ATR, tight stops, responsive SMA — range fades
  - TRENDING : threshold 3.0 ATR, wider stops — only fade extreme extensions
  - VOLATILE : disabled (return None)
  - None     : backward-compat TRENDING defaults

Regime gating is still in the router (RANGING list), but the router tells the
strategy *which* regime it's running in so parameters auto-adapt.

Pure numpy implementation.
"""

from datetime import datetime, timezone

import numpy as np

from wolfpack.exchanges.base import Candle
from wolfpack.price_utils import round_price
from wolfpack.strategies.base import Strategy


class MeanReversionStrategy(Strategy):
    name = "mean_reversion"
    description = "Fade extreme deviations from SMA mean, target return to mean"
    parameters = {
        "mean_period": {
            "type": "int",
            "default": 20,
            "min": 10,
            "max": 50,
            "desc": "SMA period for the mean",
        },
        "threshold_atr_mult": {
            "type": "float",
            "default": 3.0,
            "min": 1.0,
            "max": 4.0,
            "desc": "Entry when price is N ATR units from mean",
        },
        "stop_atr_mult": {
            "type": "float",
            "default": 1.0,
            "min": 0.5,
            "max": 3.0,
            "desc": "Stop loss distance in ATR units",
        },
        "size_pct": {
            "type": "float",
            "default": 12.0,
            "min": 1.0,
            "max": 25.0,
            "desc": "Position size as % of equity",
        },
    }

    # Regime-adaptive parameter presets — each tunes threshold / stops / SMA / sizing
    # for the specific sub-regime the router is emitting. The router uses
    # sub-regimes (RANGING_LOW_VOL, RANGING_HIGH_VOL, TRENDING_UP/DOWN) so we
    # key by those. Legacy family names (RANGING, TRENDING) fall through to
    # sensible defaults for back-compat with tests and pinned calls.
    REGIME_PRESETS = {
        # Empirical tuning: live probe across 7 symbols on 2026-04-13
        # showed max |distance| = 0.99 ATR in the current flat-chop regime.
        # 0.75 fires on normal micro-oscillations; 0.4 stop keeps risk small
        # to match the tight band. 5% size × high frequency = low-vol scalp
        # posture. The intent: be profitable even when nothing is extended.
        "RANGING_LOW_VOL": {
            "mean_period": 10,
            "threshold_atr_mult": 0.75,
            "stop_atr_mult": 0.4,
            "size_pct": 5.0,
        },
        "RANGING_HIGH_VOL": {
            # Validator feedback (2026-04-13): HIGH_VOL classifications have
            # been scoring low because realized excursion rarely exceeds 1 ATR.
            # Tightened to 1.0 ATR / 0.5 stop so we still fire when the
            # detector is noisy. Size slightly larger than LOW_VOL.
            "mean_period": 15,
            "threshold_atr_mult": 1.0,
            "stop_atr_mult": 0.5,
            "size_pct": 7.0,
        },
        "RANGING": {  # back-compat family-level default
            "mean_period": 15,
            "threshold_atr_mult": 1.5,
            "stop_atr_mult": 0.7,
            "size_pct": 8.0,
        },
        "TRENDING_UP": {
            "mean_period": 20,
            "threshold_atr_mult": 3.0,
            "stop_atr_mult": 1.0,
            "size_pct": 12.0,
        },
        "TRENDING_DOWN": {
            "mean_period": 20,
            "threshold_atr_mult": 3.0,
            "stop_atr_mult": 1.0,
            "size_pct": 12.0,
        },
        "TRENDING": {  # back-compat
            "mean_period": 20,
            "threshold_atr_mult": 3.0,
            "stop_atr_mult": 1.0,
            "size_pct": 12.0,
        },
    }

    @property
    def warmup_bars(self) -> int:
        return 30

    @classmethod
    def _preset_for(cls, regime: str | None) -> dict:
        """Return parameter preset for the given specific regime or family.

        None / unknown falls back to TRENDING defaults (back-compat).
        VOLATILE / TRANSITION return an empty dict — caller should early-return None.
        """
        if regime in ("VOLATILE", "TRANSITION"):
            return {}
        return cls.REGIME_PRESETS.get(regime or "TRENDING", cls.REGIME_PRESETS["TRENDING"])

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        macro_regime = params.get("macro_regime")

        # VOLATILE / TRANSITION: mean-reversion is dangerous mid-shift
        if macro_regime in ("VOLATILE", "TRANSITION"):
            return None

        preset = self._preset_for(macro_regime)
        mean_period = params.get("mean_period", preset.get("mean_period", 20))
        threshold_atr_mult = params.get(
            "threshold_atr_mult", preset.get("threshold_atr_mult", 3.0)
        )
        stop_atr_mult = params.get("stop_atr_mult", preset.get("stop_atr_mult", 1.0))
        size_pct = params.get("size_pct", preset.get("size_pct", 12.0))

        needed = max(mean_period, 15) + 1  # 14 for ATR + 1
        if current_idx < needed:
            return None

        start = max(0, current_idx - needed - 10)
        window = candles[start : current_idx + 1]
        if len(window) < needed:
            return None

        closes = np.array([c.close for c in window], dtype=np.float64)
        current_close = closes[-1]

        # SMA as the mean
        mean = np.mean(closes[-mean_period:])

        # ATR(14) for distance measurement
        atr = self._compute_atr(window, 14)
        if atr <= 0:
            return None

        distance = (current_close - mean) / atr

        # Liquidity sweep filter: check sweeps against structural levels
        # (prior day/week H/L, swing points) for higher-conviction entries,
        # falling back to local highs/lows.
        sweep_lookback = 5
        recent = window[-sweep_lookback:]
        highs = np.array([c.high for c in window[-mean_period:]], dtype=np.float64)
        lows = np.array([c.low for c in window[-mean_period:]], dtype=np.float64)
        local_high = np.max(highs[:-sweep_lookback]) if len(highs) > sweep_lookback else np.max(highs)
        local_low = np.min(lows[:-sweep_lookback]) if len(lows) > sweep_lookback else np.min(lows)

        # Compute structural levels from candle history for enhanced sweep detection
        struct_levels = self._compute_structural_levels(candles, current_idx)

        # Displacement: body % of total range on the entry candle.
        # Exhaustion candle (small body, big wicks closing toward mean) = higher conviction.
        # Strong push candle (big body away from mean) = move may not be done.
        entry_candle = window[-1]
        displacement = _compute_displacement(entry_candle)
        # Which direction is the body closing relative to the mean?
        closing_toward_mean_long = entry_candle.close > entry_candle.open  # green candle when below mean
        closing_toward_mean_short = entry_candle.close < entry_candle.open  # red candle when above mean

        # Long: price far below mean + recent wick below local low (sweep)
        if distance < -threshold_atr_mult:
            swept_local = any(c.low < local_low and c.close > local_low for c in recent)
            swept_structural = self._check_structural_sweep_below(recent, struct_levels)
            if swept_structural:
                conviction = 75  # structural level sweep = +20 bonus
            elif swept_local:
                conviction = 70  # local sweep = +15 bonus
            else:
                conviction = 55
            # Displacement adjustment
            if displacement < 0.40 and closing_toward_mean_long:
                conviction += 10  # exhaustion wick closing back up = reversal likely
            elif displacement > 0.70 and not closing_toward_mean_long:
                conviction -= 15  # strong red body pushing lower = move not done
            return {
                "symbol": "",
                "direction": "long",
                "conviction": min(conviction, 90),
                "entry_price": current_close,
                "stop_loss": round_price(current_close - atr * stop_atr_mult),
                "take_profit": round_price(mean),
                "size_pct": size_pct,
            }

        # Short: price far above mean + recent wick above local high (sweep)
        if distance > threshold_atr_mult:
            swept_local = any(c.high > local_high and c.close < local_high for c in recent)
            swept_structural = self._check_structural_sweep_above(recent, struct_levels)
            if swept_structural:
                conviction = 75  # structural level sweep = +20 bonus
            elif swept_local:
                conviction = 70  # local sweep = +15 bonus
            else:
                conviction = 55
            # Displacement adjustment
            if displacement < 0.40 and closing_toward_mean_short:
                conviction += 10  # exhaustion wick closing back down = reversal likely
            elif displacement > 0.70 and not closing_toward_mean_short:
                conviction -= 15  # strong green body pushing higher = move not done
            return {
                "symbol": "",
                "direction": "short",
                "conviction": min(conviction, 90),
                "entry_price": current_close,
                "stop_loss": round_price(current_close + atr * stop_atr_mult),
                "take_profit": round_price(mean),
                "size_pct": size_pct,
            }

        return None

    def _compute_structural_levels(
        self, candles: list[Candle], current_idx: int
    ) -> dict[str, list[float]]:
        """Compute simplified structural levels from candle history.

        Returns dict with 'highs' and 'lows' lists of structural price levels
        (prior day H/L, prior week H/L, swing points).
        """
        end = current_idx + 1
        lookback = min(200, end)
        window = candles[end - lookback : end]

        if len(window) < 30:
            return {"highs": [], "lows": []}

        struct_highs: list[float] = []
        struct_lows: list[float] = []

        # Group by UTC date for prior day H/L
        by_date: dict[str, list[Candle]] = {}
        for c in window:
            ts = c.timestamp / 1000 if c.timestamp > 1e12 else c.timestamp
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            key = dt.strftime("%Y-%m-%d")
            by_date.setdefault(key, []).append(c)

        sorted_dates = sorted(by_date.keys())
        if len(sorted_dates) >= 2:
            prev_day = by_date[sorted_dates[-2]]
            struct_highs.append(max(c.high for c in prev_day))
            struct_lows.append(min(c.low for c in prev_day))

        # Group by ISO week for prior week H/L
        by_week: dict[str, list[Candle]] = {}
        for c in window:
            ts = c.timestamp / 1000 if c.timestamp > 1e12 else c.timestamp
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
            by_week.setdefault(key, []).append(c)

        sorted_weeks = sorted(by_week.keys())
        if len(sorted_weeks) >= 2:
            prev_week = by_week[sorted_weeks[-2]]
            struct_highs.append(max(c.high for c in prev_week))
            struct_lows.append(min(c.low for c in prev_week))

        # Swing points (3-bar confirmation) from last 100 bars
        swing_lookback = min(100, len(window))
        recent = window[-swing_lookback:]
        n = 3
        for i in range(n, len(recent) - n):
            high = recent[i].high
            if all(recent[i - j].high < high and recent[i + j].high < high for j in range(1, n + 1)):
                struct_highs.append(high)
            low = recent[i].low
            if all(recent[i - j].low > low and recent[i + j].low > low for j in range(1, n + 1)):
                struct_lows.append(low)

        return {"highs": struct_highs, "lows": struct_lows}

    @staticmethod
    def _check_structural_sweep_below(
        recent: list[Candle], struct_levels: dict[str, list[float]]
    ) -> bool:
        """Check if any recent candle swept below a structural low and closed back above."""
        for level in struct_levels.get("lows", []):
            if any(c.low < level and c.close > level for c in recent):
                return True
        return False

    @staticmethod
    def _check_structural_sweep_above(
        recent: list[Candle], struct_levels: dict[str, list[float]]
    ) -> bool:
        """Check if any recent candle swept above a structural high and closed back below."""
        for level in struct_levels.get("highs", []):
            if any(c.high > level and c.close < level for c in recent):
                return True
        return False

    @staticmethod
    def _compute_atr(candles: list[Candle], period: int = 14) -> float:
        """Compute Average True Range over the last `period` candles."""
        if len(candles) < period + 1:
            return 0.0

        true_ranges: list[float] = []
        for i in range(len(candles) - period, len(candles)):
            c = candles[i]
            prev_close = candles[i - 1].close
            tr = max(
                c.high - c.low,
                abs(c.high - prev_close),
                abs(c.low - prev_close),
            )
            true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0


def _compute_displacement(candle) -> float:
    """Body percentage of total candle range (0.0 = doji, 1.0 = marubozu).

    Measures directional commitment: high displacement = strong move,
    low displacement = rejection/exhaustion (big wicks, small body).
    """
    total_range = candle.high - candle.low
    if total_range <= 0:
        return 0.0
    body = abs(candle.close - candle.open)
    return body / total_range
