"""Trend Pullback Strategy -- buy the dip / sell the rip in confirmed trends.

The gap it fills: ema_crossover and turtle_donchian only fire on the
fresh cross/breakout event. Once a trend is established and price is
mid-move, those strategies go silent even though the trend still has
edge. This strategy fires during active trends when price pulls back
to the fast EMA (20), giving trending regimes a continuously-active
entry signal.

Regime gating:
  TRENDING_UP     → long-only, fires on pullback to EMA(20) from above
  TRENDING_DOWN   → short-only, fires on rally to EMA(20) from below
  RANGING_*       → disabled (pullback is the whole move in chop)
  VOLATILE        → disabled
  TRANSITION      → disabled
  None            → both directions (backward compat)

Entry criteria (long example):
  1. macro_regime == TRENDING_UP
  2. EMA(20) > EMA(50) (trend filter)
  3. Prior bar's low <= EMA(20) (pullback touch)
  4. Current bar's close > EMA(20) (rejection/bounce confirmation)
  5. RSI(14) between 40-70 (not oversold panic, not overbought exhaustion)

Short flips every inequality.

Targets the recent swing high (long) / swing low (short) with ATR stop
just beyond the EMA. Pure numpy implementation.
"""

import numpy as np

from wolfpack.exchanges.base import Candle
from wolfpack.price_utils import round_price
from wolfpack.strategies.base import Strategy

_LONG_OK = frozenset({"TRENDING_UP", "TRENDING", None})
_SHORT_OK = frozenset({"TRENDING_DOWN", "TRENDING", None})
_DISABLED = frozenset(
    {"RANGING", "RANGING_LOW_VOL", "RANGING_HIGH_VOL", "VOLATILE", "TRANSITION"}
)


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1)
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


def _rsi(closes: np.ndarray, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


class TrendPullbackStrategy(Strategy):
    name = "trend_pullback"
    description = "Pullback-to-EMA entries during confirmed TRENDING_UP / TRENDING_DOWN regimes"
    parameters = {
        "fast_ema": {"type": "int", "default": 20, "min": 10, "max": 50, "desc": "Fast EMA (pullback target)"},
        "slow_ema": {"type": "int", "default": 50, "min": 20, "max": 200, "desc": "Slow EMA (trend filter)"},
        "atr_period": {"type": "int", "default": 14, "min": 7, "max": 30, "desc": "ATR lookback"},
        "stop_atr_mult": {"type": "float", "default": 0.8, "min": 0.3, "max": 2.0, "desc": "ATR buffer beyond EMA for stop"},
        "rsi_low": {"type": "float", "default": 40.0, "min": 20.0, "max": 50.0, "desc": "Min RSI for long entry"},
        "rsi_high": {"type": "float", "default": 70.0, "min": 55.0, "max": 85.0, "desc": "Max RSI for long entry"},
        "size_pct": {"type": "float", "default": 10.0, "min": 1.0, "max": 25.0, "desc": "Position size as % of equity"},
    }

    @property
    def warmup_bars(self) -> int:
        return 60  # slow_ema + headroom

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        macro_regime = params.get("macro_regime")
        if macro_regime in _DISABLED:
            return None

        fast_ema_p = int(params.get("fast_ema", 20))
        slow_ema_p = int(params.get("slow_ema", 50))
        atr_period = int(params.get("atr_period", 14))
        stop_atr_mult = float(params.get("stop_atr_mult", 0.8))
        rsi_low = float(params.get("rsi_low", 40.0))
        rsi_high = float(params.get("rsi_high", 70.0))
        size_pct = float(params.get("size_pct", 10.0))

        needed = slow_ema_p + 2
        if current_idx < needed:
            return None

        window = candles[: current_idx + 1]
        if len(window) < needed:
            return None

        closes = np.array([c.close for c in window], dtype=np.float64)
        highs = np.array([c.high for c in window], dtype=np.float64)
        lows = np.array([c.low for c in window], dtype=np.float64)

        ema_fast = _ema(closes, fast_ema_p)
        ema_slow = _ema(closes, slow_ema_p)

        current_close = closes[-1]
        prev_low = lows[-2]
        prev_high = highs[-2]
        cur_ema_fast = ema_fast[-1]
        cur_ema_slow = ema_slow[-1]

        rsi_val = _rsi(closes, 14)
        if rsi_val is None:
            return None

        atr = self._compute_atr(window, atr_period)
        if atr <= 0:
            return None

        # Long pullback: uptrend structure + pullback touch + bounce confirmation
        uptrend = cur_ema_fast > cur_ema_slow
        downtrend = cur_ema_fast < cur_ema_slow

        if (
            uptrend
            and macro_regime in _LONG_OK
            and prev_low <= cur_ema_fast  # pulled into fast EMA
            and current_close > cur_ema_fast  # closed back above it
            and rsi_low <= rsi_val <= rsi_high
        ):
            stop_loss = round_price(cur_ema_fast - atr * stop_atr_mult)
            # Target: recent 20-bar swing high (if extended above current price)
            swing_high = float(np.max(highs[-20:]))
            take_profit = swing_high if swing_high > current_close else None
            return {
                "symbol": "",
                "direction": "long",
                "conviction": 75 if macro_regime == "TRENDING_UP" else 70,
                "entry_price": current_close,
                "stop_loss": stop_loss,
                "take_profit": round_price(take_profit) if take_profit else None,
                "size_pct": size_pct,
            }

        # Short pullback: downtrend structure + rally into fast EMA + rejection
        if (
            downtrend
            and macro_regime in _SHORT_OK
            and prev_high >= cur_ema_fast  # rallied into fast EMA
            and current_close < cur_ema_fast  # closed back below it
            and (100.0 - rsi_high) <= rsi_val <= (100.0 - rsi_low)
            # mirrored RSI band: 30-60 for shorts (inverse of 40-70 for longs)
        ):
            stop_loss = round_price(cur_ema_fast + atr * stop_atr_mult)
            swing_low = float(np.min(lows[-20:]))
            take_profit = swing_low if swing_low < current_close else None
            return {
                "symbol": "",
                "direction": "short",
                "conviction": 75 if macro_regime == "TRENDING_DOWN" else 70,
                "entry_price": current_close,
                "stop_loss": stop_loss,
                "take_profit": round_price(take_profit) if take_profit else None,
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
