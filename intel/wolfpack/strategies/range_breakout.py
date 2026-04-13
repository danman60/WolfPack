"""Range Breakout -- fires on 20-bar high/low breakouts in RANGING regimes.

Built 2026-04-13 as part of the regime-edge exploration phase. Hypothesis:
ranges eventually break. When they do, the expansion move is profitable to
ride to a measured target. Mean-reversion fails in breakout moves because
it bets AGAINST the break. This probe catches those breaks.

Signal logic:
  - Lookback: 20 prior bars (excluding current) define the range high/low
  - Long trigger: current close above prior 20-bar high
  - Short trigger: current close below prior 20-bar low
  - Volume confirmation: current bar volume >= 1.5x 10-bar average
  - Stop: mid-range (average of prior high and low)
  - Target: 1x range width beyond the breakout level

Regime gating: RANGING_LOW_VOL / RANGING_HIGH_VOL only. In TRENDING regimes,
turtle_donchian handles breakouts.

This is a probe strategy (4% size) — no historical validation yet.
"""

from wolfpack.exchanges.base import Candle
from wolfpack.price_utils import round_price
from wolfpack.strategies.base import Strategy

_RANGING_REGIMES = frozenset({"RANGING", "RANGING_LOW_VOL", "RANGING_HIGH_VOL"})


class RangeBreakoutStrategy(Strategy):
    name = "range_breakout"
    description = "20-bar range break with volume confirmation — RANGING regimes only"
    parameters = {
        "lookback": {
            "type": "int", "default": 20, "min": 10, "max": 50,
            "desc": "Bars defining the range",
        },
        "vol_mult": {
            "type": "float", "default": 1.5, "min": 1.0, "max": 3.0,
            "desc": "Volume multiple vs 10-bar average",
        },
        "size_pct": {
            "type": "float", "default": 4.0, "min": 1.0, "max": 15.0,
            "desc": "Position size as % of equity (probe)",
        },
    }

    @property
    def warmup_bars(self) -> int:
        return 25

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        macro_regime = params.get("macro_regime")
        if macro_regime is not None and macro_regime not in _RANGING_REGIMES:
            return None

        lookback = int(params.get("lookback", 20))
        vol_mult = float(params.get("vol_mult", 1.5))
        size_pct = float(params.get("size_pct", 4.0))

        needed = lookback + 2
        if current_idx < needed:
            return None

        prior_window = candles[current_idx - lookback : current_idx]
        if len(prior_window) < lookback:
            return None
        current = candles[current_idx]

        prior_high = max(c.high for c in prior_window)
        prior_low = min(c.low for c in prior_window)
        range_width = prior_high - prior_low
        if range_width <= 0:
            return None
        mid_range = (prior_high + prior_low) / 2

        # Volume confirmation
        vol_window = candles[max(0, current_idx - 10) : current_idx]
        if not vol_window:
            return None
        avg_vol = sum(c.volume for c in vol_window) / len(vol_window)
        if avg_vol <= 0:
            return None
        if current.volume < avg_vol * vol_mult:
            return None

        # LONG: break above prior high
        if current.close > prior_high:
            entry = float(current.close)
            stop = round_price(mid_range)
            target = round_price(entry + range_width)
            return {
                "symbol": "",
                "direction": "long",
                "conviction": 70,
                "entry_price": entry,
                "stop_loss": stop,
                "take_profit": target,
                "size_pct": size_pct,
            }

        # SHORT: break below prior low
        if current.close < prior_low:
            entry = float(current.close)
            stop = round_price(mid_range)
            target = round_price(entry - range_width)
            return {
                "symbol": "",
                "direction": "short",
                "conviction": 70,
                "entry_price": entry,
                "stop_loss": stop,
                "take_profit": target,
                "size_pct": size_pct,
            }

        return None
