"""Regime router -- maps regime state to allowed strategy sets.

Emits both a *family* classification (TRENDING / RANGING / VOLATILE) for
backward compatibility AND a *specific* sub-regime for granular strategy
tuning:

    TRENDING_UP        — sustained higher highs, momentum bull
    TRENDING_DOWN      — sustained lower lows, momentum bear
    RANGING_LOW_VOL    — quiet chop, tight ATR, mean-reversion bread and butter
    RANGING_HIGH_VOL   — wide swings inside a range, bigger stops + targets
    VOLATILE           — panic / extreme ATR, no new entries
    TRANSITION         — pending regime changing, tighten + wait

Strategies can read either `macro_regime` (family) or `specific_regime`
(sub-type) from the router return dict. Non-regime-aware strategies
continue to work unchanged.

Debounce: regime must persist for N consecutive ticks before switching
macro state. Prevents whipsaw open-close-open churn when regime oscillates
between trending and choppy on consecutive ticks. During the debounce
window the router exposes `transition=True` so process_strategy_signals
can tighten stops and block new entries while the market is making up
its mind.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Require this many consecutive ticks of the same macro regime before switching
DEBOUNCE_TICKS = 3

# Specific sub-regime → parent family lookup
FAMILY_OF: dict[str, str] = {
    "TRENDING_UP": "TRENDING",
    "TRENDING_DOWN": "TRENDING",
    "RANGING_LOW_VOL": "RANGING",
    "RANGING_HIGH_VOL": "RANGING",
    "VOLATILE": "VOLATILE",
    "TRANSITION": "TRANSITION",
    "unknown": "unknown",
}


def regime_family(specific: str | None) -> str:
    """Map a specific sub-regime name to its parent family."""
    if not specific:
        return "unknown"
    return FAMILY_OF.get(specific, specific)


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
    """Classify raw regime into a specific sub-regime.

    Returns (specific_regime, reason, allowed_strategies). The parent family
    can be retrieved via regime_family(specific_regime).
    """

    # VOLATILE: panic or extreme vol — always immediate, no debounce
    if regime == "panic" or vol_regime == "extreme":
        return "VOLATILE", f"regime={regime}, vol={vol_regime}", []

    # TRENDING UP: confirmed uptrend with strong multi-TF agreement
    if regime == "trending_up" and agreement >= 0.75:
        return (
            "TRENDING_UP",
            f"regime={regime}, agreement={agreement:.2f}",
            ["ema_crossover", "turtle_donchian", "orb_session"],
        )

    # TRENDING DOWN: confirmed downtrend with strong multi-TF agreement
    if regime == "trending_down" and agreement >= 0.75:
        return (
            "TRENDING_DOWN",
            f"regime={regime}, agreement={agreement:.2f}",
            ["ema_crossover", "turtle_donchian", "orb_session"],
        )

    # RANGING: choppy, low_vol_grind, or poor TF agreement in trends.
    # Split into HIGH_VOL vs LOW_VOL by the volatility module's output so
    # strategies can tune their thresholds to band width.
    # (measured_move was removed — it's a session-open breakout, not a fader.)
    if vol_regime == "elevated":
        return (
            "RANGING_HIGH_VOL",
            f"regime={regime}, agreement={agreement:.2f}, vol={vol_regime}",
            ["mean_reversion", "band_fade"],
        )
    return (
        "RANGING_LOW_VOL",
        f"regime={regime}, agreement={agreement:.2f}, vol={vol_regime}",
        ["mean_reversion", "band_fade"],
    )


# Allowed strategy list per specific sub-regime. Strategies receive the
# specific sub-regime in their evaluate() call so they can tune params.
#
# 2026-04-13: added slow_drift_follow + range_breakout as RANGING probes.
# Neither has historical validation — PerformanceTracker grades them and
# scales allocation. Current RANGING strategies (mean_reversion / band_fade)
# have been unreliable in slow-drift chop and need alternatives.
_ALLOWED_BY_REGIME: dict[str, list[str]] = {
    "TRENDING_UP":      ["ema_crossover", "turtle_donchian", "trend_pullback", "orb_session"],
    "TRENDING_DOWN":    ["ema_crossover", "turtle_donchian", "trend_pullback", "orb_session"],
    "RANGING_LOW_VOL":  ["mean_reversion", "band_fade", "slow_drift_follow", "range_breakout"],
    "RANGING_HIGH_VOL": ["mean_reversion", "band_fade", "slow_drift_follow", "range_breakout"],
    "VOLATILE":         [],  # safety: no new entries
    "TRANSITION":       [],  # wait for confirmation, tighten stops instead
}


def _build_return(
    specific_regime: str,
    reason: str,
    state: "RegimeState",
    transition: bool = False,
) -> dict:
    """Build the router return dict with family + specific + transition flag."""
    allowed = _ALLOWED_BY_REGIME.get(specific_regime)
    return {
        "allowed": allowed,
        "macro_regime": regime_family(specific_regime),
        "specific_regime": specific_regime,
        "transition": transition,
        "reason": reason,
        "debounce": f"pending={state.pending_macro}({state.pending_count}/{DEBOUNCE_TICKS})",
    }


def route_strategies(regime_output, vol_output=None, symbol: str = "BTC") -> dict:
    """Route strategies based on regime and volatility state.

    Returns dict with:
      - allowed: list of strategy names allowed to fire this cycle
      - macro_regime: parent family (TRENDING / RANGING / VOLATILE / TRANSITION)
      - specific_regime: sub-type (TRENDING_UP, RANGING_LOW_VOL, etc.)
      - transition: True when debounce is in progress (pending != current)
      - reason: human-readable classification context
      - debounce: pending state for diagnostics

    Debounce: macro regime must persist for DEBOUNCE_TICKS consecutive ticks
    before switching. Exception: VOLATILE is always immediate (safety).
    While debouncing, the router emits `transition=True` and an empty
    `allowed` list so process_strategy_signals can tighten stops without
    opening new positions in a regime that isn't confirmed.
    """
    if regime_output is None:
        return {
            "allowed": None,
            "macro_regime": "unknown",
            "specific_regime": "unknown",
            "transition": False,
            "reason": "no regime data",
            "debounce": "",
        }

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

    raw_specific, reason, _allowed = _classify_macro(regime, agreement, vol_regime)
    state = _get_state(symbol)

    # VOLATILE is always immediate — safety override, no debounce
    if raw_specific == "VOLATILE":
        state.current_macro = "VOLATILE"
        state.pending_macro = "VOLATILE"
        state.pending_count = DEBOUNCE_TICKS
        state.last_reason = reason
        return _build_return("VOLATILE", reason, state)

    # First tick ever — initialize without debounce
    if state.current_macro == "unknown":
        state.current_macro = raw_specific
        state.pending_macro = raw_specific
        state.pending_count = DEBOUNCE_TICKS
        state.last_reason = reason
        return _build_return(raw_specific, reason, state)

    # Same as pending — increment counter
    if raw_specific == state.pending_macro:
        state.pending_count += 1
    else:
        # New regime detected — reset counter
        state.pending_macro = raw_specific
        state.pending_count = 1
        logger.info(
            f"[regime-router] {symbol}: new pending regime {raw_specific} "
            f"(need {DEBOUNCE_TICKS} ticks to confirm)"
        )

    # Check if pending has reached threshold — promote pending to current
    if state.pending_count >= DEBOUNCE_TICKS and state.pending_macro != state.current_macro:
        old = state.current_macro
        state.current_macro = state.pending_macro
        state.last_reason = reason
        logger.info(
            f"[regime-router] {symbol}: REGIME SHIFT {old} -> {state.current_macro} "
            f"(confirmed after {DEBOUNCE_TICKS} ticks)"
        )

    # If pending != current AND we're mid-debounce, emit TRANSITION state
    transition = (
        state.pending_macro != state.current_macro
        and state.pending_count < DEBOUNCE_TICKS
    )
    if transition:
        return _build_return("TRANSITION", state.last_reason, state, transition=True)

    return _build_return(state.current_macro, state.last_reason, state)


def get_regime_state(symbol: str = "BTC") -> dict:
    """Get current regime state for diagnostics."""
    state = _get_state(symbol)
    return {
        "current_specific": state.current_macro,
        "current_family": regime_family(state.current_macro),
        "pending_specific": state.pending_macro,
        "pending_family": regime_family(state.pending_macro),
        "pending_count": state.pending_count,
        "debounce_threshold": DEBOUNCE_TICKS,
        "confirmed": state.pending_count >= DEBOUNCE_TICKS,
        "transition_active": (
            state.pending_macro != state.current_macro
            and state.pending_count < DEBOUNCE_TICKS
        ),
        "last_reason": state.last_reason,
    }
