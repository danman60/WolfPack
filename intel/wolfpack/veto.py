"""BriefVeto — post-Brief filtering layer that blocks or adjusts recommendations.

Sits between Brief output and DB storage. Ensures recommendations meet
minimum quality standards before being presented to the user.
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from wolfpack.risk_controls import HardLimits, SoftLimits, RISK_PRESETS

logger = logging.getLogger(__name__)

# Default limits for parameter defaults
_hard = HardLimits()
_soft = SoftLimits()


def _write_veto_audit_row(
    cycle_id: str | None,
    symbol: str,
    direction: str,
    raw_conviction: int,
    adjusted_conviction: int,
    penalties: dict,
    action: str,
    reject_reason: list[str],
    cooldown_expires_at: datetime | None,
) -> None:
    """Insert a row into wp_veto_log. Never raises — logs failures to stderr."""
    try:
        from wolfpack.db import get_db
        db = get_db()
        row = {
            "cycle_id": cycle_id,
            "symbol": symbol,
            "direction": direction,
            "raw_conviction": int(raw_conviction or 0),
            "adjusted_conviction": int(adjusted_conviction or 0),
            "penalties": penalties or {},
            "action": action,
            "reject_reason": reject_reason or [],
            "cooldown_expires_at": cooldown_expires_at.isoformat() if cooldown_expires_at else None,
        }
        db.table("wp_veto_log").insert(row).execute()
    except Exception as e:
        try:
            print(f"[veto_audit] failed to insert veto log row: {e}", file=sys.stderr, flush=True)
        except Exception:
            pass


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
        conviction_floor: int | None = None,
        penalty_multiplier: float | None = None,
        rejection_cooldown_hours: float | None = None,
        require_stop_loss: bool | None = None,
        profile: str | None = None,
    ) -> None:
        """Construct a BriefVeto.

        Phase 1 (1.6): when `profile` is given (e.g. "balanced"), resolve
        defaults from RISK_PRESETS[profile] instead of module-level
        SoftLimits()/HardLimits(). Explicit kwargs still override the
        preset when present — preserving backward compat with call sites
        in auto_trader.py that pass individual YOLO-profile values.
        """
        if profile and profile in RISK_PRESETS:
            preset = RISK_PRESETS[profile]
            base_soft = preset.soft
            base_hard = preset.hard
        else:
            base_soft = _soft
            base_hard = _hard

        # Track recent rejections: {symbol: datetime}
        self._recent_rejections: dict[str, datetime] = {}
        self._conviction_floor = (
            conviction_floor if conviction_floor is not None else base_soft.conviction_floor
        )
        self._penalty_multiplier = (
            penalty_multiplier if penalty_multiplier is not None else base_soft.penalty_multiplier
        )
        self._rejection_cooldown_hours = (
            rejection_cooldown_hours
            if rejection_cooldown_hours is not None
            else base_soft.rejection_cooldown_hours
        )
        self._require_stop_loss = (
            require_stop_loss if require_stop_loss is not None else base_hard.require_stop_loss
        )
        self._profile_name = profile or "default"

    def evaluate(
        self,
        rec: dict,
        cb_output: dict | None = None,
        vol_output: dict | None = None,
        quant_signals: list[dict] | None = None,
        cycle_id: str | None = None,
    ) -> VetoResult:
        """Evaluate a single recommendation.

        Args:
            rec: Recommendation dict from Brief agent
            cb_output: Circuit breaker output dict (optional)
            vol_output: Volatility module output dict (optional)
            quant_signals: Quant agent signal list (optional) — used for EMA/VWAP extension check
            cycle_id: Phase 1 telemetry — if set, every evaluation writes one
                row to wp_veto_log. Backward compatible — None is allowed and
                still writes a row (with null cycle_id).

        Returns:
            VetoResult with action, adjusted conviction, and reasons.
        """
        direction = rec.get("direction", "wait")
        conviction = rec.get("conviction", 0)
        raw_conviction = conviction
        stop_loss = rec.get("stop_loss")
        size_pct = rec.get("size_pct", 0)
        symbol = rec.get("symbol", "UNKNOWN")

        reasons: list[str] = []
        penalties: dict[str, int] = {}

        def _audit(
            action: str,
            adjusted_conv: int,
            reasons_list: list[str],
            *,
            with_cooldown: bool = False,
        ) -> None:
            cooldown_expiry: datetime | None = None
            if with_cooldown and self._rejection_cooldown_hours > 0:
                cooldown_expiry = datetime.now(timezone.utc) + timedelta(
                    hours=self._rejection_cooldown_hours
                )
            _write_veto_audit_row(
                cycle_id=cycle_id,
                symbol=symbol,
                direction=direction,
                raw_conviction=int(raw_conviction or 0),
                adjusted_conviction=int(adjusted_conv or 0),
                penalties=penalties,
                action=action,
                reject_reason=reasons_list if action == "reject" else [],
                cooldown_expires_at=cooldown_expiry,
            )

        # ── Hard veto rules (reject immediately) ──

        if direction == "wait":
            # Do NOT record a rejection for 'wait' — it's a signal-neutral
            # decision from Brief ("no setup right now"), not a symbol
            # failure. Recording it caused any symbol that ever got a 'wait'
            # to enter a 2h cooldown, then the next directional rec for
            # that symbol would hit the -20 penalty and fall below the
            # 55 floor, creating a chronic lockout.
            reasons.append("direction is 'wait'")
            _audit("reject", 0, reasons, with_cooldown=False)
            return VetoResult(
                action="reject",
                original_conviction=conviction,
                final_conviction=0,
                reasons=reasons,
            )

        if conviction < self._conviction_floor:
            reasons.append(f"conviction {conviction} < {self._conviction_floor} minimum")
            self._record_rejection(symbol)
            _audit("reject", 0, reasons, with_cooldown=True)
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
                _audit("reject", 0, reasons, with_cooldown=True)
                return VetoResult(
                    action="reject",
                    original_conviction=conviction,
                    final_conviction=0,
                    reasons=reasons,
                )
            else:
                # Soft penalty instead of hard reject
                conviction -= 10
                penalties["no_stop_loss"] = 10
                reasons.append("no stop_loss defined — soft penalty -10 conviction")

        if size_pct and size_pct > _hard.max_position_size_pct:
            reasons.append(f"size_pct {size_pct}% > {_hard.max_position_size_pct}% maximum")
            self._record_rejection(symbol)
            _audit("reject", 0, reasons, with_cooldown=True)
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
                penalties["vol_regime"] = penalty
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
                penalties["cb_suspended"] = penalty
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
                        penalties["ema_overextended"] = penalty
                        reasons.append(f"price {dist:.1f}% from 9 EMA (overextended): -{penalty} conviction")
                    elif dist > 3:
                        penalty = int(8 * self._penalty_multiplier)
                        adjusted -= penalty
                        penalties["ema_extended"] = penalty
                        reasons.append(f"price {dist:.1f}% from 9 EMA (extended): -{penalty} conviction")
                elif indicator == "VWAP_dist_pct":
                    dist = abs(float(sig.get("value", 0)))
                    if dist > 10:
                        penalty = int(15 * self._penalty_multiplier)
                        adjusted -= penalty
                        penalties["vwap_extreme"] = penalty
                        reasons.append(f"price {dist:.1f}% from VWAP (extreme extension): -{penalty} conviction")
                    elif dist > 5:
                        penalty = int(5 * self._penalty_multiplier)
                        adjusted -= penalty
                        penalties["vwap_extended"] = penalty
                        reasons.append(f"price {dist:.1f}% from VWAP (extended): -{penalty} conviction")

        # Recent rejection penalty
        if self._recently_rejected(symbol):
            penalty = int(20 * self._penalty_multiplier)
            adjusted -= penalty
            penalties["recent_rejection"] = penalty
            reasons.append(f"{symbol} rejected within last {self._rejection_cooldown_hours}h: -{penalty} conviction")

        # Check if adjusted conviction still passes threshold
        if adjusted < self._conviction_floor:
            reasons.append(f"adjusted conviction {adjusted} < {self._conviction_floor} after penalties")
            self._record_rejection(symbol)
            _audit("reject", adjusted, reasons, with_cooldown=True)
            return VetoResult(
                action="reject",
                original_conviction=conviction,
                final_conviction=adjusted,
                reasons=reasons,
            )

        action = "adjust" if adjusted != conviction else "pass"
        _audit(action, adjusted, reasons, with_cooldown=False)
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
