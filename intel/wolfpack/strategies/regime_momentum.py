"""Regime Momentum Strategy — trades in direction of detected regime.

Uses the existing RegimeDetector module directly. Goes long in trending_up,
short in trending_down, closes in choppy/panic/low_vol_grind.
"""

from wolfpack.exchanges.base import Candle
from wolfpack.modules.regime import Regime, RegimeDetector
from wolfpack.strategies.base import Strategy


class RegimeMomentumStrategy(Strategy):
    name = "regime_momentum"
    description = "Trades in the direction of the detected market regime using EMA/ADX/ATR signals"
    parameters = {
        "confidence_threshold": {
            "type": "float",
            "default": 0.4,
            "min": 0.1,
            "max": 0.9,
            "desc": "Minimum regime confidence to enter a trade",
        },
        "size_pct": {
            "type": "float",
            "default": 15.0,
            "min": 1.0,
            "max": 25.0,
            "desc": "Position size as % of equity",
        },
    }

    def __init__(self):
        self._detector = RegimeDetector(lookback=60)

    @property
    def warmup_bars(self) -> int:
        return 61

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        confidence_threshold = params.get("confidence_threshold", 0.4)
        size_pct = params.get("size_pct", 15.0)

        window = candles[max(0, current_idx - 120) : current_idx + 1]
        if len(window) < 61:
            return None

        signal = self._detector.detect(window, asset=candles[current_idx].close.__class__.__name__)
        candle = candles[current_idx]

        if signal.regime == Regime.TRENDING_UP and signal.confidence >= confidence_threshold:
            return {
                "symbol": "",  # filled by engine
                "direction": "long",
                "conviction": int(signal.confidence * 100),
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": size_pct * signal.risk_scalar,
            }
        elif signal.regime == Regime.TRENDING_DOWN and signal.confidence >= confidence_threshold:
            return {
                "symbol": "",
                "direction": "short",
                "conviction": int(signal.confidence * 100),
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": size_pct * signal.risk_scalar,
            }
        else:
            # Non-trending regime — signal to close if position open
            return {
                "symbol": "",
                "direction": "close",
                "conviction": int(signal.confidence * 100),
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": 0,
            }
