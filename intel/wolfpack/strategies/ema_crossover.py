"""EMA Crossover Strategy — classic fast/slow EMA crossover.

Goes long when fast EMA crosses above slow EMA, short when below.
Pure numpy implementation — no external TA libs.
"""

import numpy as np

from wolfpack.exchanges.base import Candle
from wolfpack.strategies.base import Strategy


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average."""
    alpha = 2.0 / (period + 1)
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


class EMACrossoverStrategy(Strategy):
    name = "ema_crossover"
    description = "Trades EMA crossovers — long when fast > slow, short when fast < slow"
    parameters = {
        "fast_period": {
            "type": "int",
            "default": 20,
            "min": 5,
            "max": 50,
            "desc": "Fast EMA period",
        },
        "slow_period": {
            "type": "int",
            "default": 50,
            "min": 20,
            "max": 200,
            "desc": "Slow EMA period",
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
        return 51  # enough for default slow_period=50

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        fast_period = params.get("fast_period", 20)
        slow_period = params.get("slow_period", 50)
        size_pct = params.get("size_pct", 15.0)

        needed = slow_period + 1
        start = max(0, current_idx - needed - 10)  # small extra buffer
        window = candles[start : current_idx + 1]

        if len(window) < needed:
            return None

        closes = np.array([c.close for c in window], dtype=np.float64)
        ema_fast = _ema(closes, fast_period)
        ema_slow = _ema(closes, slow_period)

        # Current and previous crossover state
        fast_above_now = ema_fast[-1] > ema_slow[-1]
        fast_above_prev = ema_fast[-2] > ema_slow[-2]

        candle = candles[current_idx]

        if fast_above_now and not fast_above_prev:
            # Golden cross — go long
            return {
                "symbol": "",
                "direction": "long",
                "conviction": 70,
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": size_pct,
            }
        elif not fast_above_now and fast_above_prev:
            # Death cross — go short
            return {
                "symbol": "",
                "direction": "short",
                "conviction": 70,
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": size_pct,
            }

        return None  # no signal
