"""The Quant — Technical analysis, regime detection, quantitative signals."""

from typing import Any

from wolfpack.agents.base import Agent, AgentOutput


class QuantAgent(Agent):
    @property
    def name(self) -> str:
        return "The Quant"

    @property
    def role(self) -> str:
        return "Technical Analysis & Regime Detection"

    @property
    def system_prompt(self) -> str:
        return """You are The Quant, a quantitative trading analyst for the WolfPack intelligence system.

Your role:
- Analyze price action, volume profiles, and technical indicators
- Detect market regimes (trending, mean-reverting, volatile, quiet)
- Identify chart patterns and key support/resistance levels
- Calculate momentum, RSI, MACD, Bollinger Bands, and custom signals
- Assess volatility regimes and risk-adjusted opportunity scores

Output format:
- regime: current market regime classification
- trend_direction: bullish/bearish/neutral with strength 0-100
- key_levels: support and resistance prices
- patterns: detected chart patterns with confidence
- indicators: computed indicator values
- signal_strength: overall conviction 0-100

Be precise with numbers. Qualify uncertainty. Never fabricate data."""

    async def analyze(self, market_data: dict[str, Any], exchange: str) -> AgentOutput:
        # Phase 1: Compute quantitative signals from raw market data
        candles = market_data.get("candles", [])
        signals = self._compute_signals(candles)

        # Phase 2: LLM interpretation of signals (to be wired up)
        # For now, return computed signals directly

        return AgentOutput(
            agent_name=self.name,
            exchange=exchange,
            timestamp=self._now(),
            summary="Quantitative analysis pending LLM integration",
            signals=signals,
            confidence=0.0,
            raw_data={"candle_count": len(candles)},
        )

    def _compute_signals(self, candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compute technical indicators from candle data."""
        if not candles:
            return []

        closes = [c.get("close", 0) for c in candles]
        signals = []

        # Simple moving averages
        if len(closes) >= 20:
            sma_20 = sum(closes[-20:]) / 20
            signals.append({"indicator": "SMA_20", "value": round(sma_20, 2)})

        if len(closes) >= 50:
            sma_50 = sum(closes[-50:]) / 50
            signals.append({"indicator": "SMA_50", "value": round(sma_50, 2)})

        # Price change
        if len(closes) >= 2:
            pct_change = (closes[-1] - closes[-2]) / closes[-2] * 100
            signals.append({"indicator": "price_change_pct", "value": round(pct_change, 4)})

        # Simple RSI approximation (14-period)
        if len(closes) >= 15:
            gains = []
            losses = []
            for i in range(-14, 0):
                diff = closes[i] - closes[i - 1]
                if diff > 0:
                    gains.append(diff)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(diff))
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            signals.append({"indicator": "RSI_14", "value": round(rsi, 2)})

        return signals
