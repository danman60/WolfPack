"""Mean Reversion Strategy -- fade extreme moves from the mean.

Enters when price deviates beyond N ATR units from SMA, targets a return to the mean.
Regime gating is handled by the router, NOT inside this strategy (keeps it backtest-friendly).
Pure numpy implementation.
"""

import numpy as np

from wolfpack.exchanges.base import Candle
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

    @property
    def warmup_bars(self) -> int:
        return 30

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        mean_period = params.get("mean_period", 20)
        threshold_atr_mult = params.get("threshold_atr_mult", 3.0)
        stop_atr_mult = params.get("stop_atr_mult", 1.0)
        size_pct = params.get("size_pct", 12.0)

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

        # Liquidity sweep filter: only enter if a recent candle wicked beyond
        # the local high/low then reversed (stop hunt / exhaustion pattern).
        # Conservative: check last 5 candles for a sweep wick.
        sweep_lookback = 5
        recent = window[-sweep_lookback:]
        highs = np.array([c.high for c in window[-mean_period:]], dtype=np.float64)
        lows = np.array([c.low for c in window[-mean_period:]], dtype=np.float64)
        local_high = np.max(highs[:-sweep_lookback]) if len(highs) > sweep_lookback else np.max(highs)
        local_low = np.min(lows[:-sweep_lookback]) if len(lows) > sweep_lookback else np.min(lows)

        # Long: price far below mean + recent wick below local low (sweep)
        if distance < -threshold_atr_mult:
            swept_low = any(c.low < local_low and c.close > local_low for c in recent)
            conviction = 70 if swept_low else 55
            return {
                "symbol": "",
                "direction": "long",
                "conviction": conviction,
                "entry_price": current_close,
                "stop_loss": round(current_close - atr * stop_atr_mult, 2),
                "take_profit": round(mean, 2),
                "size_pct": size_pct,
            }

        # Short: price far above mean + recent wick above local high (sweep)
        if distance > threshold_atr_mult:
            swept_high = any(c.high > local_high and c.close < local_high for c in recent)
            conviction = 70 if swept_high else 55
            return {
                "symbol": "",
                "direction": "short",
                "conviction": conviction,
                "entry_price": current_close,
                "stop_loss": round(current_close + atr * stop_atr_mult, 2),
                "take_profit": round(mean, 2),
                "size_pct": size_pct,
            }

        return None

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
