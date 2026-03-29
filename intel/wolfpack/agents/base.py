"""Base agent class — all 4 intelligence agents inherit from this."""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from wolfpack.config import settings

logger = logging.getLogger(__name__)


class AgentOutput(BaseModel):
    """Standardized output from any intelligence agent."""

    agent_name: str
    exchange: str
    timestamp: datetime
    summary: str
    signals: list[dict[str, Any]]
    confidence: float  # 0-1
    raw_data: dict[str, Any] | None = None


class Agent(ABC):
    """Base intelligence agent with LLM integration.

    Each agent receives market data and produces structured analysis
    using LLM reasoning combined with quantitative signals.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name."""
        ...

    @property
    def agent_key(self) -> str:
        """DB key for this agent (e.g. 'quant', 'snoop')."""
        return self.name.lower().replace("the ", "").strip()

    @property
    @abstractmethod
    def role(self) -> str:
        """Short description of the agent's function."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt defining the agent's personality and analysis style."""
        ...

    @property
    def model_override(self) -> str | None:
        """Override DeepSeek model for this agent. Return None to use default."""
        return None

    @abstractmethod
    async def analyze(self, market_data: dict[str, Any], exchange: str) -> AgentOutput:
        """Run analysis on the provided market data."""
        ...

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_deepseek_client_config(self) -> tuple[str, str, str, str]:
        """Return (api_key, base_url, chat_model, reasoner_model) for DeepSeek calls.

        Prefers OpenRouter over direct DeepSeek API.
        """
        if settings.openrouter_api_key:
            return (
                settings.openrouter_api_key,
                "https://openrouter.ai/api/v1",
                "deepseek/deepseek-chat-v3-0324",
                "deepseek/deepseek-r1",
            )
        return (
            settings.deepseek_api_key,
            settings.deepseek_base_url,
            settings.deepseek_model,
            settings.deepseek_reasoner_model,
        )

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM (Anthropic -> DeepSeek fallback) with the agent's system prompt."""
        if settings.anthropic_api_key:
            return await self._call_anthropic(prompt)
        elif settings.openrouter_api_key or settings.deepseek_api_key:
            return await self._call_deepseek(prompt)
        else:
            logger.warning(f"{self.name}: No LLM API key configured")
            return json.dumps({"summary": "No LLM API key configured", "conviction": 0})

    async def _call_llm_structured(self, prompt: str, schema: dict) -> dict:
        """Call LLM with structured output enforcement. Returns parsed dict.

        Anthropic: uses tool_use to guarantee valid JSON matching schema.
        DeepSeek: uses response_format=json_object.
        DeepSeek-Reasoner (R1): uses text response + JSON extraction (no json_object support).
        Falls back to text parsing on error.
        """
        if settings.anthropic_api_key:
            return await self._call_anthropic_structured(prompt, schema)
        elif settings.openrouter_api_key or settings.deepseek_api_key:
            api_key, base_url, chat_model, reasoner_model = self._get_deepseek_client_config()
            model = self.model_override or chat_model
            if model in (settings.deepseek_reasoner_model, reasoner_model):
                return await self._call_deepseek_reasoner(prompt)
            return await self._call_deepseek_structured(prompt)
        else:
            logger.warning(f"{self.name}: No LLM API key configured")
            return {"summary": "No LLM API key configured", "conviction": 0}

    async def _call_anthropic(self, prompt: str) -> str:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        try:
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"{self.name} Anthropic error: {e}")
            raise

    async def _call_anthropic_structured(self, prompt: str, schema: dict) -> dict:
        """Call Anthropic with tool_use for guaranteed structured output."""
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        tool_name = f"{self.agent_key}_analysis"

        try:
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
                tools=[{
                    "name": tool_name,
                    "description": f"Output structured {self.name} analysis",
                    "input_schema": schema,
                }],
                tool_choice={"type": "tool", "name": tool_name},
            )
            for block in response.content:
                if block.type == "tool_use":
                    return block.input  # type: ignore[return-value]
            # Fallback: text block
            for block in response.content:
                if block.type == "text":
                    return self._parse_llm_json(block.text)
            return {"summary": "No structured output returned", "conviction": 0}
        except Exception as e:
            logger.error(f"{self.name} Anthropic structured error: {e}")
            try:
                raw = await self._call_anthropic(prompt)
                return self._parse_llm_json(raw)
            except Exception:
                raise e

    async def _call_deepseek(self, prompt: str) -> str:
        from openai import AsyncOpenAI

        api_key, base_url, chat_model, reasoner_model = self._get_deepseek_client_config()
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        model = self.model_override or chat_model
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 1024,
            }
            # R1 (deepseek-reasoner) does not support temperature
            if model not in (settings.deepseek_reasoner_model, reasoner_model):
                kwargs["temperature"] = 0.3
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"{self.name} DeepSeek error: {e}")
            raise

    async def _call_deepseek_structured(self, prompt: str) -> dict:
        """Call DeepSeek with JSON mode for structured output."""
        from openai import AsyncOpenAI

        api_key, base_url, chat_model, _reasoner = self._get_deepseek_client_config()
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        model = self.model_override or chat_model
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1024,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or "{}"
            return self._parse_llm_json(text)
        except Exception as e:
            logger.error(f"{self.name} DeepSeek structured error: {e}")
            try:
                raw = await self._call_deepseek(prompt)
                return self._parse_llm_json(raw)
            except Exception:
                raise e

    async def _call_deepseek_reasoner(self, prompt: str) -> dict:
        """Call DeepSeek-Reasoner (R1) — no json_object mode, no temperature.

        R1 returns text (possibly with markdown fences). We extract JSON via _parse_llm_json.
        """
        from openai import AsyncOpenAI

        api_key, base_url, _chat, reasoner_model = self._get_deepseek_client_config()
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        try:
            response = await client.chat.completions.create(
                model=reasoner_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
            )
            text = response.choices[0].message.content or "{}"
            return self._parse_llm_json(text)
        except Exception as e:
            logger.error(f"{self.name} DeepSeek-Reasoner error: {e}")
            raise

    def _parse_llm_json(self, text: str) -> dict:
        """Try to parse JSON from LLM response, with fallback.

        Handles markdown code fences (```json ... ```) that DeepSeek sometimes wraps around output.
        """
        # Strip markdown code fences if present
        import re
        stripped = re.sub(r"^```(?:json)?\s*\n?", "", text.strip(), count=1)
        stripped = re.sub(r"\n?```\s*$", "", stripped.strip(), count=1)

        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            start = stripped.find("{")
            end = stripped.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(stripped[start:end])
                except json.JSONDecodeError:
                    pass
            return {"summary": text, "conviction": 30}
