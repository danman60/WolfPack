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
        """Call LLM (Anthropic → DeepSeek fallback) with the agent's system prompt."""
        if settings.anthropic_api_key:
            return await self._call_anthropic(prompt)
        elif settings.deepseek_api_key:
            return await self._call_deepseek(prompt)
        else:
            logger.warning(f"{self.name}: No LLM API key configured")
            return json.dumps({"summary": "No LLM API key configured", "conviction": 0})

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

    def _parse_llm_json(self, text: str) -> dict:
        """Try to parse JSON from LLM response, with fallback."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            # Try to find JSON in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            return {"summary": text, "conviction": 30}
