"""Turtle/Donchian Breakout Strategy -- classic channel breakout with SMA trend filter.

Goes long on 20-period highest-high breakout above SMA(55), short on lowest-low
breakout below SMA(55). Uses ATR-based stops and structural exits (opposite channel break).
Pure numpy implementation.
"""

import numpy as np

from wolfpack.exchanges.base import Candle
from wolfpack.strategies.base import Strategy


class TurtleDonchianStrategy(Strategy):
    name = "turtle_donchian"
    description = "Donchian channel breakout with SMA(55) trend filter and ATR stops"
    parameters = {
        "breakout_period": {
            "type": "int",
            "default": 20,
            "min": 10,
            "max": 30,
            "desc": "Period for highest-high / lowest-low channel",
        },
        "atr_period": {
            "type": "int",
            "default": 20,
            "min": 10,
            "max": 30,
            "desc": "ATR period for stop distance",
        },
        "atr_stop_mult": {
            "type": "float",
            "default": 2.0,
            "min": 1.0,
            "max": 4.0,
            "desc": "ATR multiplier for stop loss",
        },
        "sma_trend_period": {
            "type": "int",
            "default": 55,
            "min": 20,
            "max": 300,
            "desc": "SMA period for trend filter",
        },
        "size_pct": {
            "type": "float",
            "default": 15.0,
            "min": 1.0,
            "max": 25.0,
            "desc": "Position size as % of equity",
        },
    }

    @property
    def warmup_bars(self) -> int:
        return 56  # needs SMA(55)

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        breakout_period = params.get("breakout_period", 20)
        atr_period = params.get("atr_period", 20)
        atr_stop_mult = params.get("atr_stop_mult", 2.0)
        sma_trend_period = params.get("sma_trend_period", 200)
        size_pct = params.get("size_pct", 15.0)

        needed = sma_trend_period + 1
        if current_idx < needed:
            return None

        start = max(0, current_idx - needed - 10)
        window = candles[start : current_idx + 1]
        if len(window) < needed:
            return None

        closes = np.array([c.close for c in window], dtype=np.float64)
        highs = np.array([c.high for c in window], dtype=np.float64)
        lows = np.array([c.low for c in window], dtype=np.float64)

        current_close = closes[-1]

        # SMA trend filter
        sma = np.mean(closes[-sma_trend_period:])

        # Donchian channel: highest high / lowest low of previous breakout_period bars
        # (excluding current bar to detect breakout)
        channel_highs = highs[-(breakout_period + 1) : -1]
        channel_lows = lows[-(breakout_period + 1) : -1]
        highest_high = np.max(channel_highs)
        lowest_low = np.min(channel_lows)

        # ATR calculation
        atr = self._compute_atr(window, atr_period)
        if atr <= 0:
            return None

        # Structural exit: check if existing position should close
        # Long closes when close < lowest low; short closes when close > highest high
        if current_close < lowest_low and current_close < sma:
            return {
                "symbol": "",
                "direction": "close",
                "conviction": 65,
                "entry_price": current_close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": size_pct,
            }
        if current_close > highest_high and current_close > sma:
            # Could be either a close-short or an entry-long -- check for breakout
            pass

        # Long breakout: close > previous highest high AND above SMA
        if current_close > highest_high and current_close > sma:
            stop_loss = round(current_close - atr * atr_stop_mult, 2)
            return {
                "symbol": "",
                "direction": "long",
                "conviction": 65,
                "entry_price": current_close,
                "stop_loss": stop_loss,
                "take_profit": None,  # structural exit, no fixed TP
                "size_pct": size_pct,
            }

        # Short breakout: close < previous lowest low AND below SMA
        if current_close < lowest_low and current_close < sma:
            stop_loss = round(current_close + atr * atr_stop_mult, 2)
            return {
                "symbol": "",
                "direction": "short",
                "conviction": 65,
                "entry_price": current_close,
                "stop_loss": stop_loss,
                "take_profit": None,
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
