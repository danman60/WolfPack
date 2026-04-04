"""Regime router -- maps regime state to allowed strategy sets."""


def route_strategies(regime_output, vol_output=None) -> dict:
    """Route strategies based on regime and volatility state.

    Returns dict with 'allowed' (list of strategy names), 'macro_regime', 'reason'.
    When regime_output is None, returns allowed=None (all strategies run).
    """
    if regime_output is None:
        return {"allowed": None, "macro_regime": "unknown", "reason": "no regime data"}

    regime = regime_output.regime.value if hasattr(regime_output.regime, "value") else str(regime_output.regime)
    agreement = (
        getattr(regime_output.sub_signals, "multi_tf_agreement", 1.0)
        if regime_output.sub_signals
        else 1.0
    )

    # Check volatility
    vol_regime = ""
    if vol_output:
        vol_regime = (
            vol_output.get("vol_regime", "")
            if isinstance(vol_output, dict)
            else getattr(vol_output, "vol_regime", "")
        )

    # VOLATILE: panic or extreme vol
    if regime == "panic" or vol_regime == "extreme":
        return {
            "allowed": [],
            "macro_regime": "VOLATILE",
            "reason": f"regime={regime}, vol={vol_regime}",
        }

    # TRENDING: trending + multi-TF agreement
    if regime in ("trending_up", "trending_down") and agreement >= 0.75:
        return {
            "allowed": ["ema_crossover", "turtle_donchian", "orb_session", "regime_momentum"],
            "macro_regime": "TRENDING",
            "reason": f"regime={regime}, agreement={agreement:.2f}",
        }

    # RANGING: choppy, low_vol_grind, or poor TF agreement
    return {
        "allowed": ["mean_reversion", "measured_move"],
        "macro_regime": "RANGING",
        "reason": f"regime={regime}, agreement={agreement:.2f}",
    }
