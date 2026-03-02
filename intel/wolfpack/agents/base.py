"""Base agent class — all 4 intelligence agents inherit from this."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


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
    """
    Base intelligence agent.
    Each agent receives market data and produces structured analysis
    using LLM reasoning combined with quantitative signals.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name."""
        ...

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
        """
        Run analysis on the provided market data.

        Args:
            market_data: Dict containing candles, funding, orderbook, etc.
            exchange: Exchange ID (hyperliquid/dydx)

        Returns:
            Structured agent output with signals and confidence.
        """
        ...

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
