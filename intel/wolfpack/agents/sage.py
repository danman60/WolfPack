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
        "oi_divergence_signal": {"type": "string"},
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
- Analyze Open Interest levels for crowding risk (price up + OI down = bearish divergence)
- Use Fear & Greed extremes as contrarian signals (extreme fear = potential bottom, extreme greed = potential top)
- Factor whale positioning as directional bias input (whale net long/short)

You receive quantitative module outputs plus social/whale intelligence. Use all data to build a forward-looking view.

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
    "oi_divergence_signal": "description of OI vs price divergence, if any",
    "conviction": 0-100,
    "summary": "2-3 sentence strategic summary"
}

Think in probabilities, not certainties. Always present at least 2 scenarios. Challenge consensus views.

CALIBRATION EXAMPLES:

Example 1 — Bullish with 3-scenario matrix:
{"weekly_outlook": "bullish", "outlook_rationale": "Regime trending bullish, BTC/ETH correlation stable at 0.82, funding neutral — constructive setup for continuation.", "scenario_matrix": [{"scenario": "Bullish continuation to 100k", "probability": 55, "key_levels": {"support": 94000, "resistance": 100000}, "triggers": ["Break above 98k on volume", "ETH relative strength confirms"]}, {"scenario": "Range consolidation 93k-98k", "probability": 30, "key_levels": {"support": 93000, "resistance": 98000}, "triggers": ["Volume dries up", "Funding stays neutral"]}, {"scenario": "Pullback to 90k support", "probability": 15, "key_levels": {"support": 90000, "resistance": 95000}, "triggers": ["Macro risk event", "Correlation spike to 0.95+ signals risk-off"]}], "correlation_assessment": "BTC/ETH rolling correlation at 0.82 — normal range. No crisis lock or decorrelation event.", "macro_context": "Risk-on environment with DXY weakening. Crypto benefiting from rotation out of treasuries.", "carry_opportunities": ["ETH funding -0.02% — slight short crowding creates long carry opportunity"], "regime_transition_risk": "low", "oi_divergence_signal": "OI rising with price — confirming trend. No bearish divergence.", "conviction": 70, "summary": "Constructive macro backdrop with confirmed trend. Primary scenario is continuation to 100k (55% probability). Risk is a consolidation pause, not a reversal. Carry opportunity in ETH."}

Example 2 — Bearish with OI divergence:
{"weekly_outlook": "bearish", "outlook_rationale": "Price at local highs but OI declining — classic bearish divergence. Whales net short, funding elevated against longs.", "scenario_matrix": [{"scenario": "Correction to 88k", "probability": 50, "key_levels": {"support": 88000, "resistance": 95000}, "triggers": ["OI continues dropping while price stalls", "Liquidation cascade below 92k"]}, {"scenario": "Choppy range 91k-95k", "probability": 35, "key_levels": {"support": 91000, "resistance": 95000}, "triggers": ["Funding resets to neutral", "Whale selling pauses"]}], "correlation_assessment": "Tail correlation elevated at 0.93 — approaching crisis lock territory. Diversification benefit reduced.", "macro_context": "Elevated DXY and rising yields creating headwinds for risk assets.", "carry_opportunities": [], "regime_transition_risk": "high", "oi_divergence_signal": "BEARISH DIVERGENCE: Price up 3.2% this week while OI down 8.5% — smart money reducing exposure into strength.", "conviction": 62, "summary": "OI divergence is the dominant signal — price action is misleading. High probability of a correction to 88k. Regime transition risk elevated with correlation approaching crisis levels."}

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
        if market_data.get("open_interest_usd"):
            context["open_interest_usd"] = market_data["open_interest_usd"]
        if market_data.get("social_sentiment"):
            context["social_sentiment"] = market_data["social_sentiment"]
        if market_data.get("whale_tracker"):
            context["whale_tracker"] = market_data["whale_tracker"]

        prompt = f"""Produce a strategic forecast for {symbol} on {exchange} from these signals (including OI, social, and whale data):

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
        if parsed.get("oi_divergence_signal"):
            signals.append({"type": "oi_divergence", "signal": parsed["oi_divergence_signal"]})

        return AgentOutput(
            agent_name=self.agent_key,
            exchange=exchange,
            timestamp=self._now(),
            summary=summary,
            signals=signals,
            confidence=confidence,
            raw_data={"context": context, "llm_response": parsed},
        )
