"""BriefVeto — post-Brief filtering layer that blocks or adjusts recommendations.

Sits between Brief output and DB storage. Ensures recommendations meet
minimum quality standards before being presented to the user.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


@dataclass
class VetoResult:
    """Outcome of a veto evaluation."""

    action: str  # "pass", "reject", "adjust"
    original_conviction: int
    final_conviction: int
    reasons: list[str] = field(default_factory=list)


class BriefVeto:
    """Evaluates Brief recommendations against hard veto rules and soft adjustments.

    Hard veto (reject):
        - direction == "wait"
        - conviction < 55
        - no stop_loss set
        - size_pct > 25

    Soft adjustments (reduce conviction):
        - volatility regime "high" or "extreme": -10
        - circuit breaker recently suspended: -15
        - same symbol rejected within 2h: -20
    """

    def __init__(self) -> None:
        # Track recent rejections: {symbol: datetime}
        self._recent_rejections: dict[str, datetime] = {}

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
            reasons.append("direction is 'wait'")
            self._record_rejection(symbol)
            return VetoResult(
                action="reject",
                original_conviction=conviction,
                final_conviction=0,
                reasons=reasons,
            )

        if conviction < 55:
            reasons.append(f"conviction {conviction} < 55 minimum")
            self._record_rejection(symbol)
            return VetoResult(
                action="reject",
                original_conviction=conviction,
                final_conviction=0,
                reasons=reasons,
            )

        if not stop_loss:
            reasons.append("no stop_loss defined — risk unbounded")
            self._record_rejection(symbol)
            return VetoResult(
                action="reject",
                original_conviction=conviction,
                final_conviction=0,
                reasons=reasons,
            )

        if size_pct and size_pct > 25:
            reasons.append(f"size_pct {size_pct}% > 25% maximum")
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
                adjusted -= 10
                reasons.append(f"vol regime '{vol_regime}': -10 conviction")

        # Circuit breaker penalty
        if cb_output:
            cb_state = ""
            if isinstance(cb_output, dict):
                cb_state = cb_output.get("state", "")
            elif hasattr(cb_output, "state"):
                cb_state = cb_output.state
            if cb_state == "SUSPENDED":
                adjusted -= 15
                reasons.append("circuit breaker SUSPENDED: -15 conviction")

        # EMA/VWAP extension penalty — price overextended from mean
        if quant_signals:
            for sig in quant_signals:
                indicator = sig.get("indicator", "")
                if indicator == "EMA_9_dist_pct":
                    dist = abs(float(sig.get("value", 0)))
                    if dist > 5:
                        adjusted -= 15
                        reasons.append(f"price {dist:.1f}% from 9 EMA (overextended): -15 conviction")
                    elif dist > 3:
                        adjusted -= 8
                        reasons.append(f"price {dist:.1f}% from 9 EMA (extended): -8 conviction")
                elif indicator == "VWAP_dist_pct":
                    dist = abs(float(sig.get("value", 0)))
                    if dist > 10:
                        adjusted -= 15
                        reasons.append(f"price {dist:.1f}% from VWAP (extreme extension): -15 conviction")
                    elif dist > 5:
                        adjusted -= 5
                        reasons.append(f"price {dist:.1f}% from VWAP (extended): -5 conviction")

        # Recent rejection penalty
        if self._recently_rejected(symbol):
            adjusted -= 20
            reasons.append(f"{symbol} rejected within last 2h: -20 conviction")

        # Check if adjusted conviction still passes threshold
        if adjusted < 55:
            reasons.append(f"adjusted conviction {adjusted} < 55 after penalties")
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
        self._recent_rejections[symbol] = datetime.now(timezone.utc)

    def _recently_rejected(self, symbol: str) -> bool:
        last = self._recent_rejections.get(symbol)
        if not last:
            return False
        return datetime.now(timezone.utc) - last < timedelta(hours=2)
