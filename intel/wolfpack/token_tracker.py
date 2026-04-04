"""Token usage telemetry — track LLM costs per agent call."""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Approximate costs per 1M tokens (input/output)
MODEL_COSTS = {
    # Anthropic
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-20250414": {"input": 0.80, "output": 4.0},
    # DeepSeek
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # OpenRouter (varies, use defaults)
    "default": {"input": 1.0, "output": 3.0},
}


class TokenTracker:
    """Track token usage and estimated costs for LLM calls."""

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self._session_totals = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "estimated_cost_usd": 0.0,
            "calls": 0,
        }

    def record_usage(
        self,
        agent_name: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        symbol: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """Record token usage for a single LLM call."""
        total = prompt_tokens + completion_tokens
        cost = self._estimate_cost(model, prompt_tokens, completion_tokens)

        # Update session totals
        self._session_totals["prompt_tokens"] += prompt_tokens
        self._session_totals["completion_tokens"] += completion_tokens
        self._session_totals["estimated_cost_usd"] += cost
        self._session_totals["calls"] += 1

        # Persist to DB
        try:
            self.supabase.table("wp_token_usage").insert({
                "agent_name": agent_name,
                "model": model,
                "provider": provider or self._infer_provider(model),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total,
                "estimated_cost_usd": cost,
                "symbol": symbol,
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to record token usage: {e}")

        logger.debug(
            f"Token usage: {agent_name}/{model} — "
            f"{prompt_tokens}+{completion_tokens}={total} tokens, ${cost:.4f}"
        )

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in USD based on model pricing."""
        costs = MODEL_COSTS.get(model, MODEL_COSTS["default"])
        input_cost = (prompt_tokens / 1_000_000) * costs["input"]
        output_cost = (completion_tokens / 1_000_000) * costs["output"]
        return round(input_cost + output_cost, 6)

    def _infer_provider(self, model: str) -> str:
        """Infer provider from model name."""
        if "claude" in model:
            return "anthropic"
        if "deepseek" in model:
            return "deepseek"
        return "openrouter"

    def get_daily_summary(self) -> dict:
        """Get today's token usage summary."""
        try:
            today = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
            result = self.supabase.table("wp_token_usage").select(
                "agent_name, model, prompt_tokens, completion_tokens, "
                "total_tokens, estimated_cost_usd"
            ).gte("created_at", today).execute()

            if not result.data:
                return {
                    "total_tokens": 0,
                    "total_cost": 0,
                    "calls": 0,
                    "by_agent": {},
                    "by_model": {},
                }

            total_tokens = sum(r["total_tokens"] or 0 for r in result.data)
            total_cost = sum(float(r["estimated_cost_usd"] or 0) for r in result.data)

            by_agent: dict = {}
            by_model: dict = {}
            for r in result.data:
                agent = r["agent_name"]
                model = r["model"] or "unknown"
                tokens = r["total_tokens"] or 0
                cost = float(r["estimated_cost_usd"] or 0)

                if agent not in by_agent:
                    by_agent[agent] = {"tokens": 0, "cost": 0, "calls": 0}
                by_agent[agent]["tokens"] += tokens
                by_agent[agent]["cost"] += cost
                by_agent[agent]["calls"] += 1

                if model not in by_model:
                    by_model[model] = {"tokens": 0, "cost": 0, "calls": 0}
                by_model[model]["tokens"] += tokens
                by_model[model]["cost"] += cost
                by_model[model]["calls"] += 1

            return {
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "calls": len(result.data),
                "by_agent": by_agent,
                "by_model": by_model,
            }
        except Exception as e:
            logger.warning(f"Failed to get daily summary: {e}")
            return {"error": str(e)}

    def get_session_totals(self) -> dict:
        """Return totals since this process started."""
        return dict(self._session_totals)
