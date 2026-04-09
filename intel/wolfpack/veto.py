"""BriefVeto — post-Brief filtering layer that blocks or adjusts recommendations.

Sits between Brief output and DB storage. Ensures recommendations meet
minimum quality standards before being presented to the user.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from wolfpack.risk_controls import HardLimits, SoftLimits

logger = logging.getLogger(__name__)

# Default limits for parameter defaults
_hard = HardLimits()
_soft = SoftLimits()


@dataclass
class VetoResult:
    """Outcome of a veto evaluation."""

    action: str  # "pass", "reject", "adjust"
    original_conviction: int
    final_conviction: int
    reasons: list[str] = field(default_factory=list)


class BriefVeto:
    """Evaluates Brief recommendations against hard veto rules and soft adjustments.

    All thresholds and penalties are configurable via constructor parameters,
    allowing the YOLO Meter to scale aggressiveness across all throttle layers.

    Hard veto (reject):
        - direction == "wait"
        - conviction < conviction_floor (default 55)
        - no stop_loss set
        - size_pct > 25

    Soft adjustments (reduce conviction, scaled by penalty_multiplier):
        - volatility regime "high" or "extreme"
        - circuit breaker recently suspended
        - same symbol rejected within cooldown window
    """

    def __init__(
        self,
        conviction_floor: int = _soft.conviction_floor,
        penalty_multiplier: float = _soft.penalty_multiplier,
        rejection_cooldown_hours: float = _soft.rejection_cooldown_hours,
        require_stop_loss: bool = _hard.require_stop_loss,
    ) -> None:
        # Track recent rejections: {symbol: datetime}
        self._recent_rejections: dict[str, datetime] = {}
        self._conviction_floor = conviction_floor
        self._penalty_multiplier = penalty_multiplier
        self._rejection_cooldown_hours = rejection_cooldown_hours
        self._require_stop_loss = require_stop_loss

    def evaluate(
        self,
        rec: dict,
        cb_output: dict | None = None,
        vol_output: dict | None = None,
        quant_signals: list[dict] | None = None,
    ) -> VetoResult:
        """Evaluate a single recommendation.

        Args:
            rec: Recommendation dict from Brief agent
            cb_output: Circuit breaker output dict (optional)
            vol_output: Volatility module output dict (optional)
            quant_signals: Quant agent signal list (optional) — used for EMA/VWAP extension check

        Returns:
            VetoResult with action, adjusted conviction, and reasons.
        """
        direction = rec.get("direction", "wait")
        conviction = rec.get("conviction", 0)
        stop_loss = rec.get("stop_loss")
        size_pct = rec.get("size_pct", 0)
        symbol = rec.get("symbol", "UNKNOWN")

        reasons: list[str] = []

        # ── Hard veto rules (reject immediately) ──

        if direction == "wait":
            # Do NOT record a rejection for 'wait' — it's a signal-neutral
            # decision from Brief ("no setup right now"), not a symbol
            # failure. Recording it caused any symbol that ever got a 'wait'
            # to enter a 2h cooldown, then the next directional rec for
            # that symbol would hit the -20 penalty and fall below the
            # 55 floor, creating a chronic lockout.
            reasons.append("direction is 'wait'")
            return VetoResult(
                action="reject",
                original_conviction=conviction,
                final_conviction=0,
                reasons=reasons,
            )

        if conviction < self._conviction_floor:
            reasons.append(f"conviction {conviction} < {self._conviction_floor} minimum")
            self._record_rejection(symbol)
            return VetoResult(
                action="reject",
                original_conviction=conviction,
                final_conviction=0,
                reasons=reasons,
            )

        if not stop_loss:
            if self._require_stop_loss:
                reasons.append("no stop_loss defined — risk unbounded")
                self._record_rejection(symbol)
                return VetoResult(
                    action="reject",
                    original_conviction=conviction,
                    final_conviction=0,
                    reasons=reasons,
                )
            else:
                # Soft penalty instead of hard reject
                conviction -= 10
                reasons.append("no stop_loss defined — soft penalty -10 conviction")

        if size_pct and size_pct > _hard.max_position_size_pct:
            reasons.append(f"size_pct {size_pct}% > {_hard.max_position_size_pct}% maximum")
            self._record_rejection(symbol)
            return VetoResult(
                action="reject",
                original_conviction=conviction,
                final_conviction=0,
                reasons=reasons,
            )

        # ── Soft adjustment rules (reduce conviction) ──

        adjusted = conviction

        # Volatility penalty
        if vol_output:
            vol_regime = ""
            if isinstance(vol_output, dict):
                vol_regime = vol_output.get("vol_regime", "")
            elif hasattr(vol_output, "vol_regime"):
                vol_regime = vol_output.vol_regime
            if vol_regime in ("high", "extreme"):
                penalty = int(10 * self._penalty_multiplier)
                adjusted -= penalty
                reasons.append(f"vol regime '{vol_regime}': -{penalty} conviction")

        # Circuit breaker penalty
        if cb_output:
            cb_state = ""
            if isinstance(cb_output, dict):
                cb_state = cb_output.get("state", "")
            elif hasattr(cb_output, "state"):
                cb_state = cb_output.state
            if cb_state == "SUSPENDED":
                penalty = int(15 * self._penalty_multiplier)
                adjusted -= penalty
                reasons.append(f"circuit breaker SUSPENDED: -{penalty} conviction")

        # EMA/VWAP extension penalty — price overextended from mean
        if quant_signals:
            for sig in quant_signals:
                indicator = sig.get("indicator", "")
                if indicator == "EMA_9_dist_pct":
                    dist = abs(float(sig.get("value", 0)))
                    if dist > 5:
                        penalty = int(15 * self._penalty_multiplier)
                        adjusted -= penalty
                        reasons.append(f"price {dist:.1f}% from 9 EMA (overextended): -{penalty} conviction")
                    elif dist > 3:
                        penalty = int(8 * self._penalty_multiplier)
                        adjusted -= penalty
                        reasons.append(f"price {dist:.1f}% from 9 EMA (extended): -{penalty} conviction")
                elif indicator == "VWAP_dist_pct":
                    dist = abs(float(sig.get("value", 0)))
                    if dist > 10:
                        penalty = int(15 * self._penalty_multiplier)
                        adjusted -= penalty
                        reasons.append(f"price {dist:.1f}% from VWAP (extreme extension): -{penalty} conviction")
                    elif dist > 5:
                        penalty = int(5 * self._penalty_multiplier)
                        adjusted -= penalty
                        reasons.append(f"price {dist:.1f}% from VWAP (extended): -{penalty} conviction")

        # Recent rejection penalty
        if self._recently_rejected(symbol):
            penalty = int(20 * self._penalty_multiplier)
            adjusted -= penalty
            reasons.append(f"{symbol} rejected within last {self._rejection_cooldown_hours}h: -{penalty} conviction")

        # Check if adjusted conviction still passes threshold
        if adjusted < self._conviction_floor:
            reasons.append(f"adjusted conviction {adjusted} < {self._conviction_floor} after penalties")
            self._record_rejection(symbol)
            return VetoResult(
                action="reject",
                original_conviction=conviction,
                final_conviction=adjusted,
                reasons=reasons,
            )

        action = "adjust" if adjusted != conviction else "pass"
        return VetoResult(
            action=action,
            original_conviction=conviction,
            final_conviction=adjusted,
            reasons=reasons,
        )

    def _record_rejection(self, symbol: str) -> None:
        # Do NOT refresh the timer if already in cooldown.
        # Previously this latched symbols out forever: the -20 recent-rejection
        # penalty (line 190) would drop conviction below floor, trigger another
        # rejection at line 197, which refreshed the timer, extending cooldown
        # indefinitely. With this guard, the 2h cooldown is absolute from the
        # FIRST rejection — symbol is guaranteed to escape exactly 2h later.
        if symbol in self._recent_rejections and self._recently_rejected(symbol):
            return
        self._recent_rejections[symbol] = datetime.now(timezone.utc)

    def _recently_rejected(self, symbol: str) -> bool:
        if self._rejection_cooldown_hours <= 0:
            return False
        last = self._recent_rejections.get(symbol)
        if not last:
            return False
        return datetime.now(timezone.utc) - last < timedelta(hours=self._rejection_cooldown_hours)
