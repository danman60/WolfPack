"""LP Rebalance Engine — debounced rebalance triggers for LP positions."""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

REBALANCE_DEBOUNCE_TICKS = 3   # consecutive OOR ticks before rebalance
REBALANCE_COOLDOWN_TICKS = 6   # minimum ticks between rebalances (30 min)
IL_REBALANCE_THRESHOLD = 5.0   # IL % that triggers rebalance


@dataclass
class RebalanceState:
    position_id: str
    out_of_range_count: int = 0
    last_rebalance_tick: int = 0     # tick counter at last rebalance
    total_rebalances: int = 0


class LPRebalanceEngine:
    def __init__(self):
        self._states: dict[str, RebalanceState] = {}
        self._tick_counter: int = 0

    def evaluate(self, position, recommended_range) -> dict | None:
        """Evaluate if position needs rebalancing.

        Args:
            position: PaperLPPosition (has pool_address, tick_lower, tick_upper,
                      current_tick, il_pct, status, position_id)
            recommended_range: RangeRecommendation (has tick_lower, tick_upper)

        Returns dict with action details or None.
        Triggers:
        1. Out of range for REBALANCE_DEBOUNCE_TICKS consecutive ticks
        2. IL exceeds IL_REBALANCE_THRESHOLD
        3. Range width changed >20% from recommended (vol shift)

        Respects cooldown between rebalances.
        """
        self._tick_counter += 1
        state = self._get_state(position.position_id)

        # Check cooldown
        if state.last_rebalance_tick > 0:
            ticks_since = self._tick_counter - state.last_rebalance_tick
            if ticks_since < REBALANCE_COOLDOWN_TICKS:
                return None

        # Trigger 1: Out of range (debounced)
        in_range = position.tick_lower <= position.current_tick <= position.tick_upper
        if not in_range:
            state.out_of_range_count += 1
            if state.out_of_range_count >= REBALANCE_DEBOUNCE_TICKS:
                return self._build_rebalance_action(position, recommended_range, "out_of_range", state)
        else:
            state.out_of_range_count = 0

        # Trigger 2: IL threshold
        if abs(position.il_pct) >= IL_REBALANCE_THRESHOLD:
            return self._build_rebalance_action(position, recommended_range, "il_threshold", state)

        # Trigger 3: Range width shift >20%
        if recommended_range:
            current_width = position.tick_upper - position.tick_lower
            new_width = recommended_range.tick_upper - recommended_range.tick_lower
            if current_width > 0 and abs(new_width - current_width) / current_width > 0.20:
                return self._build_rebalance_action(position, recommended_range, "vol_shift", state)

        return None

    def record_rebalance(self, position_id: str):
        """Record that a rebalance was executed."""
        state = self._get_state(position_id)
        state.last_rebalance_tick = self._tick_counter
        state.total_rebalances += 1
        state.out_of_range_count = 0

    def _get_state(self, position_id: str) -> RebalanceState:
        if position_id not in self._states:
            self._states[position_id] = RebalanceState(position_id=position_id)
        return self._states[position_id]

    def _build_rebalance_action(self, position, recommended_range, reason: str, state: RebalanceState) -> dict:
        return {
            "action": "rebalance",
            "position_id": position.position_id,
            "pool_address": position.pool_address,
            "pair": f"{position.token0_symbol}/{position.token1_symbol}",
            "old_range": [position.tick_lower, position.tick_upper],
            "new_range": [recommended_range.tick_lower, recommended_range.tick_upper] if recommended_range else None,
            "reason": reason,
            "il_pct": position.il_pct,
            "out_of_range_ticks": state.out_of_range_count,
        }
