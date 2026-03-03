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

    @abstractmethod
    async def analyze(self, market_data: dict[str, Any], exchange: str) -> AgentOutput:
        """Run analysis on the provided market data."""
        ...

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM (Anthropic -> DeepSeek fallback) with the agent's system prompt."""
        if settings.anthropic_api_key:
            return await self._call_anthropic(prompt)
        elif settings.deepseek_api_key:
            return await self._call_deepseek(prompt)
        else:
            logger.warning(f"{self.name}: No LLM API key configured")
            return json.dumps({"summary": "No LLM API key configured", "conviction": 0})

    async def _call_llm_structured(self, prompt: str, schema: dict) -> dict:
        """Call LLM with structured output enforcement. Returns parsed dict.

        Anthropic: uses tool_use to guarantee valid JSON matching schema.
        DeepSeek: uses response_format=json_object.
        Falls back to text parsing on error.
        """
        if settings.anthropic_api_key:
            return await self._call_anthropic_structured(prompt, schema)
        elif settings.deepseek_api_key:
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

        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        try:
            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1024,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"{self.name} DeepSeek error: {e}")
            raise

    async def _call_deepseek_structured(self, prompt: str) -> dict:
        """Call DeepSeek with JSON mode for structured output."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        try:
            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1024,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or "{}"
            return json.loads(text)
        except Exception as e:
            logger.error(f"{self.name} DeepSeek structured error: {e}")
            try:
                raw = await self._call_deepseek(prompt)
                return self._parse_llm_json(raw)
            except Exception:
                raise e

    def _parse_llm_json(self, text: str) -> dict:
        """Try to parse JSON from LLM response, with fallback."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            return {"summary": text, "conviction": 30}
