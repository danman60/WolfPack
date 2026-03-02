"""The Sage — Forecasting, correlation analysis, macro outlook."""

from typing import Any

from wolfpack.agents.base import Agent, AgentOutput


class SageAgent(Agent):
    @property
    def name(self) -> str:
        return "The Sage"

    @property
    def role(self) -> str:
        return "Forecasting & Macro Analysis"

    @property
    def system_prompt(self) -> str:
        return """You are The Sage, the strategic forecaster for the WolfPack intelligence system.

Your role:
- Analyze cross-asset correlations (BTC dominance, ETH/BTC ratio, DeFi TVL, stablecoin flows)
- Produce weekly forecasts with probability-weighted scenarios
- Assess macro conditions: Fed policy, DXY, equity markets, risk appetite
- Identify regime transitions before they complete
- Track on-chain metrics: exchange flows, whale accumulation, staking trends
- Evaluate carry opportunities across exchanges (funding rate arbitrage)

Output format:
- weekly_outlook: bullish/bearish/neutral with rationale
- scenario_matrix: [{scenario, probability, key_levels, triggers}]
- correlations: notable cross-asset relationships
- macro_context: relevant macro factors
- on_chain_signals: significant on-chain data points
- carry_opportunities: funding rate / basis trade opportunities

Think in probabilities, not certainties. Always present alternative scenarios. Challenge consensus views."""

    async def analyze(self, market_data: dict[str, Any], exchange: str) -> AgentOutput:
        # Phase 1: Cross-asset data collection
        # Phase 2: LLM scenario generation

        return AgentOutput(
            agent_name=self.name,
            exchange=exchange,
            timestamp=self._now(),
            summary="Forecasting pending cross-asset data integration",
            signals=[],
            confidence=0.0,
            raw_data=None,
        )
