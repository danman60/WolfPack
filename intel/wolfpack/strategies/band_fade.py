"""Band Fade Strategy -- fade Bollinger Band touches in RANGING regimes.

Pure RANGING play. Fires when:
  - Price closes outside the Bollinger Band (20 SMA ± N stdev)
  - RSI(14) is in oversold/overbought territory
  - Prior bar confirms the touch (not mid-trend continuation)

Targets the 20 SMA (middle band) for TP, with a tight stop beyond the outer band.

Regime gating: only fires in RANGING_LOW_VOL or RANGING_HIGH_VOL. Other
sub-regimes return None. The band-stdev and RSI thresholds also auto-tune
per sub-regime — HIGH_VOL uses 2.5 stdev + stricter RSI, LOW_VOL uses 2.0
stdev + standard RSI.

This is the strategy that was missing from the range book. mean_reversion at its
default 3.0 ATR threshold fires on extreme reversals; band_fade fires on normal
range oscillation (1-2 stdev moves), which is the bread-and-butter of choppy
markets.

Pure numpy implementation.
"""

_RANGING_REGIMES = frozenset({"RANGING", "RANGING_LOW_VOL", "RANGING_HIGH_VOL"})
# Empirical tuning: live probe 2026-04-13 showed RSI range 43-53 and all
# 7 symbols sitting inside the 2σ Bollinger Band. LOW_VOL presets drop to
# 1.0σ + RSI 42/58 so the strategy can fire in extreme mid-range equilibrium.
# HIGH_VOL stays tighter because wider chop = more noise = need more conviction.
_REGIME_PRESETS = {
    "RANGING_LOW_VOL": {
        "bb_period": 15,
        "bb_stdev": 1.0,
        "rsi_oversold": 42.0,
        "rsi_overbought": 58.0,
        "stop_atr_mult": 0.4,
        "size_pct": 6.0,
    },
    "RANGING_HIGH_VOL": {
        "bb_period": 20,
        "bb_stdev": 2.0,
        "rsi_oversold": 35.0,
        "rsi_overbought": 65.0,
        "stop_atr_mult": 0.8,
        "size_pct": 8.0,
    },
}

import numpy as np

from wolfpack.exchanges.base import Candle
from wolfpack.price_utils import round_price
from wolfpack.strategies.base import Strategy


class BandFadeStrategy(Strategy):
    name = "band_fade"
    description = "Bollinger Band + RSI reversion — fires on range oscillations in RANGING regime"
    parameters = {
        "bb_period": {
            "type": "int",
            "default": 20,
            "min": 10,
            "max": 50,
            "desc": "Bollinger Band SMA period",
        },
        "bb_stdev": {
            "type": "float",
            "default": 2.0,
            "min": 1.5,
            "max": 3.0,
            "desc": "Number of standard deviations for band width",
        },
        "rsi_period": {
            "type": "int",
            "default": 14,
            "min": 7,
            "max": 21,
            "desc": "RSI lookback",
        },
        "rsi_oversold": {
            "type": "float",
            "default": 35.0,
            "min": 20.0,
            "max": 40.0,
            "desc": "RSI threshold for long entry",
        },
        "rsi_overbought": {
            "type": "float",
            "default": 65.0,
            "min": 60.0,
            "max": 80.0,
            "desc": "RSI threshold for short entry",
        },
        "stop_atr_mult": {
            "type": "float",
            "default": 0.6,
            "min": 0.3,
            "max": 1.5,
            "desc": "Stop loss distance in ATR units beyond the band",
        },
        "size_pct": {
            "type": "float",
            "default": 10.0,
            "min": 1.0,
            "max": 25.0,
            "desc": "Position size as % of equity",
        },
    }

    @property
    def warmup_bars(self) -> int:
        return 35  # enough for BB(20) + RSI(14)

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        macro_regime = params.get("macro_regime")
        # Pure RANGING play — don't fire in trends, volatile panic, or transitions
        if macro_regime is not None and macro_regime not in _RANGING_REGIMES:
            return None

        # Pick sub-regime preset (HIGH_VOL vs LOW_VOL). Fallback: LOW_VOL defaults.
        preset = _REGIME_PRESETS.get(
            macro_regime or "RANGING_LOW_VOL",
            _REGIME_PRESETS["RANGING_LOW_VOL"],
        )

        bb_period = int(params.get("bb_period", preset.get("bb_period", 20)))
        bb_stdev = float(params.get("bb_stdev", preset["bb_stdev"]))
        rsi_period = int(params.get("rsi_period", 14))
        rsi_oversold = float(params.get("rsi_oversold", preset["rsi_oversold"]))
        rsi_overbought = float(params.get("rsi_overbought", preset["rsi_overbought"]))
        stop_atr_mult = float(params.get("stop_atr_mult", preset["stop_atr_mult"]))
        size_pct = float(params.get("size_pct", preset["size_pct"]))

        needed = max(bb_period, rsi_period) + 2
        if current_idx < needed:
            return None

        window = candles[: current_idx + 1]
        if len(window) < needed:
            return None

        closes = np.array([c.close for c in window], dtype=np.float64)
        current_close = closes[-1]
        prev_close = closes[-2]

        # Bollinger Band
        bb_slice = closes[-bb_period:]
        middle = float(np.mean(bb_slice))
        std = float(np.std(bb_slice, ddof=0))
        if std <= 0:
            return None
        upper = middle + bb_stdev * std
        lower = middle - bb_stdev * std

        # RSI(14) — Wilder's smoothing
        rsi = self._compute_rsi(closes, rsi_period)
        if rsi is None:
            return None

        # ATR for stop distance
        atr = self._compute_atr(window, 14)
        if atr <= 0:
            return None

        # Long: price closed below lower band (this bar or last) AND RSI oversold
        touched_lower = current_close <= lower or prev_close <= lower
        if touched_lower and rsi <= rsi_oversold:
            # Stop sits one ATR fraction below the lower band
            stop = round_price(min(lower, current_close) - atr * stop_atr_mult)
            conviction = 65
            if rsi < 25:
                conviction += 10  # deep oversold bonus
            # Confirmation: body closing up off the low = reversal strength
            last = window[-1]
            if last.close > last.open and last.close > prev_close:
                conviction += 5
            return {
                "symbol": "",
                "direction": "long",
                "conviction": min(conviction, 90),
                "entry_price": current_close,
                "stop_loss": stop,
                "take_profit": round_price(middle),
                "size_pct": size_pct,
            }

        # Short: price closed above upper band AND RSI overbought
        touched_upper = current_close >= upper or prev_close >= upper
        if touched_upper and rsi >= rsi_overbought:
            stop = round_price(max(upper, current_close) + atr * stop_atr_mult)
            conviction = 65
            if rsi > 75:
                conviction += 10
            last = window[-1]
            if last.close < last.open and last.close < prev_close:
                conviction += 5
            return {
                "symbol": "",
                "direction": "short",
                "conviction": min(conviction, 90),
                "entry_price": current_close,
                "stop_loss": stop,
                "take_profit": round_price(middle),
                "size_pct": size_pct,
            }

        return None

    @staticmethod
    def _compute_rsi(closes: np.ndarray, period: int = 14) -> float | None:
        """Wilder's RSI on a 1D closes array."""
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Seed with simple average over the first `period` bars
        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))

        # Wilder smoothing for the remainder
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _compute_atr(candles: list[Candle], period: int = 14) -> float:
        """Average True Range over the last `period` candles."""
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
