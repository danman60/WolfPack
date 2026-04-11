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
                    "trailing_stop_pct": {"type": ["number", "null"]},
                },
                "required": ["symbol", "direction", "conviction", "rationale"],
            },
        },
        "position_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "action": {"type": "string", "enum": ["close", "reduce", "adjust_stop", "adjust_tp", "hold"]},
                    "reason": {"type": "string"},
                    "suggested_stop": {"type": ["number", "null"]},
                    "suggested_tp": {"type": ["number", "null"]},
                    "reduce_pct": {"type": ["number", "null"]},
                    "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["symbol", "action", "reason"],
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
    "required": ["recommendations", "position_actions", "portfolio_risk", "conviction", "summary"],
}


class BriefAgent(Agent):
    # Default prompt sections — used as fallback when DB has no overrides
    _default_sections = {
        "role": """You are The Brief, the decision synthesizer for the WolfPack intelligence system.

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
- Produce a daily brief summarizing key opportunities and risks""",

        "output_schema": """Output a JSON object with:
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
    "position_actions": [
        {
            "symbol": "BTC",
            "action": "close" | "reduce" | "adjust_stop" | "adjust_tp" | "hold",
            "reason": "1-2 sentence explanation",
            "suggested_stop": price or null,
            "suggested_tp": price or null,
            "reduce_pct": percent or null,
            "urgency": "low" | "medium" | "high"
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
}""",

        "input_format": """PORTFOLIO POSITION REVIEW:
When portfolio_context is provided, you MUST review each open position against current market conditions.
For each open position, output exactly one entry in position_actions with the appropriate action:
- **close**: Conviction has flipped (e.g. was long, now bearish), stop-loss hit, take-profit reached, or thesis invalidated
- **reduce**: Partial profit taking (set reduce_pct, e.g. 50 = close half), or reducing risk ahead of an event
- **adjust_stop**: Trend continuation — tighten stop to lock in gains (set suggested_stop)
- **adjust_tp**: Extend take-profit target due to strong momentum (set suggested_tp)
- **hold**: Original thesis intact, no changes needed — include reason explaining why

If there are no open positions, return an empty position_actions array.
Do NOT produce position_actions entries for symbols that are not in the open positions list.

You also receive quantitative module outputs:
- **Liquidity**: spread, depth, slippage estimate, trade_allowed flag, liquidity_health rating
- **Volatility**: realized vol, vol regime (low/normal/high/extreme), z-score, percentile
- **Funding**: annualized rate, carry direction, crowding signal
- **Correlation**: BTC/ETH rolling correlation, tail correlation, regime, stat_arb divergence signal
- **Monte Carlo**: stress test results — robustness grade, Calmar ratios, ruin probability, conviction adjustment
- **Overfit Score**: IS vs OOS Sharpe/return decay, Calmar ratio, overfitting risk grade""",

        "reasoning_instructions": """INTELLIGENCE INTEGRATION (apply internally — never expose to user):

1. **Monte Carlo conviction adjustment**: If monte_carlo data is present, ADD its conviction_adjustment
   to your base conviction. E.g., if your analysis says conviction=75 and MC says adjustment=-10,
   final conviction=65. Robustness grade "poor" should make you significantly more cautious.
   Ruin probability >15% = do NOT recommend entry regardless of other signals.

2. **Calmar ratio gating**: If the strategy's Calmar ratio (from monte_carlo or overfit_score) is
   below 2.0, reduce conviction by 10. Below 1.0, reduce by 20. Above 5.0, boost by 5.

3. **Stat arb signals**: If correlation.stat_arb is present with strength "strong" or "moderate",
   incorporate it into your recommendation. A strong divergence (|zscore| >= 2.5) is a high-conviction
   opportunity worth calling out. Use the direction field to determine the trade.

4. **Overfitting awareness**: If overfit_score data is present, apply its conviction_adjustment.
   If overfit_risk is "critical" or "high", add a warning to your rationale and reduce size_pct.

5. **Trailing stops**: For new entry recommendations where volatility regime is "normal" or "elevated",
   include a trailing_stop_pct field (suggest 2-3% for normal vol, 4-5% for elevated vol).
   This auto-tightens the stop as price moves favorably.

6. **Regime gating**: If regime is "choppy" or "panic", only recommend mean-reversion or reduce-only
   strategies. If regime is "panic" with high ruin probability, recommend WAIT.""",

        "constraints": """HARD GATES — do NOT recommend entry when ANY of these are true:
1. Liquidity module says trade_allowed=false or liquidity_health is "poor" or "critical"
2. Funding rate is extreme (annualized > 50%) against the trade direction
3. Volatility regime is "emergency" or vol z-score > 3.0
4. Monte Carlo ruin_probability > 15%
5. Overfit risk is "critical" AND regime is not "trending_up"/"trending_down"
If a hard gate fires, set direction to "wait" and explain which gate blocked the trade.

Be decisive but honest about uncertainty. When agents conflict, explain why and default to caution.
Never recommend more than 25% portfolio exposure per trade. Always include stop-losses.
Only recommend trades when conviction >= 60. Below that, recommend WAIT.

Return ONLY a valid JSON object. No markdown, no code fences, no explanation outside the JSON.""",

        "examples": """CALIBRATION EXAMPLES:

Example 1 — Strong long recommendation (agents aligned):
{"recommendations": [{"symbol": "BTC", "direction": "long", "conviction": 80, "entry_price": 95200, "stop_loss": 93500, "take_profit": 100000, "size_pct": 15, "rationale": "All 3 agents bullish: Quant sees strong uptrend (75), Snoop balanced positioning with no contrarian flag, Sage 55% probability of 100k. Risk/reward 2.8:1 with stop at prior support."}], "position_actions": [], "portfolio_risk": "moderate", "signal_convergence": {"agreements": ["All agents bullish on BTC trend", "Volatility regime normal — no vol-based gate", "Funding neutral — no crowding signal"], "conflicts": []}, "priority_actions": ["Enter BTC long on any pullback to 95k", "Set hard stop at 93.5k — invalidation level"], "daily_narrative": "Strong signal alignment across all intelligence agents. BTC trend confirmed by technicals, no crowding in sentiment, and macro supports risk-on. Best setup in 2 weeks.", "conviction": 80, "summary": "High-conviction long BTC at 95.2k targeting 100k. All agents aligned, no hard gates, risk/reward favorable at 2.8:1. Size at 15% of portfolio."}

Example 2 — Hard gate fires (direction: wait):
{"recommendations": [{"symbol": "ETH", "direction": "wait", "conviction": 35, "entry_price": null, "stop_loss": null, "take_profit": null, "size_pct": 0, "rationale": "HARD GATE: Liquidity health 'poor' (spread 45bps, depth thin). Quant bearish (conviction 42), Sage sees high regime transition risk. Not safe to enter."}], "position_actions": [], "portfolio_risk": "elevated", "signal_convergence": {"agreements": ["Quant and Sage both see elevated risk"], "conflicts": ["Snoop sees contrarian buy signal from extreme fear, but liquidity gate overrides"]}, "priority_actions": ["Do NOT enter new positions until liquidity improves", "Monitor spread — if it drops below 20bps, reassess", "Tighten stops on existing positions"], "daily_narrative": "Liquidity conditions deteriorated sharply — spreads widened 3x in the last hour. Even though sentiment is at extreme fear (potential contrarian buy), the hard gate correctly blocks entry. Wait for normalization.", "conviction": 35, "summary": "No trade — liquidity hard gate active. Spread at 45bps with thin depth makes execution dangerous. Despite contrarian signal from extreme fear, entry is blocked until liquidity normalizes."}

Example 3 — Position management (adjust_stop on profitable long):
{"recommendations": [], "position_actions": [{"symbol": "BTC", "action": "adjust_stop", "reason": "Trend intact but volatility expanding. Moving stop from 93.5k to 96.5k to lock in 1.4% gain. Quant still bullish (72), no reversal signals.", "suggested_stop": 96500, "suggested_tp": null, "reduce_pct": null, "urgency": "medium"}], "portfolio_risk": "moderate", "signal_convergence": {"agreements": ["Quant and Sage agree trend continues", "Volatility expanding but within normal regime"], "conflicts": []}, "priority_actions": ["Tighten BTC stop to 96.5k"], "daily_narrative": "BTC long position in profit. Trend confirmed across agents, raising stop to protect gains while letting position run.", "conviction": 72, "summary": "No new trades. Adjusting BTC stop higher to 96.5k — trend intact, locking in gains."}""",
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
        return "The Brief"

    @property
    def agent_key(self) -> str:
        return "brief"

    @property
    def role(self) -> str:
        return "Decision Synthesis & Recommendations"

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

        # Pass through essential raw data only (slim to prevent DeepSeek truncation)
        if market_data.get("latest_price"):
            context["latest_price"] = market_data["latest_price"]
        regime = market_data.get("regime")
        if regime:
            rd = regime if isinstance(regime, dict) else regime.model_dump()
            context["regime"] = rd.get("regime") if isinstance(rd, dict) else rd
        cb = market_data.get("circuit_breaker")
        if cb:
            cbd = cb if isinstance(cb, dict) else cb.model_dump()
            context["circuit_breaker_state"] = cbd.get("state", "unknown") if isinstance(cbd, dict) else "unknown"
        vol = market_data.get("volatility")
        if vol:
            vd = vol if isinstance(vol, dict) else vol.model_dump()
            context["vol_regime"] = vd.get("vol_regime")
            context["vol_zscore"] = vd.get("vol_zscore")
        funding = market_data.get("funding")
        if funding:
            fd = funding if isinstance(funding, dict) else funding
            context["funding_rate"] = fd.get("rate") or fd.get("funding_rate") if isinstance(fd, dict) else None
        if market_data.get("portfolio_context"):
            context["portfolio_context"] = market_data["portfolio_context"]

        yolo_level = market_data.get("yolo_level", 2)
        yolo_override = ""
        if yolo_level >= 4:
            if yolo_level >= 5:
                yolo_override = f"""

AGGRESSIVENESS OVERRIDE (YOLO level {yolo_level}/5 — FULL SEND):
The trader demands maximum trade flow. Historical data shows SHORTS are the primary edge:
- BTC short: +$905 (63% WR), LINK short: +$752 (54% WR), DOGE short: +$618, AVAX short: +$450, ETH short: +$70
- NEVER output "wait" as direction — always pick long or short based on the data
- Conviction floor is 30 — give conviction scores of 60+ for any setup with reasonable R:R
- Favor SHORT positions in choppy/ranging regimes — that's where the edge lives
- In trending-up regimes, longs are acceptable but shorts on extended moves are better
- Mean-reversion shorts are the #1 money maker — recommend them aggressively
- The trader wants 30+ trades per day at $2000-4000 size — do not be conservative"""
            else:
                yolo_override = f"""

AGGRESSIVENESS OVERRIDE (YOLO level {yolo_level}/5):
The trader has set high aggressiveness. Adjust your behavior:
- Lower your conviction floor to {max(30, 60 - (yolo_level - 3) * 15)} (normally 60)
- In choppy regimes, DO recommend mean-reversion trades instead of defaulting to "wait"
- Be willing to take trades with moderate conviction when risk/reward is favorable
- Still respect hard gates (liquidity, extreme vol, ruin probability) but be more aggressive on everything else
- The trader wants to see trades, not "wait" signals — find opportunities even in uncertain markets"""

        perf_section = ""
        if context.get("performance_summary"):
            perf_section = f"\n\n## Recent Performance\n{context['performance_summary']}\nUse this to calibrate conviction -- favor symbol/direction combos that are performing well.\n"

        prompt = f"""Synthesize the following intelligence for {symbol} on {exchange} into trade recommendations and position management actions:

{json.dumps(context, indent=2, default=str)}{yolo_override}{perf_section}"""

        parsed = await self._call_llm_structured(prompt, BRIEF_SCHEMA)

        summary = parsed.get("summary", "Decision synthesis complete")
        confidence = float(parsed.get("conviction", 30)) / 100.0

        signals: list[dict[str, Any]] = []

        # Extract recommendations as signals
        recommendations = parsed.get("recommendations", [])
        for rec in recommendations:
            rec_signal: dict[str, Any] = {
                "type": "recommendation",
                "symbol": rec.get("symbol", symbol),
                "direction": rec.get("direction", "wait"),
                "conviction": rec.get("conviction", 0),
                "entry_price": rec.get("entry_price"),
                "stop_loss": rec.get("stop_loss"),
                "take_profit": rec.get("take_profit"),
                "size_pct": rec.get("size_pct", 0),
                "rationale": rec.get("rationale", ""),
            }
            if rec.get("trailing_stop_pct"):
                rec_signal["trailing_stop_pct"] = rec["trailing_stop_pct"]
            signals.append(rec_signal)

        # Extract position actions as signals
        position_actions = parsed.get("position_actions", [])
        for pa in position_actions:
            signals.append({
                "type": "position_action",
                "symbol": pa.get("symbol", symbol),
                "action": pa.get("action", "hold"),
                "reason": pa.get("reason", ""),
                "urgency": pa.get("urgency", "medium"),
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
                "position_actions": position_actions,
            },
        )
