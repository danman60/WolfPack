"""Adaptive Position Sizing — Combines vol, regime, conviction, drawdown, and liquidity signals.

Produces a single recommended size_pct by multiplying a base allocation through
scaling factors from existing modules:

  final_size = base_pct * vol_scalar * regime_scalar * conviction_scalar * drawdown_scalar * liquidity_adj

Each scalar is clamped to safe bounds. Final output is floored at MIN_SIZE_PCT and
capped at MAX_SIZE_PCT (matches PaperTradingEngine's 25% hard cap).
"""

from typing import Any

from pydantic import BaseModel


class SizingOutput(BaseModel):
    """Result of the adaptive sizing computation."""

    base_pct: float
    vol_scalar: float
    regime_scalar: float
    conviction_scalar: float
    drawdown_scalar: float
    liquidity_adj: float
    raw_size_pct: float
    final_size_pct: float
    risk_state: str
    rationale: str


# Regime -> base risk scalar (mirrors regime.py _RISK_BASES but decoupled for sizing)
_REGIME_SIZING: dict[str, float] = {
    "trending_up": 1.0,
    "trending_down": 0.7,
    "choppy": 0.4,
    "panic": 0.15,
    "low_vol_grind": 0.6,
}

MIN_SIZE_PCT = 2.0
MAX_SIZE_PCT = 25.0
DEFAULT_BASE_PCT = 10.0


class SizingEngine:
    """Computes adaptive position size from multi-module inputs.

    Inputs (all optional — missing data defaults to neutral 1.0 scalars):
    - vol_output: VolatilityOutput (provides vol_scalar, drawdown_scalar, risk_state)
    - regime_output: RegimeSignal (provides regime enum, risk_scalar)
    - liquidity_output: LiquidityOutput (provides recommended_size_adjustment)
    - conviction: 0-100 from Brief agent recommendation
    - base_pct: starting allocation before adjustments (default 10%)
    """

    def __init__(self, base_pct: float = DEFAULT_BASE_PCT):
        self.base_pct = base_pct

    def compute(
        self,
        conviction: float = 50.0,
        vol_output: Any = None,
        regime_output: Any = None,
        liquidity_output: Any = None,
    ) -> SizingOutput:
        """Compute adaptive position size.

        Args:
            conviction: Brief agent conviction score (0-100).
            vol_output: VolatilityOutput or dict with vol_scalar, drawdown_scalar, risk_state.
            regime_output: RegimeSignal or dict with regime, risk_scalar.
            liquidity_output: LiquidityOutput or dict with recommended_size_adjustment.

        Returns:
            SizingOutput with all scalars and final_size_pct.
        """
        # --- Vol scalar: target_vol / realized_vol (from VolatilitySignal) ---
        vol_scalar = 1.0
        drawdown_scalar = 1.0
        risk_state = "full_risk"

        if vol_output is not None:
            v = vol_output if isinstance(vol_output, dict) else vol_output.model_dump()
            vol_scalar = float(v.get("vol_scalar", 1.0))
            drawdown_scalar = float(v.get("drawdown_scalar", 1.0))
            risk_state = v.get("risk_state", "full_risk")

        # Clamp vol scalar to [0.1, 1.5]
        vol_scalar = max(0.1, min(vol_scalar, 1.5))
        # Clamp drawdown scalar to [0.0, 1.0]
        drawdown_scalar = max(0.0, min(drawdown_scalar, 1.0))

        # --- Regime scalar ---
        regime_scalar = 1.0
        if regime_output is not None:
            r = regime_output if isinstance(regime_output, dict) else regime_output.model_dump()
            regime_name = r.get("regime", "choppy")
            # Use our sizing-specific regime map
            regime_scalar = _REGIME_SIZING.get(regime_name, 0.5)

        # --- Conviction scalar: maps 0-100 conviction to 0.3-1.2 multiplier ---
        # Below 40 conviction → heavily penalized (0.3-0.6)
        # 40-70 → moderate (0.6-1.0)
        # 70-100 → full-aggressive (1.0-1.2)
        conv = max(0.0, min(conviction, 100.0))
        if conv < 40:
            conviction_scalar = 0.3 + (conv / 40.0) * 0.3  # 0.3 to 0.6
        elif conv < 70:
            conviction_scalar = 0.6 + ((conv - 40) / 30.0) * 0.4  # 0.6 to 1.0
        else:
            conviction_scalar = 1.0 + ((conv - 70) / 30.0) * 0.2  # 1.0 to 1.2

        # --- Liquidity adjustment ---
        liquidity_adj = 1.0
        if liquidity_output is not None:
            liq = liquidity_output if isinstance(liquidity_output, dict) else liquidity_output.model_dump()
            liquidity_adj = float(liq.get("recommended_size_adjustment", 1.0))
        liquidity_adj = max(0.1, min(liquidity_adj, 1.0))

        # --- Emergency override: if risk_state is emergency or drawdown_scalar is 0, force minimum ---
        if risk_state == "emergency" or drawdown_scalar <= 0.0:
            return SizingOutput(
                base_pct=self.base_pct,
                vol_scalar=vol_scalar,
                regime_scalar=regime_scalar,
                conviction_scalar=conviction_scalar,
                drawdown_scalar=0.0,
                liquidity_adj=liquidity_adj,
                raw_size_pct=0.0,
                final_size_pct=0.0,
                risk_state=risk_state,
                rationale="Emergency: drawdown limit reached, no new positions",
            )

        # --- Compute raw size ---
        raw = self.base_pct * vol_scalar * regime_scalar * conviction_scalar * drawdown_scalar * liquidity_adj

        # --- Clamp to bounds ---
        final = max(MIN_SIZE_PCT, min(raw, MAX_SIZE_PCT))

        # --- Build rationale ---
        parts = []
        if vol_scalar < 0.8:
            parts.append(f"vol high (x{vol_scalar:.2f})")
        if regime_scalar < 0.5:
            parts.append(f"regime cautious (x{regime_scalar:.2f})")
        if conviction_scalar < 0.7:
            parts.append(f"low conviction (x{conviction_scalar:.2f})")
        if drawdown_scalar < 0.8:
            parts.append(f"drawdown pullback (x{drawdown_scalar:.2f})")
        if liquidity_adj < 0.8:
            parts.append(f"thin liquidity (x{liquidity_adj:.2f})")
        if not parts:
            parts.append("all signals favorable")

        rationale = f"Base {self.base_pct}% -> {final:.1f}%: {', '.join(parts)}"

        return SizingOutput(
            base_pct=self.base_pct,
            vol_scalar=round(vol_scalar, 4),
            regime_scalar=round(regime_scalar, 4),
            conviction_scalar=round(conviction_scalar, 4),
            drawdown_scalar=round(drawdown_scalar, 4),
            liquidity_adj=round(liquidity_adj, 4),
            raw_size_pct=round(raw, 4),
            final_size_pct=round(final, 2),
            risk_state=risk_state,
            rationale=rationale,
        )
