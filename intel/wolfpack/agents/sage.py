"""The Sage — Forecasting, correlation analysis, macro outlook.

Analyzes cross-asset correlations, regime context, and funding data
to produce probability-weighted scenarios and macro outlook.
"""

import json
import logging
from typing import Any

from wolfpack.agents.base import Agent, AgentOutput

logger = logging.getLogger(__name__)

SAGE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "weekly_outlook": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "outlook_rationale": {"type": "string"},
        "scenario_matrix": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scenario": {"type": "string"},
                    "probability": {"type": "number", "minimum": 0, "maximum": 100},
                    "key_levels": {
                        "type": "object",
                        "properties": {
                            "support": {"type": "number"},
                            "resistance": {"type": "number"},
                        },
                    },
                    "triggers": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["scenario", "probability"],
            },
        },
        "correlation_assessment": {"type": "string"},
        "macro_context": {"type": "string"},
        "carry_opportunities": {"type": "array", "items": {"type": "string"}},
        "regime_transition_risk": {"type": "string", "enum": ["low", "moderate", "high"]},
        "conviction": {"type": "number", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
    },
    "required": ["weekly_outlook", "scenario_matrix", "conviction", "summary"],
}


class SageAgent(Agent):
    @property
    def name(self) -> str:
        return "The Sage"

    @property
    def agent_key(self) -> str:
        return "sage"

    @property
    def role(self) -> str:
        return "Forecasting & Macro Analysis"

    @property
    def system_prompt(self) -> str:
        return """You are The Sage, the strategic forecaster for the WolfPack intelligence system.

Your role:
- Analyze cross-asset correlations (BTC/ETH beta, tail correlation, diversification)
- Produce probability-weighted scenarios (bull/bear/base case)
- Assess macro conditions from regime detection and funding data
- Identify regime transitions before they complete
- Evaluate carry opportunities from funding rate differentials
- Flag correlation regime changes (crisis lock, decorrelation events)

You receive quantitative module outputs. Use them to build a forward-looking view.

Output a JSON object with:
{
    "weekly_outlook": "bullish" | "bearish" | "neutral",
    "outlook_rationale": "1-2 sentence rationale",
    "scenario_matrix": [
        {"scenario": "description", "probability": 0-100, "key_levels": {"support": price, "resistance": price}, "triggers": ["trigger1"]}
    ],
    "correlation_assessment": "description of cross-asset dynamics",
    "macro_context": "relevant macro factors inferred from data",
    "carry_opportunities": ["opportunity description", ...],
    "regime_transition_risk": "low" | "moderate" | "high",
    "conviction": 0-100,
    "summary": "2-3 sentence strategic summary"
}

Think in probabilities, not certainties. Always present at least 2 scenarios. Challenge consensus views.

Return ONLY a valid JSON object. No markdown, no code fences, no explanation outside the JSON."""

    async def analyze(self, market_data: dict[str, Any], exchange: str) -> AgentOutput:
        symbol = market_data.get("symbol", "BTC")

        context: dict[str, Any] = {
            "symbol": symbol,
            "exchange": exchange,
        }

        # Correlation data (BTC/ETH)
        if market_data.get("correlation"):
            corr = market_data["correlation"]
            context["correlation"] = corr if isinstance(corr, dict) else corr.model_dump()

        # Regime context
        if market_data.get("regime"):
            regime = market_data["regime"]
            context["regime"] = regime if isinstance(regime, dict) else regime.model_dump()

        # Funding data
        if market_data.get("funding"):
            funding = market_data["funding"]
            context["funding"] = funding if isinstance(funding, dict) else funding.model_dump()

        # Volatility context
        if market_data.get("volatility"):
            vol = market_data["volatility"]
            context["volatility"] = vol if isinstance(vol, dict) else vol.model_dump()

        # Liquidity context
        if market_data.get("liquidity"):
            liq = market_data["liquidity"]
            context["liquidity"] = liq if isinstance(liq, dict) else liq.model_dump()

        # Latest price for scenario levels
        if market_data.get("latest_price"):
            context["latest_price"] = market_data["latest_price"]

        prompt = f"""Produce a strategic forecast for {symbol} on {exchange} from these quantitative signals:

{json.dumps(context, indent=2, default=str)}"""

        parsed = await self._call_llm_structured(prompt, SAGE_SCHEMA)

        summary = parsed.get("summary", "Strategic forecast complete")
        confidence = float(parsed.get("conviction", 35)) / 100.0

        signals: list[dict[str, Any]] = []

        if parsed.get("weekly_outlook"):
            signals.append({
                "type": "outlook",
                "direction": parsed["weekly_outlook"],
                "rationale": parsed.get("outlook_rationale", ""),
            })

        for scenario in parsed.get("scenario_matrix", []):
            signals.append({
                "type": "scenario",
                "description": scenario.get("scenario", ""),
                "probability": scenario.get("probability", 0),
                "triggers": scenario.get("triggers", []),
            })

        if parsed.get("regime_transition_risk"):
            signals.append({
                "type": "regime_risk",
                "level": parsed["regime_transition_risk"],
            })

        if parsed.get("correlation_assessment"):
            signals.append({
                "type": "correlation",
                "assessment": parsed["correlation_assessment"],
            })

        for opp in parsed.get("carry_opportunities", []):
            signals.append({"type": "carry", "description": opp})

        return AgentOutput(
            agent_name=self.agent_key,
            exchange=exchange,
            timestamp=self._now(),
            summary=summary,
            signals=signals,
            confidence=confidence,
            raw_data={"context": context, "llm_response": parsed},
        )
