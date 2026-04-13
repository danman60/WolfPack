"""Regime router -- maps regime state to allowed strategy sets.

Includes debounce logic: regime must persist for N consecutive ticks
before switching macro state. Prevents whipsaw open-close-open churn
when regime oscillates between trending and choppy on consecutive ticks.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Require this many consecutive ticks of the same macro regime before switching
DEBOUNCE_TICKS = 3


@dataclass
class RegimeState:
    """Tracks regime persistence for debounce."""
    current_macro: str = "unknown"      # Active macro regime (what strategies see)
    pending_macro: str = "unknown"      # What regime detector is saying now
    pending_count: int = 0              # How many consecutive ticks pending has held
    last_reason: str = ""


# Per-symbol regime state
_regime_states: dict[str, RegimeState] = {}


def _get_state(symbol: str) -> RegimeState:
    if symbol not in _regime_states:
        _regime_states[symbol] = RegimeState()
    return _regime_states[symbol]


def _classify_macro(regime: str, agreement: float, vol_regime: str) -> tuple[str, str, list[str]]:
    """Classify raw regime into macro state. Returns (macro, reason, allowed_strategies)."""

    # VOLATILE: panic or extreme vol — always immediate, no debounce
    if regime == "panic" or vol_regime == "extreme":
        return "VOLATILE", f"regime={regime}, vol={vol_regime}", []

    # TRENDING: trending + multi-TF agreement
    if regime in ("trending_up", "trending_down") and agreement >= 0.75:
        return (
            "TRENDING",
            f"regime={regime}, agreement={agreement:.2f}",
            ["ema_crossover", "turtle_donchian", "orb_session"],
        )

    # RANGING: choppy, low_vol_grind, or poor TF agreement
    # Note: measured_move is a session-open breakout strategy, not a range fader.
    # It's been removed from the RANGING list — its 5m session-window nature is
    # incompatible with mean-reversion chop. band_fade replaces it as the second
    # true range strategy alongside mean_reversion.
    return (
        "RANGING",
        f"regime={regime}, agreement={agreement:.2f}",
        ["mean_reversion", "band_fade"],
    )


def route_strategies(regime_output, vol_output=None, symbol: str = "BTC") -> dict:
    """Route strategies based on regime and volatility state.

    Returns dict with 'allowed' (list of strategy names), 'macro_regime', 'reason'.
    When regime_output is None, returns allowed=None (all strategies run).

    Debounce: macro regime must persist for DEBOUNCE_TICKS consecutive ticks
    before switching. Exception: VOLATILE is always immediate (safety).
    """
    if regime_output is None:
        return {"allowed": None, "macro_regime": "unknown", "reason": "no regime data"}

    regime = regime_output.regime.value if hasattr(regime_output.regime, "value") else str(regime_output.regime)
    agreement = (
        getattr(regime_output.sub_signals, "multi_tf_agreement", 1.0)
        if regime_output.sub_signals
        else 1.0
    )

    vol_regime = ""
    if vol_output:
        vol_regime = (
            vol_output.get("vol_regime", "")
            if isinstance(vol_output, dict)
            else getattr(vol_output, "vol_regime", "")
        )

    raw_macro, reason, allowed = _classify_macro(regime, agreement, vol_regime)
    state = _get_state(symbol)

    # VOLATILE is always immediate — safety override, no debounce
    if raw_macro == "VOLATILE":
        state.current_macro = "VOLATILE"
        state.pending_macro = "VOLATILE"
        state.pending_count = DEBOUNCE_TICKS
        state.last_reason = reason
        return {"allowed": [], "macro_regime": "VOLATILE", "reason": reason}

    # First tick ever — initialize without debounce
    if state.current_macro == "unknown":
        state.current_macro = raw_macro
        state.pending_macro = raw_macro
        state.pending_count = DEBOUNCE_TICKS
        state.last_reason = reason
        return {"allowed": allowed, "macro_regime": raw_macro, "reason": reason}

    # Same as pending — increment counter
    if raw_macro == state.pending_macro:
        state.pending_count += 1
    else:
        # New regime detected — reset counter
        state.pending_macro = raw_macro
        state.pending_count = 1
        logger.info(f"[regime-router] {symbol}: new pending regime {raw_macro} (need {DEBOUNCE_TICKS} ticks to confirm)")

    # Check if pending has reached threshold
    if state.pending_count >= DEBOUNCE_TICKS and state.pending_macro != state.current_macro:
        old = state.current_macro
        state.current_macro = state.pending_macro
        state.last_reason = reason
        logger.info(f"[regime-router] {symbol}: REGIME SHIFT {old} -> {state.current_macro} (confirmed after {DEBOUNCE_TICKS} ticks)")

    # Return based on CURRENT (debounced) macro, not raw
    if state.current_macro == "TRENDING":
        return {
            "allowed": ["ema_crossover", "turtle_donchian", "orb_session"],
            "macro_regime": "TRENDING",
            "reason": state.last_reason,
            "debounce": f"pending={state.pending_macro}({state.pending_count}/{DEBOUNCE_TICKS})",
        }
    elif state.current_macro == "RANGING":
        return {
            "allowed": ["mean_reversion", "band_fade"],
            "macro_regime": "RANGING",
            "reason": state.last_reason,
            "debounce": f"pending={state.pending_macro}({state.pending_count}/{DEBOUNCE_TICKS})",
        }
    else:
        return {
            "allowed": None,
            "macro_regime": state.current_macro,
            "reason": state.last_reason,
            "debounce": f"pending={state.pending_macro}({state.pending_count}/{DEBOUNCE_TICKS})",
        }


def get_regime_state(symbol: str = "BTC") -> dict:
    """Get current regime state for diagnostics."""
    state = _get_state(symbol)
    return {
        "current_macro": state.current_macro,
        "pending_macro": state.pending_macro,
        "pending_count": state.pending_count,
        "debounce_threshold": DEBOUNCE_TICKS,
        "confirmed": state.pending_count >= DEBOUNCE_TICKS,
        "last_reason": state.last_reason,
    }
