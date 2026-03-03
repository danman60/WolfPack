"""Volatility Breakout Strategy — trades regime transitions.

Uses the existing VolatilitySignal module. Enters when vol regime transitions
from low/normal to elevated/extreme (breakout), exits when vol subsides.
"""

from wolfpack.exchanges.base import Candle
from wolfpack.modules.volatility import VolatilitySignal
from wolfpack.strategies.base import Strategy


class VolBreakoutStrategy(Strategy):
    name = "vol_breakout"
    description = "Trades volatility regime transitions — enters on breakout, exits when vol subsides"
    parameters = {
        "target_vol_pct": {
            "type": "float",
            "default": 30.0,
            "min": 10.0,
            "max": 60.0,
            "desc": "Target annualized volatility for position sizing",
        },
        "breakout_zscore": {
            "type": "float",
            "default": 1.5,
            "min": 0.5,
            "max": 3.0,
            "desc": "Vol z-score threshold for breakout entry",
        },
        "size_pct": {
            "type": "float",
            "default": 12.0,
            "min": 1.0,
            "max": 25.0,
            "desc": "Position size as % of equity",
        },
    }

    def __init__(self):
        self._prev_regime: str | None = None

    @property
    def warmup_bars(self) -> int:
        return 200  # need decent history for vol calculations

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        target_vol = params.get("target_vol_pct", 30.0)
        breakout_zscore = params.get("breakout_zscore", 1.5)
        size_pct = params.get("size_pct", 12.0)

        window = candles[max(0, current_idx - 750) : current_idx + 1]
        if len(window) < 50:
            return None

        closes = [c.close for c in window]
        candle = candles[current_idx]

        analyzer = VolatilitySignal(target_vol_pct=target_vol)
        result = analyzer.analyze(asset="", closes=closes)

        current_regime = result.vol_regime
        prev_regime = self._prev_regime
        self._prev_regime = current_regime

        if prev_regime is None:
            return None

        # Determine price direction from recent momentum (20-bar return)
        if len(closes) >= 20:
            momentum = (closes[-1] - closes[-20]) / closes[-20]
        else:
            momentum = 0.0

        # Breakout: transition from low/normal to elevated/extreme with high z-score
        low_regimes = ("low", "normal")
        high_regimes = ("elevated", "extreme")

        if (
            prev_regime in low_regimes
            and current_regime in high_regimes
            and result.vol_zscore >= breakout_zscore
        ):
            direction = "long" if momentum > 0 else "short"
            scaled_size = size_pct * result.combined_exposure_multiplier
            return {
                "symbol": "",
                "direction": direction,
                "conviction": min(int(abs(result.vol_zscore) * 30), 100),
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": max(scaled_size, 1.0),
            }

        # Exit: transition from elevated/extreme back to low/normal
        if prev_regime in high_regimes and current_regime in low_regimes:
            return {
                "symbol": "",
                "direction": "close",
                "conviction": 60,
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": 0,
            }

        # Emergency: extreme vol regime → close
        if current_regime == "extreme" and result.risk_state == "emergency":
            return {
                "symbol": "",
                "direction": "close",
                "conviction": 90,
                "entry_price": candle.close,
                "stop_loss": None,
                "take_profit": None,
                "size_pct": 0,
            }

        return None
