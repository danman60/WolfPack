"""Regime transition manager — handles position management during regime shifts.

When regime shifts (e.g., TRENDING -> RANGING), this manager:
1. Identifies positions opened under the wrong regime
2. Closes those positions
3. Tightens stops on remaining positions
4. Blocks new entries for a cooldown period
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TRENDING_STRATEGIES = {"ema_crossover", "turtle_donchian", "orb_session", "regime_momentum"}
RANGING_STRATEGIES = {"mean_reversion", "measured_move"}

# Cooldown: 2 ticks = 10 minutes (each tick is 5 min)
COOLDOWN_TICKS = 2


@dataclass
class TransitionActions:
    """Actions to take during a regime transition."""
    close_positions: list[str] = field(default_factory=list)  # recommendation_ids to close
    tighten_stop_factor: float = 1.0  # multiply existing stop distance by this (0.5 = halve)
    cooldown_remaining: int = 0  # ticks remaining in cooldown
    regime_shifted: bool = False
    old_regime: str = ""
    new_regime: str = ""


class RegimeTransitionManager:
    """Manages positions during regime transitions."""

    def __init__(self):
        # Per-symbol state: {symbol: {"prev_macro": str, "cooldown_remaining": int}}
        self._symbol_states: dict[str, dict] = {}

    def _get_state(self, symbol: str) -> dict:
        """Get or create state for a symbol."""
        if symbol not in self._symbol_states:
            self._symbol_states[symbol] = {
                "prev_macro": "unknown",
                "cooldown_remaining": 0,
            }
        return self._symbol_states[symbol]

    def check_transition(
        self, symbol: str, current_macro: str, positions
    ) -> TransitionActions:
        """Check for regime transition and determine actions.

        Args:
            symbol: Asset symbol
            current_macro: Current macro regime (TRENDING, RANGING, VOLATILE)
            positions: List of position objects with recommendation_id attribute

        Returns:
            TransitionActions with positions to close and actions to take
        """
        actions = TransitionActions()
        state = self._get_state(symbol)
        prev_macro = state["prev_macro"]

        # Skip if in cooldown or no valid previous regime
        if state["cooldown_remaining"] > 0:
            actions.cooldown_remaining = state["cooldown_remaining"]
            return actions

        if prev_macro == "unknown" or prev_macro == "":
            # First regime detected
            state["prev_macro"] = current_macro
            return actions

        if current_macro == "unknown":
            return actions

        # Check for regime shift (excluding VOLATILE -> non-VOLATILE which is handled separately)
        if current_macro != prev_macro:
            actions.regime_shifted = True
            actions.old_regime = prev_macro
            actions.new_regime = current_macro

            # Start cooldown
            state["cooldown_remaining"] = COOLDOWN_TICKS
            actions.cooldown_remaining = COOLDOWN_TICKS

            # Identify wrong-regime positions to close
            # If TRENDING now, close RANGING positions
            # If RANGING now, close TRENDING positions
            wrong_strategies = set()
            if current_macro == "TRENDING":
                wrong_strategies = RANGING_STRATEGIES
            elif current_macro == "RANGING":
                wrong_strategies = TRENDING_STRATEGIES

            if wrong_strategies:
                for pos in positions:
                    rec_id = getattr(pos, "recommendation_id", "")
                    if rec_id:
                        # Check if any wrong strategy is in the recommendation_id
                        for wrong_strat in wrong_strategies:
                            if wrong_strat in rec_id:
                                actions.close_positions.append(rec_id)
                                break

            # Tighten stops on remaining positions
            actions.tighten_stop_factor = 0.5

            logger.info(
                f"[regime-transition] {symbol}: regime shifted {prev_macro} -> {current_macro}, "
                f"closing {len(actions.close_positions)} positions, tightening stops"
            )

        # Update previous regime
        state["prev_macro"] = current_macro

        return actions

    def is_in_cooldown(self, symbol: str) -> bool:
        """Check if symbol is currently in cooldown period."""
        state = self._get_state(symbol)
        return state["cooldown_remaining"] > 0

    def tick(self, symbol: str) -> None:
        """Decrement cooldown counter. Call once per cycle/tick.

        Args:
            symbol: Asset symbol
        """
        state = self._get_state(symbol)
        if state["cooldown_remaining"] > 0:
            state["cooldown_remaining"] -= 1
            if state["cooldown_remaining"] == 0:
                logger.info(f"[regime-transition] {symbol}: cooldown ended")


# Singleton instance
_manager: RegimeTransitionManager | None = None


def get_transition_manager() -> RegimeTransitionManager:
    """Get the singleton RegimeTransitionManager instance."""
    global _manager
    if _manager is None:
        _manager = RegimeTransitionManager()
    return _manager
