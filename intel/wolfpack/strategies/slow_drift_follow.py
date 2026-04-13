"""Slow Drift Follow -- catches slow directional drift in RANGING regimes.

Built 2026-04-13 as part of the regime-edge exploration phase. Hypothesis:
the regime detector labels slow grind-up/down as RANGING_LOW_VOL because
ATR is low, but the tape is actually drifting with a persistent slope.
Mean-reversion strategies lose here (nothing reverts) while trend-followers
gated to TRENDING never fire. This probe fills that gap.

Signal logic:
  - Slope: compare close N bars ago vs current close
  - Entry trigger: price has pulled back toward the 20 SMA
  - Direction: LONG on up-slope pullback, SHORT on down-slope pullback
  - Stop: 1 ATR beyond the 20 SMA (away from entry)
  - Target: 2x risk distance

Regime gating: RANGING_LOW_VOL / RANGING_HIGH_VOL only. In TRENDING regimes,
ema_crossover and turtle_donchian already cover the trend-follow role.

This is a probe strategy (4% size) — it has no historical validation yet.
PerformanceTracker grades it over ~30 trades and scales accordingly.
"""

import numpy as np

from wolfpack.exchanges.base import Candle
from wolfpack.price_utils import round_price
from wolfpack.strategies.base import Strategy

_RANGING_REGIMES = frozenset({"RANGING", "RANGING_LOW_VOL", "RANGING_HIGH_VOL"})


class SlowDriftFollowStrategy(Strategy):
    name = "slow_drift_follow"
    description = "Trend-follow slow drift in RANGING regimes via pullback entries"
    parameters = {
        "slope_lookback": {
            "type": "int", "default": 6, "min": 3, "max": 20,
            "desc": "Bars back to measure slope",
        },
        "sma_period": {
            "type": "int", "default": 20, "min": 10, "max": 50,
            "desc": "SMA period for pullback target",
        },
        "min_slope_pct": {
            "type": "float", "default": 0.3, "min": 0.1, "max": 2.0,
            "desc": "Minimum % move over lookback to qualify as drift",
        },
        "pullback_atr": {
            "type": "float", "default": 0.5, "min": 0.1, "max": 1.5,
            "desc": "Max ATR distance from SMA to trigger entry",
        },
        "stop_atr": {
            "type": "float", "default": 1.0, "min": 0.5, "max": 2.5,
            "desc": "Stop distance in ATR from SMA",
        },
        "size_pct": {
            "type": "float", "default": 4.0, "min": 1.0, "max": 15.0,
            "desc": "Position size as % of equity (probe size)",
        },
    }

    @property
    def warmup_bars(self) -> int:
        return 22

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        macro_regime = params.get("macro_regime")
        if macro_regime is not None and macro_regime not in _RANGING_REGIMES:
            return None

        slope_lookback = int(params.get("slope_lookback", 6))
        sma_period = int(params.get("sma_period", 20))
        min_slope_pct = float(params.get("min_slope_pct", 0.3))
        pullback_atr_mult = float(params.get("pullback_atr", 0.5))
        stop_atr_mult = float(params.get("stop_atr", 1.0))
        size_pct = float(params.get("size_pct", 4.0))

        needed = max(sma_period, slope_lookback) + 2
        if current_idx < needed:
            return None

        window = candles[: current_idx + 1]
        if len(window) < needed:
            return None

        closes = np.array([c.close for c in window], dtype=np.float64)
        current_close = float(closes[-1])

        prior_close = float(closes[-slope_lookback - 1])
        if prior_close <= 0:
            return None
        slope_pct = ((current_close - prior_close) / prior_close) * 100

        sma = float(np.mean(closes[-sma_period:]))

        atr = self._compute_atr(window, 14)
        if atr <= 0:
            return None

        distance_atr = abs(current_close - sma) / atr
        if distance_atr > pullback_atr_mult:
            return None

        last = window[-1]

        if slope_pct > min_slope_pct:
            if last.close <= last.open:
                return None
            stop = round_price(sma - atr * stop_atr_mult)
            risk = current_close - stop
            if risk <= 0:
                return None
            target = round_price(current_close + risk * 2.0)
            return {
                "symbol": "",
                "direction": "long",
                "conviction": 65,
                "entry_price": current_close,
                "stop_loss": stop,
                "take_profit": target,
                "size_pct": size_pct,
            }

        if slope_pct < -min_slope_pct:
            if last.close >= last.open:
                return None
            stop = round_price(sma + atr * stop_atr_mult)
            risk = stop - current_close
            if risk <= 0:
                return None
            target = round_price(current_close - risk * 2.0)
            return {
                "symbol": "",
                "direction": "short",
                "conviction": 65,
                "entry_price": current_close,
                "stop_loss": stop,
                "take_profit": target,
                "size_pct": size_pct,
            }

        return None

    @staticmethod
    def _compute_atr(candles: list[Candle], period: int = 14) -> float:
        if len(candles) < period + 1:
            return 0.0
        trs: list[float] = []
        for i in range(len(candles) - period, len(candles)):
            c = candles[i]
            prev_close = candles[i - 1].close
            tr = max(
                c.high - c.low,
                abs(c.high - prev_close),
                abs(c.low - prev_close),
            )
            trs.append(tr)
        return sum(trs) / len(trs) if trs else 0.0
