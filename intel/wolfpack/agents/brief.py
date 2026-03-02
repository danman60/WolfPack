"""The Brief — Decision synthesis, trade recommendations, portfolio management."""

from typing import Any

from wolfpack.agents.base import Agent, AgentOutput


class BriefAgent(Agent):
    @property
    def name(self) -> str:
        return "The Brief"

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

Output format:
- recommendations: [{asset, direction, conviction, entry, stop_loss, take_profit, size_pct, rationale}]
- portfolio_adjustments: suggested position changes
- risk_assessment: overall portfolio risk level
- signal_convergence: where agents agree/disagree
- priority_actions: what to do RIGHT NOW
- daily_narrative: 2-3 sentence market summary

Be decisive but honest about uncertainty. When agents conflict, explain why and default to caution.
Never recommend more than 50% portfolio exposure. Always include stop-losses."""

    async def analyze(self, market_data: dict[str, Any], exchange: str) -> AgentOutput:
        # Phase 1: Collect outputs from Quant, Snoop, Sage
        # Phase 2: LLM synthesis into actionable recommendations

        return AgentOutput(
            agent_name=self.name,
            exchange=exchange,
            timestamp=self._now(),
            summary="Decision synthesis pending agent integration",
            signals=[],
            confidence=0.0,
            raw_data=None,
        )
