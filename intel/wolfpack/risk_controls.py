"""Unified Risk Policy — single source of truth for all hard and soft limits.

Hard limits are code-enforced and NEVER overridden by AI, config, or YOLO profiles.
Soft limits are AI-guided conviction penalties, not hard rejections.

YOLO profiles (Cautious → Full Send) are named presets that adjust soft limits
and some hard limits within safe bounds.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class HardLimits:
    """Code-enforced limits. NEVER overridden by AI or config."""
    max_positions: int = 5
    max_position_size_pct: float = 25.0       # sizing.py MAX_SIZE_PCT
    max_margin_usage_pct: float = 90.0
    max_drawdown_pct: float = 10.0            # circuit_breaker CRITICAL threshold
    daily_pnl_floor_pct: float = -3.0         # circuit_breaker CRITICAL threshold
    rolling_24h_pnl_floor_pct: float = -3.0   # circuit_breaker CRITICAL threshold
    min_position_size_usd: float = 50.0
    require_stop_loss: bool = True


@dataclass
class SoftLimits:
    """AI-guided limits. Applied as conviction penalties, not hard rejections."""
    conviction_floor: int = 55                # veto.py default floor
    max_trades_per_day: int = 4               # circuit_breaker soft violation
    max_exposure_pct: float = 50.0            # circuit_breaker soft violation
    max_data_age_s: float = 120.0             # circuit_breaker soft violation
    cooldown_seconds: float = 1800.0          # circuit_breaker SUSPENDED cooldown
    min_risk_reward: float = 2.0
    base_pct: float = 10.0                    # sizing.py DEFAULT_BASE_PCT
    # Conviction penalties (veto.py soft adjustments)
    high_vol_penalty: int = 10
    suspended_state_penalty: int = 15
    ema_distance_penalty: int = 15            # EMA distance >5%
    ema_extended_penalty: int = 8             # EMA distance >3%
    vwap_extreme_penalty: int = 15            # VWAP distance >10%
    vwap_extended_penalty: int = 5            # VWAP distance >5%
    recent_rejection_penalty: int = 20
    penalty_multiplier: float = 1.0           # scales all soft penalties
    rejection_cooldown_hours: float = 2.0
    max_positions_per_symbol: int = 1


@dataclass
class RiskPolicy:
    """Unified risk policy combining hard and soft limits."""
    name: str = "default"
    hard: HardLimits = field(default_factory=HardLimits)
    soft: SoftLimits = field(default_factory=SoftLimits)


# ── YOLO profile presets ──
# Mapped from auto_trader.py YOLO_PROFILES (levels 1-5)

RISK_PRESETS: Dict[str, RiskPolicy] = {
    "cautious": RiskPolicy(
        name="cautious",
        hard=HardLimits(
            max_position_size_pct=10.0,
            require_stop_loss=True,
        ),
        soft=SoftLimits(
            conviction_floor=60,
            max_trades_per_day=3,
            cooldown_seconds=2700.0,
            base_pct=5.0,
            penalty_multiplier=1.5,
            rejection_cooldown_hours=4.0,
            max_positions_per_symbol=1,
        ),
    ),
    "balanced": RiskPolicy(
        name="balanced",
        hard=HardLimits(
            max_position_size_pct=15.0,
            require_stop_loss=True,
        ),
        soft=SoftLimits(
            conviction_floor=55,
            max_trades_per_day=4,
            cooldown_seconds=1800.0,
            base_pct=10.0,
            penalty_multiplier=1.0,
            rejection_cooldown_hours=2.0,
            max_positions_per_symbol=1,
        ),
    ),
    "aggressive": RiskPolicy(
        name="aggressive",
        hard=HardLimits(
            max_position_size_pct=20.0,
            require_stop_loss=True,
        ),
        soft=SoftLimits(
            conviction_floor=45,
            max_trades_per_day=8,
            cooldown_seconds=900.0,
            base_pct=12.0,
            penalty_multiplier=0.5,
            rejection_cooldown_hours=0.5,
            max_positions_per_symbol=2,
        ),
    ),
    "yolo": RiskPolicy(
        name="yolo",
        hard=HardLimits(
            max_position_size_pct=25.0,
            require_stop_loss=False,
        ),
        soft=SoftLimits(
            conviction_floor=35,
            max_trades_per_day=12,
            cooldown_seconds=300.0,
            base_pct=15.0,
            penalty_multiplier=0.25,
            rejection_cooldown_hours=0.25,
            max_positions_per_symbol=3,
        ),
    ),
    "full_send": RiskPolicy(
        name="full_send",
        hard=HardLimits(
            max_position_size_pct=25.0,
            require_stop_loss=False,
        ),
        soft=SoftLimits(
            conviction_floor=25,
            max_trades_per_day=20,
            cooldown_seconds=0.0,
            base_pct=20.0,
            penalty_multiplier=0.0,
            rejection_cooldown_hours=0.0,
            max_positions_per_symbol=4,
        ),
    ),
}

# Map YOLO level integers (1-5) to preset names for backward compat
YOLO_LEVEL_MAP: Dict[int, str] = {
    1: "cautious",
    2: "balanced",
    3: "aggressive",
    4: "yolo",
    5: "full_send",
}


def get_preset(level: int) -> RiskPolicy:
    """Get a RiskPolicy preset by YOLO level (1-5)."""
    name = YOLO_LEVEL_MAP.get(level, "balanced")
    return RISK_PRESETS[name]


def enforce_hard(recommendation: dict, policy: RiskPolicy, portfolio_state: dict) -> Tuple[bool, Optional[str]]:
    """Binary hard limit check. Returns (passed, fail_reason).

    These checks cannot be overridden. A failure means the trade is rejected.
    """
    hard = policy.hard

    # Check position count
    open_positions = portfolio_state.get("open_positions", 0)
    if open_positions >= hard.max_positions:
        return False, f"Max positions reached ({open_positions}/{hard.max_positions})"

    # Check position size
    size_pct = recommendation.get("size_pct", 0)
    if size_pct > hard.max_position_size_pct:
        return False, f"Position size {size_pct}% exceeds max {hard.max_position_size_pct}%"

    if recommendation.get("size_usd", 0) > 0 and recommendation["size_usd"] < hard.min_position_size_usd:
        return False, f"Position size below minimum ${hard.min_position_size_usd}"

    # Check direction
    if recommendation.get("direction") == "wait":
        return False, "Direction is 'wait'"

    # Check stop loss
    if hard.require_stop_loss and not recommendation.get("stop_loss"):
        return False, "No stop_loss defined (required)"

    # Check conviction absolute minimum (below any soft floor)
    conviction = recommendation.get("conviction", 0)
    if conviction < 20:
        return False, f"Conviction {conviction} below absolute minimum (20)"

    # Check drawdown (CRITICAL threshold from circuit_breaker)
    drawdown = portfolio_state.get("current_drawdown_pct", 0)
    if drawdown >= hard.max_drawdown_pct:
        return False, f"Drawdown {drawdown:.1f}% exceeds max {hard.max_drawdown_pct}%"

    # Check daily PnL (CRITICAL threshold from circuit_breaker)
    daily_pnl_pct = portfolio_state.get("daily_pnl_pct", 0)
    if daily_pnl_pct <= hard.daily_pnl_floor_pct:
        return False, f"Daily PnL {daily_pnl_pct:.1f}% hit floor {hard.daily_pnl_floor_pct}%"

    # Check margin usage
    margin_usage_pct = portfolio_state.get("margin_usage_pct", 0)
    if margin_usage_pct > hard.max_margin_usage_pct:
        return False, f"Margin usage {margin_usage_pct:.1f}% exceeds max {hard.max_margin_usage_pct}%"

    return True, None


def apply_soft(recommendation: dict, policy: RiskPolicy, market_state: dict) -> dict:
    """Apply soft conviction penalties. Returns adjusted recommendation.

    Penalties are scaled by policy.soft.penalty_multiplier.
    """
    soft = policy.soft
    conviction = recommendation.get("conviction", 0)
    penalties: List[str] = []

    # Conviction floor check (soft reject, not hard)
    if conviction < soft.conviction_floor:
        penalties.append(f"Below conviction floor ({conviction} < {soft.conviction_floor})")
        recommendation["vetoed"] = True
        recommendation["veto_reasons"] = penalties
        return recommendation

    mult = soft.penalty_multiplier

    # Vol regime penalty
    vol_regime = market_state.get("vol_regime", "")
    if vol_regime in ("high", "extreme"):
        penalty = int(soft.high_vol_penalty * mult)
        if penalty > 0:
            conviction -= penalty
            penalties.append(f"High vol regime: -{penalty}")

    # Circuit breaker state penalty
    cb_state = market_state.get("circuit_breaker_state", "ACTIVE")
    if cb_state == "SUSPENDED":
        penalty = int(soft.suspended_state_penalty * mult)
        if penalty > 0:
            conviction -= penalty
            penalties.append(f"Circuit breaker SUSPENDED: -{penalty}")

    # EMA distance penalty
    ema_distance_pct = market_state.get("ema_distance_pct", 0)
    if abs(ema_distance_pct) > 5.0:
        penalty = int(soft.ema_distance_penalty * mult)
        if penalty > 0:
            conviction -= penalty
            penalties.append(f"EMA distance {ema_distance_pct:.1f}%: -{penalty}")
    elif abs(ema_distance_pct) > 3.0:
        penalty = int(soft.ema_extended_penalty * mult)
        if penalty > 0:
            conviction -= penalty
            penalties.append(f"EMA distance {ema_distance_pct:.1f}%: -{penalty}")

    # VWAP distance penalty
    vwap_distance_pct = market_state.get("vwap_distance_pct", 0)
    if abs(vwap_distance_pct) > 10.0:
        penalty = int(soft.vwap_extreme_penalty * mult)
        if penalty > 0:
            conviction -= penalty
            penalties.append(f"VWAP distance {vwap_distance_pct:.1f}%: -{penalty}")
    elif abs(vwap_distance_pct) > 5.0:
        penalty = int(soft.vwap_extended_penalty * mult)
        if penalty > 0:
            conviction -= penalty
            penalties.append(f"VWAP distance {vwap_distance_pct:.1f}%: -{penalty}")

    # Trades per day check
    trades_today = market_state.get("trades_today", 0)
    if trades_today >= soft.max_trades_per_day:
        conviction -= 20
        penalties.append(f"Trades today ({trades_today}) at limit: -20")

    # Recent rejection penalty
    recently_rejected = market_state.get("recently_rejected", False)
    if recently_rejected:
        penalty = int(soft.recent_rejection_penalty * mult)
        if penalty > 0:
            conviction -= penalty
            penalties.append(f"Recently rejected: -{penalty}")

    recommendation["conviction"] = max(conviction, 0)
    recommendation["soft_penalties"] = penalties

    # Re-check against floor after penalties
    if conviction < soft.conviction_floor:
        recommendation["vetoed"] = True
        recommendation["veto_reasons"] = [
            f"Conviction {conviction} below floor {soft.conviction_floor} after penalties"
        ] + penalties

    return recommendation
