"""The Quant — Technical analysis, regime detection, quantitative signals.

Fetches market data → runs regime detector + other modules → interprets via LLM → stores to Supabase.
"""

import json
import logging
from typing import Any

from wolfpack.agents.base import Agent, AgentOutput

logger = logging.getLogger(__name__)

QUANT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "regime_assessment": {"type": "string"},
        "trend_direction": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "trend_strength": {"type": "number", "minimum": 0, "maximum": 100},
        "key_levels": {
            "type": "object",
            "properties": {
                "support": {"type": "array", "items": {"type": "number"}},
                "resistance": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["support", "resistance"],
        },
        "risk_level": {"type": "string", "enum": ["low", "moderate", "elevated", "extreme"]},
        "opportunities": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "conviction": {"type": "number", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
    },
    "required": ["trend_direction", "trend_strength", "risk_level", "conviction", "summary"],
}


class QuantAgent(Agent):
    @property
    def name(self) -> str:
        return "The Quant"

    @property
    def agent_key(self) -> str:
        return "quant"

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
- Assess volatility regimes and risk-adjusted opportunity scores

You receive pre-computed quantitative signals from the modules. Your job is to INTERPRET them,
identify what matters, and produce a clear summary with actionable insights.

Output a JSON object with:
{
    "regime_assessment": "1-2 sentence regime description",
    "trend_direction": "bullish" | "bearish" | "neutral",
    "trend_strength": 0-100,
    "key_levels": {"support": [price, ...], "resistance": [price, ...]},
    "risk_level": "low" | "moderate" | "elevated" | "extreme",
    "opportunities": ["opportunity description", ...],
    "warnings": ["warning description", ...],
    "conviction": 0-100,
    "summary": "2-3 sentence actionable summary"
}

Be precise with numbers. Qualify uncertainty. Never fabricate data that wasn't provided to you."""

    async def analyze(self, market_data: dict[str, Any], exchange: str) -> AgentOutput:
        """Run quantitative analysis: compute signals then interpret via LLM."""
        from wolfpack.exchanges.base import Candle

        candles_raw = market_data.get("candles", [])
        regime_output = market_data.get("regime")
        volatility_output = market_data.get("volatility")
        liquidity_output = market_data.get("liquidity")
        funding_output = market_data.get("funding")
        symbol = market_data.get("symbol", "BTC")

        # Compute basic technical signals from candles
        signals = self._compute_signals(candles_raw)

        # Build context for LLM
        context: dict[str, Any] = {
            "symbol": symbol,
            "exchange": exchange,
            "candle_count": len(candles_raw),
            "technical_signals": signals,
        }

        if regime_output:
            context["regime"] = regime_output if isinstance(regime_output, dict) else regime_output.model_dump()
        if volatility_output:
            context["volatility"] = volatility_output if isinstance(volatility_output, dict) else volatility_output.model_dump()
        if liquidity_output:
            context["liquidity"] = liquidity_output if isinstance(liquidity_output, dict) else liquidity_output.model_dump()
        if funding_output:
            context["funding"] = funding_output if isinstance(funding_output, dict) else funding_output

        # Get latest price info
        if candles_raw:
            last = candles_raw[-1]
            if isinstance(last, Candle):
                context["latest_price"] = last.close
                context["latest_volume"] = last.volume
            elif isinstance(last, dict):
                context["latest_price"] = last.get("close", 0)
                context["latest_volume"] = last.get("volume", 0)

        # Call LLM with structured output
        prompt = f"""Analyze the following quantitative signals for {symbol} on {exchange}:

{json.dumps(context, indent=2, default=str)}"""

        parsed = await self._call_llm_structured(prompt, QUANT_SCHEMA)

        summary = parsed.get("summary", "Analysis complete")
        confidence = float(parsed.get("conviction", 50)) / 100.0

        llm_signals: list[dict[str, Any]] = []
        if parsed.get("trend_direction"):
            llm_signals.append({"type": "trend", "direction": parsed["trend_direction"], "strength": parsed.get("trend_strength", 0)})
        if parsed.get("risk_level"):
            llm_signals.append({"type": "risk", "level": parsed["risk_level"]})
        if parsed.get("key_levels"):
            llm_signals.append({"type": "levels", **parsed["key_levels"]})
        for opp in parsed.get("opportunities", []):
            llm_signals.append({"type": "opportunity", "description": opp})
        for warn in parsed.get("warnings", []):
            llm_signals.append({"type": "warning", "description": warn})

        return AgentOutput(
            agent_name=self.agent_key,
            exchange=exchange,
            timestamp=self._now(),
            summary=summary,
            signals=signals + llm_signals,
            confidence=confidence,
            raw_data={"context": context, "llm_response": parsed},
        )

    def _compute_signals(self, candles: list) -> list[dict[str, Any]]:
        """Compute technical indicators from candle data."""
        from wolfpack.exchanges.base import Candle

        if not candles:
            return []

        closes: list[float] = []
        for c in candles:
            if isinstance(c, Candle):
                closes.append(c.close)
            elif isinstance(c, dict):
                closes.append(float(c.get("close", 0)))

        signals: list[dict[str, Any]] = []

        if len(closes) >= 20:
            sma_20 = sum(closes[-20:]) / 20
            signals.append({"indicator": "SMA_20", "value": round(sma_20, 2)})

        if len(closes) >= 50:
            sma_50 = sum(closes[-50:]) / 50
            signals.append({"indicator": "SMA_50", "value": round(sma_50, 2)})

        if len(closes) >= 2:
            pct_change = (closes[-1] - closes[-2]) / closes[-2] * 100 if closes[-2] != 0 else 0
            signals.append({"indicator": "price_change_pct", "value": round(pct_change, 4)})

        if len(closes) >= 15:
            rsi = self._rsi(closes, 14)
            signals.append({"indicator": "RSI_14", "value": round(rsi, 2)})

        if closes:
            signals.append({"indicator": "latest_close", "value": closes[-1]})

        return signals

    @staticmethod
    def _rsi(closes: list[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(-period, 0):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
