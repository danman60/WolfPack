"""EMA Crossover Strategy — classic fast/slow EMA crossover, regime-gated.

Goes long on golden crosses (fast > slow) and short on death crosses (fast < slow).
Regime gating (read from macro_regime kwarg):

  TRENDING_UP     → longs only (golden crosses aligned with the trend)
  TRENDING_DOWN   → shorts only (death crosses aligned with the trend)
  RANGING_*       → disabled (too many whipsaw crosses in chop)
  VOLATILE        → disabled
  TRANSITION      → disabled (wait for confirmation)
  None            → both directions (backward compat)

Pure numpy implementation — no external TA libs.
"""

import numpy as np

from wolfpack.exchanges.base import Candle
from wolfpack.strategies.base import Strategy

# Regimes that allow long crosses to fire
_LONG_OK = frozenset({"TRENDING_UP", "TRENDING", None})
# Regimes that allow short crosses to fire
_SHORT_OK = frozenset({"TRENDING_DOWN", "TRENDING", None})
# Regimes that disable this strategy entirely
_DISABLED = frozenset(
    {"RANGING", "RANGING_LOW_VOL", "RANGING_HIGH_VOL", "VOLATILE", "TRANSITION"}
)


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
        macro_regime = params.get("macro_regime")

        # Disabled regimes: chop (too many whipsaws), volatile, transition
        if macro_regime in _DISABLED:
            return None

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
            # Golden cross — only fire if regime allows longs
            if macro_regime not in _LONG_OK:
                return None
            return {
                "symbol": "",
                "direction": "long",
                "conviction": 75 if macro_regime == "TRENDING_UP" else 70,
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": size_pct,
            }
        elif not fast_above_now and fast_above_prev:
            # Death cross — only fire if regime allows shorts
            if macro_regime not in _SHORT_OK:
                return None
            return {
                "symbol": "",
                "direction": "short",
                "conviction": 75 if macro_regime == "TRENDING_DOWN" else 70,
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": size_pct,
            }

        return None  # no signal
