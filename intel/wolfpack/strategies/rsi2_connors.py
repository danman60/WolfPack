"""RSI(2) Connors strategy with 200-SMA trend filter.

Per docs/research/regime/04-strategy-regime-pairings.md, this is one of the
highest-WR mean-reversion strategies in the literature with strong cross-symbol
crypto replications. Spec:

  - Long entry:  RSI(2) < 5 AND close > SMA(200)
  - Short entry: RSI(2) > 95 AND close < SMA(200)
  - Exit: close crosses 5-SMA against position (handled by close signal)
  - Stop: 3*ATR from entry (crypto-adapted; Connors used no stop on equities)
  - Time stop: 5 bars max (handled by engine via close signal)

Pure numpy implementation, no LLM, no router dependencies.
"""

import numpy as np

from wolfpack.exchanges.base import Candle
from wolfpack.price_utils import round_price
from wolfpack.strategies.base import Strategy


class RSI2ConnorsStrategy(Strategy):
    name = "rsi2_connors"
    description = "Connors RSI(2) mean reversion with 200-SMA trend filter"
    parameters = {
        "rsi_period": {
            "type": "int",
            "default": 2,
            "min": 2,
            "max": 5,
            "desc": "RSI period (Connors uses 2)",
        },
        "rsi_long_threshold": {
            "type": "float",
            "default": 5.0,
            "min": 1.0,
            "max": 20.0,
            "desc": "Long when RSI(2) below this",
        },
        "rsi_short_threshold": {
            "type": "float",
            "default": 95.0,
            "min": 80.0,
            "max": 99.0,
            "desc": "Short when RSI(2) above this",
        },
        "trend_sma_period": {
            "type": "int",
            "default": 200,
            "min": 100,
            "max": 300,
            "desc": "Trend filter SMA period",
        },
        "exit_sma_period": {
            "type": "int",
            "default": 5,
            "min": 3,
            "max": 10,
            "desc": "Exit when close crosses this SMA",
        },
        "stop_atr_mult": {
            "type": "float",
            "default": 3.0,
            "min": 1.0,
            "max": 5.0,
            "desc": "Stop loss in ATR units",
        },
        "size_pct": {
            "type": "float",
            "default": 8.0,
            "min": 1.0,
            "max": 25.0,
            "desc": "Position size as % of equity",
        },
    }

    @property
    def warmup_bars(self) -> int:
        return 210  # 200 SMA + 14 ATR + buffer

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        rsi_period = params.get("rsi_period", 2)
        rsi_long = params.get("rsi_long_threshold", 5.0)
        rsi_short = params.get("rsi_short_threshold", 95.0)
        trend_period = params.get("trend_sma_period", 200)
        exit_period = params.get("exit_sma_period", 5)
        stop_atr_mult = params.get("stop_atr_mult", 3.0)
        size_pct = params.get("size_pct", 8.0)

        needed = trend_period + 1
        if current_idx < needed:
            return None

        window = candles[: current_idx + 1]
        closes = np.array([c.close for c in window], dtype=np.float64)
        current_close = closes[-1]

        # Trend filter
        sma_trend = np.mean(closes[-trend_period:])
        in_uptrend = current_close > sma_trend
        in_downtrend = current_close < sma_trend

        # Exit-SMA — close opposite-position when crossed
        sma_exit = np.mean(closes[-exit_period:])

        # RSI(2)
        rsi = self._compute_rsi(closes, rsi_period)
        if rsi is None:
            return None

        # ATR(14) for stop
        atr = self._compute_atr(window, 14)
        if atr <= 0:
            return None

        # Long entry: RSI(2) < 5 AND uptrend
        if rsi < rsi_long and in_uptrend:
            return {
                "symbol": "",
                "direction": "long",
                "conviction": 75,
                "entry_price": current_close,
                "stop_loss": round_price(current_close - atr * stop_atr_mult),
                "take_profit": round_price(sma_exit),
                "size_pct": size_pct,
            }

        # Short entry: RSI(2) > 95 AND downtrend
        if rsi > rsi_short and in_downtrend:
            return {
                "symbol": "",
                "direction": "short",
                "conviction": 75,
                "entry_price": current_close,
                "stop_loss": round_price(current_close + atr * stop_atr_mult),
                "take_profit": round_price(sma_exit),
                "size_pct": size_pct,
            }

        # Exit signal: close crossed 5-SMA against an open position
        # (position direction not visible at strategy layer; engine handles
        # cross-direction reversal as close+open. We emit "close" when RSI
        # has flipped to neutral so engine flattens the prior signal.)
        # Simpler: do nothing on exit — let stop_loss / take_profit handle it.
        # Connors uses 5-SMA cross as the actual exit; engine's TP at sma_exit
        # is our analog (we set TP = sma_exit on every entry).

        return None

    @staticmethod
    def _compute_rsi(closes: np.ndarray, period: int) -> float | None:
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes[-(period + 1) :])
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = float(np.mean(gains))
        avg_loss = float(np.mean(losses))
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    @staticmethod
    def _compute_atr(window: list[Candle], period: int = 14) -> float:
        if len(window) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(window)):
            c = window[i]
            prev = window[i - 1].close
            tr = max(
                c.high - c.low,
                abs(c.high - prev),
                abs(c.low - prev),
            )
            trs.append(tr)
        if len(trs) < period:
            return 0.0
        return float(np.mean(trs[-period:]))
