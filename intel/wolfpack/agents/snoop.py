"""The Snoop — Social sentiment, news analysis, narrative tracking.

Analyzes market data + funding/regime context to infer social sentiment
and narrative direction. Full social API integration (Twitter, Reddit) is Phase 2+.
"""

import json
import logging
from typing import Any

from wolfpack.agents.base import Agent, AgentOutput

logger = logging.getLogger(__name__)


class SnoopAgent(Agent):
    @property
    def name(self) -> str:
        return "The Snoop"

    @property
    def agent_key(self) -> str:
        return "snoop"

    @property
    def role(self) -> str:
        return "Social Intelligence & Sentiment"

    @property
    def system_prompt(self) -> str:
        return """You are The Snoop, a social intelligence analyst for the WolfPack system.

Your role:
- Infer crypto market sentiment from price action, funding rates, and volume patterns
- Identify when crowd positioning is extreme (funding rates, OI changes)
- Detect narrative shifts from regime changes (panic, breakout, grinding)
- Flag contrarian opportunities where positioning diverges from technicals
- Estimate social volume intensity from volume + volatility patterns

You receive quantitative data (not direct social feeds yet). Use it to INFER sentiment.

Output a JSON object with:
{
    "sentiment_score": -100 to 100,
    "narrative": "dominant narrative description",
    "narrative_momentum": "accelerating" | "peaking" | "fading" | "dormant",
    "crowd_positioning": "crowded_long" | "crowded_short" | "balanced",
    "contrarian_signal": true/false,
    "notable_observations": ["observation 1", ...],
    "risk_flags": ["flag 1", ...],
    "conviction": 0-100,
    "summary": "2-3 sentence sentiment summary"
}

Be skeptical of hype. Distinguish signal from noise."""

    async def analyze(self, market_data: dict[str, Any], exchange: str) -> AgentOutput:
        symbol = market_data.get("symbol", "BTC")

        # Build context from available data
        context: dict[str, Any] = {
            "symbol": symbol,
            "exchange": exchange,
        }

        if market_data.get("regime"):
            regime = market_data["regime"]
            context["regime"] = regime if isinstance(regime, dict) else regime.model_dump()
        if market_data.get("funding"):
            funding = market_data["funding"]
            context["funding"] = funding if isinstance(funding, dict) else funding.model_dump()
        if market_data.get("volatility"):
            vol = market_data["volatility"]
            context["volatility"] = vol if isinstance(vol, dict) else vol.model_dump()
        if market_data.get("liquidity"):
            liq = market_data["liquidity"]
            context["liquidity"] = liq if isinstance(liq, dict) else liq.model_dump()

        prompt = f"""Infer social sentiment for {symbol} on {exchange} from these quantitative signals:

{json.dumps(context, indent=2, default=str)}

Respond with ONLY a JSON object matching the format specified in your system prompt."""

        llm_response = await self._call_llm(prompt)
        parsed = self._parse_llm_json(llm_response)

        summary = parsed.get("summary", "Sentiment analysis complete")
        confidence = float(parsed.get("conviction", 40)) / 100.0

        signals: list[dict[str, Any]] = []
        if parsed.get("sentiment_score") is not None:
            signals.append({"type": "sentiment", "score": parsed["sentiment_score"]})
        if parsed.get("crowd_positioning"):
            signals.append({"type": "positioning", "state": parsed["crowd_positioning"]})
        if parsed.get("narrative_momentum"):
            signals.append({"type": "narrative", "momentum": parsed["narrative_momentum"], "narrative": parsed.get("narrative", "")})
        if parsed.get("contrarian_signal"):
            signals.append({"type": "contrarian", "active": True})
        for flag in parsed.get("risk_flags", []):
            signals.append({"type": "risk_flag", "description": flag})

        return AgentOutput(
            agent_name=self.agent_key,
            exchange=exchange,
            timestamp=self._now(),
            summary=summary,
            signals=signals,
            confidence=confidence,
            raw_data={"context": context, "llm_response": llm_response},
        )
