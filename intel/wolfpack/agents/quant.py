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
    # Default prompt sections — used as fallback when DB has no overrides
    _default_sections = {
        "role": """You are The Quant, a quantitative trading analyst for the WolfPack intelligence system.

Your role:
- Analyze price action, volume profiles, and technical indicators
- Detect market regimes (trending, mean-reverting, volatile, quiet)
- Identify chart patterns and key support/resistance levels
- Assess volatility regimes and risk-adjusted opportunity scores""",

        "constraints": """You receive pre-computed quantitative signals from the modules. Your job is to INTERPRET them,
identify what matters, and produce a clear summary with actionable insights.

Be precise with numbers. Qualify uncertainty. Never fabricate data that wasn't provided to you.

Return ONLY a valid JSON object. No markdown, no code fences, no explanation outside the JSON.""",

        "output_schema": """Output a JSON object with:
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
}""",

        "examples": """CALIBRATION EXAMPLES:

Example 1 — Bullish trending regime:
{"regime_assessment": "Strong uptrend with rising SMA_20 above SMA_50, RSI at 62 — healthy momentum without overextension.", "trend_direction": "bullish", "trend_strength": 72, "key_levels": {"support": [94500, 92800], "resistance": [98200, 100000]}, "risk_level": "moderate", "opportunities": ["Trend continuation long above 95k with tight stop at 94.5k", "Breakout entry if 98.2k resistance clears on volume"], "warnings": ["RSI approaching overbought territory — watch for divergence above 70"], "conviction": 75, "summary": "BTC in a healthy uptrend with room to run. Momentum indicators confirm trend without extreme readings. Key resistance at 98.2k is the next decision point."}

Example 2 — Choppy uncertain regime:
{"regime_assessment": "Range-bound between 89k-93k for 48h. SMA_20 flat, RSI oscillating 45-55. No clear directional bias.", "trend_direction": "neutral", "trend_strength": 25, "key_levels": {"support": [89000, 87500], "resistance": [93000, 95000]}, "risk_level": "moderate", "opportunities": ["Mean reversion plays within the 89k-93k range"], "warnings": ["Compression often precedes expansion — a breakout in either direction is likely within 24-48h", "Volume declining — lack of conviction from both bulls and bears"], "conviction": 40, "summary": "Market in consolidation with no edge. Low conviction on any directional bet. Wait for a breakout above 93k or breakdown below 89k before committing capital."}""",
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
        return "The Quant"

    @property
    def agent_key(self) -> str:
        return "quant"

    @property
    def role(self) -> str:
        return "Technical Analysis & Regime Detection"

    @property
    def model_override(self) -> str | None:
        _api_key, _base_url, _chat, reasoner = self._get_deepseek_client_config()
        return reasoner

    @property
    def system_prompt(self) -> str:
        from wolfpack.prompt_builder import get_prompt_builder
        pb = get_prompt_builder()
        if pb:
            return pb.build_system_prompt(self.agent_key)
        # Fallback: assemble from hardcoded defaults
        return "\n\n".join(s.strip() for s in self._default_sections.values())

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

        # Correlation + stat arb data
        correlation_output = market_data.get("correlation")
        if correlation_output:
            corr_data = correlation_output if isinstance(correlation_output, dict) else correlation_output.model_dump()
            context["correlation"] = corr_data
            # Highlight stat arb signal if present
            stat_arb = corr_data.get("stat_arb")
            if stat_arb and stat_arb.get("strength") in ("strong", "moderate"):
                context["stat_arb_alert"] = stat_arb

        # Get latest price info
        if candles_raw:
            last = candles_raw[-1]
            if isinstance(last, Candle):
                context["latest_price"] = last.close
                context["latest_volume"] = last.volume
            elif isinstance(last, dict):
                context["latest_price"] = last.get("close", 0)
                context["latest_volume"] = last.get("volume", 0)

        # Trim context to essential data — large prompts cause DeepSeek truncation
        slim_context = _slim_context(context)

        # Call LLM with structured output
        prompt = f"""Analyze the following quantitative signals for {symbol} on {exchange}:

{json.dumps(slim_context, indent=2, default=str)}"""

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
        volumes: list[float] = []
        for c in candles:
            if isinstance(c, Candle):
                closes.append(c.close)
                volumes.append(c.volume)
            elif isinstance(c, dict):
                closes.append(float(c.get("close", 0)))
                volumes.append(float(c.get("volume", 0)))

        signals: list[dict[str, Any]] = []

        if len(closes) >= 20:
            sma_20 = sum(closes[-20:]) / 20
            signals.append({"indicator": "SMA_20", "value": round(sma_20, 2)})

        if len(closes) >= 50:
            sma_50 = sum(closes[-50:]) / 50
            signals.append({"indicator": "SMA_50", "value": round(sma_50, 2)})

        # 9 EMA — fast trend filter (price extended above = risky entry)
        if len(closes) >= 9:
            ema_9 = self._ema(closes, 9)
            signals.append({"indicator": "EMA_9", "value": round(ema_9, 2)})
            if closes[-1] != 0:
                ema_9_dist_pct = ((closes[-1] - ema_9) / ema_9) * 100
                signals.append({"indicator": "EMA_9_dist_pct", "value": round(ema_9_dist_pct, 2)})
                # Flag extended price: >3% above 9 EMA = overextended long, <-3% = overextended short
                if abs(ema_9_dist_pct) > 3:
                    direction = "above" if ema_9_dist_pct > 0 else "below"
                    signals.append({
                        "type": "risk",
                        "level": "elevated",
                        "indicator": "EMA_9_extension",
                        "detail": f"Price {abs(ema_9_dist_pct):.1f}% {direction} 9 EMA — overextended, wait for pullback",
                    })

        # VWAP — volume-weighted average price (session anchor)
        if len(closes) >= 10 and len(volumes) >= 10:
            vwap = self._vwap(closes, volumes)
            signals.append({"indicator": "VWAP", "value": round(vwap, 2)})
            if vwap > 0:
                vwap_dist_pct = ((closes[-1] - vwap) / vwap) * 100
                signals.append({"indicator": "VWAP_dist_pct", "value": round(vwap_dist_pct, 2)})
                # Flag >10% above VWAP = extreme extension
                if abs(vwap_dist_pct) > 10:
                    direction = "above" if vwap_dist_pct > 0 else "below"
                    signals.append({
                        "type": "risk",
                        "level": "high",
                        "indicator": "VWAP_extension",
                        "detail": f"Price {abs(vwap_dist_pct):.1f}% {direction} VWAP — extreme extension, high reversion risk",
                    })

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
    def _ema(closes: list[float], period: int) -> float:
        """Exponential moving average."""
        if len(closes) < period:
            return closes[-1] if closes else 0.0
        multiplier = 2 / (period + 1)
        ema = sum(closes[:period]) / period  # Seed with SMA
        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    @staticmethod
    def _vwap(closes: list[float], volumes: list[float]) -> float:
        """Volume-weighted average price over the available candles."""
        total_vol = sum(volumes)
        if total_vol == 0:
            return closes[-1] if closes else 0.0
        return sum(c * v for c, v in zip(closes, volumes)) / total_vol

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


def _slim_context(ctx: dict) -> dict:
    """Trim context to essential fields — prevents DeepSeek response truncation.

    Full module outputs can be 3000+ tokens. LLM only needs the key numbers.
    """
    slim: dict = {
        "symbol": ctx.get("symbol"),
        "exchange": ctx.get("exchange"),
        "latest_price": ctx.get("latest_price"),
        "technical_signals": ctx.get("technical_signals", []),
    }

    # Regime: just the key fields
    r = ctx.get("regime")
    if r and isinstance(r, dict):
        slim["regime"] = {
            "regime": r.get("regime"),
            "confidence": r.get("confidence"),
            "risk_scalar": r.get("risk_scalar"),
        }

    # Volatility: key numbers only
    v = ctx.get("volatility")
    if v and isinstance(v, dict):
        slim["volatility"] = {
            "vol_regime": v.get("vol_regime"),
            "realized_vol_1d": v.get("realized_vol_1d"),
            "vol_zscore": v.get("vol_zscore"),
            "risk_state": v.get("risk_state"),
        }

    # Liquidity: just the spread and depth
    liq = ctx.get("liquidity")
    if liq and isinstance(liq, dict):
        slim["liquidity"] = {
            "spread_bps": liq.get("spread_bps"),
            "bid_depth_usd": liq.get("bid_depth_usd"),
            "ask_depth_usd": liq.get("ask_depth_usd"),
        }

    # Funding: just the rate
    f = ctx.get("funding")
    if f and isinstance(f, dict):
        slim["funding_rate"] = f.get("rate") or f.get("funding_rate")

    # Correlation: just the stat arb alert if present
    if ctx.get("stat_arb_alert"):
        slim["stat_arb_alert"] = ctx["stat_arb_alert"]

    return slim
