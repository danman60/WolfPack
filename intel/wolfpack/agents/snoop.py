"""The Snoop — Social sentiment, news analysis, narrative tracking.

Analyzes market data + funding/regime context to infer social sentiment
and narrative direction. Full social API integration (Twitter, Reddit) is Phase 2+.
"""

import json
import logging
from typing import Any

from wolfpack.agents.base import Agent, AgentOutput

logger = logging.getLogger(__name__)

SNOOP_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "sentiment_score": {"type": "number", "minimum": -100, "maximum": 100},
        "narrative": {"type": "string"},
        "narrative_momentum": {"type": "string", "enum": ["accelerating", "peaking", "fading", "dormant"]},
        "crowd_positioning": {"type": "string", "enum": ["crowded_long", "crowded_short", "balanced"]},
        "contrarian_signal": {"type": "boolean"},
        "whale_activity": {"type": "string"},
        "social_data_quality": {"type": "string", "enum": ["strong", "moderate", "weak"]},
        "notable_observations": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "conviction": {"type": "number", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
    },
    "required": ["sentiment_score", "crowd_positioning", "conviction", "summary"],
}


class SnoopAgent(Agent):
    # Default prompt sections — used as fallback when DB has no overrides
    _default_sections = {
        "role": """You are The Snoop, a social intelligence analyst for the WolfPack system.

Your role:
- Analyze crypto market sentiment from quant signals, social data, and whale activity
- Use the Fear & Greed Index to gauge broad market mood (extreme values are contrarian signals)
- Check if the symbol is trending on CoinGecko (high social attention = potential volatility)
- Analyze whale trading patterns — net whale direction and volume indicate smart money positioning
- Identify when crowd positioning is extreme (funding rates, OI changes, whale flows)
- Detect narrative shifts from regime changes (panic, breakout, grinding)
- Flag contrarian opportunities where positioning diverges from technicals

You receive both quantitative module data AND social/whale intelligence feeds.""",

        "output_schema": """Output a JSON object with:
{
    "sentiment_score": -100 to 100,
    "narrative": "dominant narrative description",
    "narrative_momentum": "accelerating" | "peaking" | "fading" | "dormant",
    "crowd_positioning": "crowded_long" | "crowded_short" | "balanced",
    "contrarian_signal": true/false,
    "whale_activity": "brief summary of whale behavior and what it implies",
    "social_data_quality": "strong" | "moderate" | "weak" (based on data availability),
    "notable_observations": ["observation 1", ...],
    "risk_flags": ["flag 1", ...],
    "conviction": 0-100,
    "summary": "2-3 sentence sentiment summary"
}""",

        "constraints": """Be skeptical of hype. Distinguish signal from noise. Whale data > social hype.

Return ONLY a valid JSON object. No markdown, no code fences, no explanation outside the JSON.""",

        "examples": """CALIBRATION EXAMPLES:

Example 1 — Crowded long with contrarian signal:
{"sentiment_score": 72, "narrative": "Euphoric retail longs piling in after breakout, funding rate elevated. Whales net short $8.2M in last 4h — smart money diverging from crowd.", "narrative_momentum": "peaking", "crowd_positioning": "crowded_long", "contrarian_signal": true, "whale_activity": "Large sells ($100k+) outpacing buys 3:1 in last 4 hours, suggesting distribution by whales into retail strength.", "social_data_quality": "strong", "notable_observations": ["Fear & Greed at 78 (Extreme Greed) — historically precedes 5-15% pullbacks", "Symbol trending #2 on CoinGecko — maximum social attention"], "risk_flags": ["Extreme funding rate suggests overleveraged longs vulnerable to liquidation cascade", "Whale-retail divergence is a high-probability mean reversion setup"], "conviction": 68, "summary": "Crowded long positioning with whale distribution pattern. Contrarian signal active — smart money is fading the retail euphoria. High probability of a flush to reset funding."}

Example 2 — Balanced with weak social data:
{"sentiment_score": 5, "narrative": "Quiet market with no dominant narrative. Social volume low, no trending topics. Whales inactive — small trades only.", "narrative_momentum": "dormant", "crowd_positioning": "balanced", "contrarian_signal": false, "whale_activity": "Minimal whale activity — no trades above $100k threshold in last 6 hours.", "social_data_quality": "weak", "notable_observations": ["Fear & Greed at 48 (Neutral) — no extreme to trade against"], "risk_flags": ["Low social data quality reduces confidence in any sentiment read"], "conviction": 30, "summary": "No actionable sentiment signal. Market in a low-attention phase with balanced positioning. Social data too thin to derive meaningful edge — defer to technical and macro signals."}""",
    }

    def __init__(self):
        super().__init__()
        self._register_prompt_defaults()

    def _register_prompt_defaults(self):
        """Register default prompt sections with the global PromptBuilder."""
        from wolfpack.prompt_builder import get_prompt_builder
        pb = get_prompt_builder()
        if pb:
            pb.register_defaults(self.agent_key, self._default_sections)

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
        from wolfpack.prompt_builder import get_prompt_builder
        pb = get_prompt_builder()
        if pb:
            return pb.build_system_prompt(self.agent_key)
        # Fallback: assemble from hardcoded defaults
        return "\n\n".join(s.strip() for s in self._default_sections.values())

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
        if market_data.get("social_sentiment"):
            context["social_sentiment"] = market_data["social_sentiment"]
        if market_data.get("whale_tracker"):
            context["whale_tracker"] = market_data["whale_tracker"]
        if market_data.get("open_interest_usd"):
            context["open_interest_usd"] = market_data["open_interest_usd"]

        prompt = f"""Analyze social sentiment for {symbol} on {exchange} from these signals:

{json.dumps(context, indent=2, default=str)}"""

        parsed = await self._call_llm_structured(prompt, SNOOP_SCHEMA)

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
        if parsed.get("whale_activity"):
            signals.append({"type": "whale_activity", "summary": parsed["whale_activity"]})
        if parsed.get("social_data_quality"):
            signals.append({"type": "social_quality", "level": parsed["social_data_quality"]})
        for flag in parsed.get("risk_flags", []):
            signals.append({"type": "risk_flag", "description": flag})

        return AgentOutput(
            agent_name=self.agent_key,
            exchange=exchange,
            timestamp=self._now(),
            summary=summary,
            signals=signals,
            confidence=confidence,
            raw_data={"context": context, "llm_response": parsed},
        )
