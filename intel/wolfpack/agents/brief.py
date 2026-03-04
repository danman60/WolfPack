"""The Brief — Decision synthesis, trade recommendations, portfolio management.

Consumes outputs from Quant, Snoop, and Sage agents to produce
actionable trade recommendations with entry/exit levels and sizing.
"""

import json
import logging
from typing import Any

from wolfpack.agents.base import Agent, AgentOutput

logger = logging.getLogger(__name__)

BRIEF_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "direction": {"type": "string", "enum": ["long", "short", "wait"]},
                    "conviction": {"type": "number", "minimum": 0, "maximum": 100},
                    "entry_price": {"type": ["number", "null"]},
                    "stop_loss": {"type": ["number", "null"]},
                    "take_profit": {"type": ["number", "null"]},
                    "size_pct": {"type": "number", "minimum": 1, "maximum": 25},
                    "rationale": {"type": "string"},
                },
                "required": ["symbol", "direction", "conviction", "rationale"],
            },
        },
        "portfolio_risk": {"type": "string", "enum": ["low", "moderate", "elevated", "extreme"]},
        "signal_convergence": {
            "type": "object",
            "properties": {
                "agreements": {"type": "array", "items": {"type": "string"}},
                "conflicts": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["agreements", "conflicts"],
        },
        "priority_actions": {"type": "array", "items": {"type": "string"}},
        "daily_narrative": {"type": "string"},
        "conviction": {"type": "number", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
    },
    "required": ["recommendations", "portfolio_risk", "conviction", "summary"],
}


class BriefAgent(Agent):
    @property
    def name(self) -> str:
        return "The Brief"

    @property
    def agent_key(self) -> str:
        return "brief"

    @property
    def role(self) -> str:
        return "Decision Synthesis & Recommendations"

    @property
    def system_prompt(self) -> str:
        return """You are The Brief, the decision synthesizer for the WolfPack intelligence system.

You receive analysis from three other agents:
- The Quant (technical analysis, regime detection)
- The Snoop (social sentiment, narrative tracking)
- The Sage (forecasting, macro outlook)

Your role:
- Synthesize all intelligence into actionable trade recommendations
- Assign conviction scores (0-100) based on signal convergence
- Generate specific trade ideas with entry, stop-loss, take-profit levels
- Manage portfolio-level risk: position sizing, exposure limits, correlation risk
- Flag conflicting signals between agents
- Produce a daily brief summarizing key opportunities and risks

Output a JSON object with:
{
    "recommendations": [
        {
            "symbol": "BTC",
            "direction": "long" | "short",
            "conviction": 0-100,
            "entry_price": price or null,
            "stop_loss": price or null,
            "take_profit": price or null,
            "size_pct": 1-25,
            "rationale": "1-2 sentence rationale"
        }
    ],
    "portfolio_risk": "low" | "moderate" | "elevated" | "extreme",
    "signal_convergence": {
        "agreements": ["where agents agree"],
        "conflicts": ["where agents disagree"]
    },
    "priority_actions": ["immediate action items"],
    "daily_narrative": "2-3 sentence market summary",
    "conviction": 0-100,
    "summary": "2-3 sentence actionable summary"
}

You also receive quantitative module outputs:
- **Liquidity**: spread, depth, slippage estimate, trade_allowed flag, liquidity_health rating
- **Volatility**: realized vol, vol regime (low/normal/high/extreme), z-score, percentile
- **Funding**: annualized rate, carry direction, crowding signal
- **Correlation**: BTC/ETH rolling correlation, tail correlation, regime

HARD GATES — do NOT recommend entry when ANY of these are true:
1. Liquidity module says trade_allowed=false or liquidity_health is "poor" or "critical"
2. Funding rate is extreme (annualized > 50%) against the trade direction
3. Volatility regime is "emergency" or vol z-score > 3.0
If a hard gate fires, set direction to "wait" and explain which gate blocked the trade.

Be decisive but honest about uncertainty. When agents conflict, explain why and default to caution.
Never recommend more than 25% portfolio exposure per trade. Always include stop-losses.
Only recommend trades when conviction >= 60. Below that, recommend WAIT.

CALIBRATION EXAMPLES:

Example 1 — Strong long recommendation (agents aligned):
{"recommendations": [{"symbol": "BTC", "direction": "long", "conviction": 80, "entry_price": 95200, "stop_loss": 93500, "take_profit": 100000, "size_pct": 15, "rationale": "All 3 agents bullish: Quant sees strong uptrend (75), Snoop balanced positioning with no contrarian flag, Sage 55% probability of 100k. Risk/reward 2.8:1 with stop at prior support."}], "portfolio_risk": "moderate", "signal_convergence": {"agreements": ["All agents bullish on BTC trend", "Volatility regime normal — no vol-based gate", "Funding neutral — no crowding signal"], "conflicts": []}, "priority_actions": ["Enter BTC long on any pullback to 95k", "Set hard stop at 93.5k — invalidation level"], "daily_narrative": "Strong signal alignment across all intelligence agents. BTC trend confirmed by technicals, no crowding in sentiment, and macro supports risk-on. Best setup in 2 weeks.", "conviction": 80, "summary": "High-conviction long BTC at 95.2k targeting 100k. All agents aligned, no hard gates, risk/reward favorable at 2.8:1. Size at 15% of portfolio."}

Example 2 — Hard gate fires (direction: wait):
{"recommendations": [{"symbol": "ETH", "direction": "wait", "conviction": 35, "entry_price": null, "stop_loss": null, "take_profit": null, "size_pct": 0, "rationale": "HARD GATE: Liquidity health 'poor' (spread 45bps, depth thin). Quant bearish (conviction 42), Sage sees high regime transition risk. Not safe to enter."}], "portfolio_risk": "elevated", "signal_convergence": {"agreements": ["Quant and Sage both see elevated risk"], "conflicts": ["Snoop sees contrarian buy signal from extreme fear, but liquidity gate overrides"]}, "priority_actions": ["Do NOT enter new positions until liquidity improves", "Monitor spread — if it drops below 20bps, reassess", "Tighten stops on existing positions"], "daily_narrative": "Liquidity conditions deteriorated sharply — spreads widened 3x in the last hour. Even though sentiment is at extreme fear (potential contrarian buy), the hard gate correctly blocks entry. Wait for normalization.", "conviction": 35, "summary": "No trade — liquidity hard gate active. Spread at 45bps with thin depth makes execution dangerous. Despite contrarian signal from extreme fear, entry is blocked until liquidity normalizes."}

Return ONLY a valid JSON object. No markdown, no code fences, no explanation outside the JSON."""

    async def analyze(self, market_data: dict[str, Any], exchange: str) -> AgentOutput:
        symbol = market_data.get("symbol", "BTC")

        # Collect agent outputs
        context: dict[str, Any] = {
            "symbol": symbol,
            "exchange": exchange,
        }

        if market_data.get("quant_output"):
            qo = market_data["quant_output"]
            context["quant_analysis"] = {
                "summary": qo.get("summary") if isinstance(qo, dict) else qo.summary,
                "signals": qo.get("signals") if isinstance(qo, dict) else qo.signals,
                "confidence": qo.get("confidence") if isinstance(qo, dict) else qo.confidence,
            }

        if market_data.get("snoop_output"):
            so = market_data["snoop_output"]
            context["snoop_analysis"] = {
                "summary": so.get("summary") if isinstance(so, dict) else so.summary,
                "signals": so.get("signals") if isinstance(so, dict) else so.signals,
                "confidence": so.get("confidence") if isinstance(so, dict) else so.confidence,
            }

        if market_data.get("sage_output"):
            sgo = market_data["sage_output"]
            context["sage_analysis"] = {
                "summary": sgo.get("summary") if isinstance(sgo, dict) else sgo.summary,
                "signals": sgo.get("signals") if isinstance(sgo, dict) else sgo.signals,
                "confidence": sgo.get("confidence") if isinstance(sgo, dict) else sgo.confidence,
            }

        # Pass through raw data for context
        if market_data.get("latest_price"):
            context["latest_price"] = market_data["latest_price"]
        if market_data.get("regime"):
            regime = market_data["regime"]
            context["regime"] = regime if isinstance(regime, dict) else regime.model_dump()
        if market_data.get("circuit_breaker"):
            context["circuit_breaker"] = market_data["circuit_breaker"]
        if market_data.get("liquidity"):
            liq = market_data["liquidity"]
            context["liquidity"] = liq if isinstance(liq, dict) else liq.model_dump()
        if market_data.get("volatility"):
            vol = market_data["volatility"]
            context["volatility"] = vol if isinstance(vol, dict) else vol.model_dump()
        if market_data.get("funding"):
            funding = market_data["funding"]
            context["funding"] = funding if isinstance(funding, dict) else funding
        if market_data.get("correlation"):
            corr = market_data["correlation"]
            context["correlation"] = corr if isinstance(corr, dict) else corr

        prompt = f"""Synthesize the following intelligence for {symbol} on {exchange} into trade recommendations:

{json.dumps(context, indent=2, default=str)}"""

        parsed = await self._call_llm_structured(prompt, BRIEF_SCHEMA)

        summary = parsed.get("summary", "Decision synthesis complete")
        confidence = float(parsed.get("conviction", 30)) / 100.0

        signals: list[dict[str, Any]] = []

        # Extract recommendations as signals
        recommendations = parsed.get("recommendations", [])
        for rec in recommendations:
            signals.append({
                "type": "recommendation",
                "symbol": rec.get("symbol", symbol),
                "direction": rec.get("direction", "wait"),
                "conviction": rec.get("conviction", 0),
                "entry_price": rec.get("entry_price"),
                "stop_loss": rec.get("stop_loss"),
                "take_profit": rec.get("take_profit"),
                "size_pct": rec.get("size_pct", 0),
                "rationale": rec.get("rationale", ""),
            })

        if parsed.get("portfolio_risk"):
            signals.append({"type": "portfolio_risk", "level": parsed["portfolio_risk"]})

        if parsed.get("signal_convergence"):
            signals.append({"type": "convergence", **parsed["signal_convergence"]})

        for action in parsed.get("priority_actions", []):
            signals.append({"type": "priority_action", "description": action})

        return AgentOutput(
            agent_name=self.agent_key,
            exchange=exchange,
            timestamp=self._now(),
            summary=summary,
            signals=signals,
            confidence=confidence,
            raw_data={
                "context": context,
                "llm_response": parsed,
                "recommendations": recommendations,
            },
        )
