"""The Quant — Technical analysis, regime detection, quantitative signals.

Fetches market data → runs regime detector + other modules → interprets via LLM → stores to Supabase.
"""

import json
import logging
from typing import Any

from wolfpack.agents.base import Agent, AgentOutput
from wolfpack.config import settings

logger = logging.getLogger(__name__)


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

        # Call LLM for interpretation
        llm_analysis = await self._call_llm(context)

        # Parse LLM response
        try:
            parsed = json.loads(llm_analysis) if isinstance(llm_analysis, str) else llm_analysis
            summary = parsed.get("summary", llm_analysis if isinstance(llm_analysis, str) else "Analysis complete")
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
        except (json.JSONDecodeError, TypeError, AttributeError):
            summary = llm_analysis if isinstance(llm_analysis, str) else "Analysis complete"
            confidence = 0.5
            llm_signals = signals

        all_signals = signals + llm_signals

        return AgentOutput(
            agent_name=self.agent_key,
            exchange=exchange,
            timestamp=self._now(),
            summary=summary,
            signals=all_signals,
            confidence=confidence,
            raw_data={"context": context, "llm_response": llm_analysis},
        )

    async def _call_llm(self, context: dict) -> str:
        """Call LLM (Anthropic Claude or DeepSeek) to interpret quantitative signals."""
        prompt = f"""Analyze the following quantitative signals for {context.get('symbol', 'BTC')} on {context.get('exchange', 'hyperliquid')}:

{json.dumps(context, indent=2, default=str)}

Respond with ONLY a JSON object matching the format specified in your system prompt."""

        if settings.anthropic_api_key:
            return await self._call_anthropic(prompt)
        elif settings.deepseek_api_key:
            return await self._call_deepseek(prompt)
        else:
            logger.warning("No LLM API key configured — returning raw signals only")
            return json.dumps({
                "regime_assessment": f"Regime: {context.get('regime', {}).get('regime', 'unknown')}",
                "trend_direction": "neutral",
                "trend_strength": 50,
                "key_levels": {"support": [], "resistance": []},
                "risk_level": "moderate",
                "opportunities": [],
                "warnings": ["No LLM API key configured"],
                "conviction": 30,
                "summary": "Quantitative signals computed but no LLM available for interpretation.",
            })

    async def _call_anthropic(self, prompt: str) -> str:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        try:
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def _call_deepseek(self, prompt: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        try:
            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1024,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise

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
