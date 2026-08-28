"""Capitulation Flush — long-only mean-reversion on post-cascade alt bars.

Hypothesis (validated Phase 4, t > 2 cross-symbol):
  When 5-bar log return drops below the 5th percentile of the trailing 120-bar
  distribution → forward 4-12 bar return is positive.

Survivors at Phase 4 (4 gates, 28mo Hyperliquid 4h):
  - AVAX  h=4  Sharpe 3.52  cum +240.6%
  - DOGE  h=12 Sharpe 2.72  cum +451.0%
  - LINK  h=12 Sharpe 1.77  cum +278.4%

Fails on BTC, ETH, SOL, ARB (Gate 1 or 2 fail). Strategy is therefore
explicitly gated to alts where the signal validated.
"""

import numpy as np

from wolfpack.exchanges.base import Candle
from wolfpack.price_utils import round_price
from wolfpack.strategies.base import Strategy


class CapitulationFlushStrategy(Strategy):
    name = "capitulation_flush"
    description = "Long alts after sharp 5-bar drops below 5th percentile of trailing 120 bars"
    parameters = {
        "lookback": {
            "type": "int", "default": 120, "min": 60, "max": 240,
            "desc": "Trailing bars for percentile distribution",
        },
        "percentile": {
            "type": "float", "default": 5.0, "min": 1.0, "max": 15.0,
            "desc": "Percentile threshold (lower = sharper flush)",
        },
        "stop_atr_mult": {
            "type": "float", "default": 3.0, "min": 1.0, "max": 5.0,
            "desc": "Stop loss distance in ATR units",
        },
        "tp_atr_mult": {
            "type": "float", "default": 1.5, "min": 0.5, "max": 4.0,
            "desc": "Take profit distance in ATR units",
        },
        "size_pct": {
            "type": "float", "default": 10.0, "min": 1.0, "max": 25.0,
            "desc": "Position size as % of equity",
        },
    }

    @property
    def warmup_bars(self) -> int:
        return 130  # 120 + 5-bar return + buffer

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        lookback = int(params.get("lookback", 120))
        percentile = float(params.get("percentile", 5.0))
        stop_atr_mult = float(params.get("stop_atr_mult", 3.0))
        tp_atr_mult = float(params.get("tp_atr_mult", 1.5))
        size_pct = float(params.get("size_pct", 10.0))

        # Need at least lookback + 5 + buffer
        if current_idx < lookback + 6:
            return None

        window = candles[: current_idx + 1]
        closes = np.array([c.close for c in window], dtype=np.float64)
        log_close = np.log(closes)

        # Current bar's 5-bar log return
        current_ret_5 = log_close[-1] - log_close[-6]

        # Trailing distribution of 5-bar returns over `lookback` bars
        # ret_5[i] = log_close[i] - log_close[i-5], for i in last `lookback` bars
        end = len(log_close) - 1
        start = end - lookback
        rets_5 = log_close[start:end] - log_close[start - 5 : end - 5]
        if len(rets_5) < 30:
            return None

        thresh = float(np.percentile(rets_5, percentile))

        # Fire only on capitulation (current bar in bottom percentile)
        if current_ret_5 >= thresh:
            return None

        # ATR(14) for stop/TP scaling
        atr = self._compute_atr(window, 14)
        if atr <= 0:
            return None

        current_close = closes[-1]
        return {
            "symbol": "",
            "direction": "long",
            "conviction": 70,
            "entry_price": current_close,
            "stop_loss": round_price(current_close - stop_atr_mult * atr),
            "take_profit": round_price(current_close + tp_atr_mult * atr),
            "size_pct": size_pct,
        }

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
