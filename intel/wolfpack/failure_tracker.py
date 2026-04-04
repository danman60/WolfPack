"""Consecutive failure tracking for intelligence agents.

If any agent fails SAFE_MODE_THRESHOLD times in a row, safe mode activates:
no new positions are opened until the agent recovers. Exits (close/reduce)
are always allowed — safe mode only blocks new entries.
"""

import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SAFE_MODE_THRESHOLD = 3  # consecutive failures before safe mode


@dataclass
class AgentFailureState:
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None
    last_success_time: Optional[float] = None


class FailureTracker:
    def __init__(self, threshold: int = SAFE_MODE_THRESHOLD):
        self.threshold = threshold
        self._agents: Dict[str, AgentFailureState] = {}

    def record_success(self, agent_name: str):
        """Reset failure counter on successful agent run."""
        state = self._agents.get(agent_name, AgentFailureState())
        was_failing = state.consecutive_failures >= self.threshold
        state.consecutive_failures = 0
        state.last_success_time = time.time()
        self._agents[agent_name] = state

        if was_failing:
            logger.info(f"Agent '{agent_name}' recovered — exiting safe mode contribution")

    def record_failure(self, agent_name: str, error: str):
        """Increment failure counter. Log loudly at threshold."""
        state = self._agents.get(agent_name, AgentFailureState())
        state.consecutive_failures += 1
        state.last_error = str(error)[:500]  # truncate
        state.last_error_time = time.time()
        self._agents[agent_name] = state

        if state.consecutive_failures == self.threshold:
            logger.error(
                f"SAFE MODE ACTIVATED — Agent '{agent_name}' failed {self.threshold}x consecutively. "
                f"Last error: {state.last_error}. No new positions will be opened."
            )
        elif state.consecutive_failures > self.threshold:
            logger.warning(f"Agent '{agent_name}' still failing ({state.consecutive_failures}x): {state.last_error}")

    def is_safe_mode(self) -> bool:
        """True if ANY agent has hit the failure threshold."""
        return any(
            s.consecutive_failures >= self.threshold
            for s in self._agents.values()
        )

    def get_failing_agents(self) -> list:
        """Return names of agents currently in failure state."""
        return [
            name for name, state in self._agents.items()
            if state.consecutive_failures >= self.threshold
        ]

    def get_status(self) -> dict:
        """Full status for health endpoint."""
        return {
            "safe_mode": self.is_safe_mode(),
            "failing_agents": self.get_failing_agents(),
            "agents": {
                name: {
                    "consecutive_failures": state.consecutive_failures,
                    "last_error": state.last_error,
                    "last_error_time": state.last_error_time,
                    "last_success_time": state.last_success_time,
                }
                for name, state in self._agents.items()
            },
        }
