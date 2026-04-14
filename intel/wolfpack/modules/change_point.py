"""Fast-path change-point confirmer for WolfPack regime flips.

Sits beside the 3-tick debounce in ``regime_router.py``. On a 5-minute tick
cadence the existing debounce costs ~15 min of lag before a regime flip is
committed. This module adds a fast-confirm path that cuts that to ~5-10 min on
sharp shifts while the 3-tick debounce remains the safety fallback for gradual
drift.

Design is a direct implementation of the research doc:
``docs/research/regime/05-change-point-detection.md``

Two independent detectors run in parallel:
  1. **Page-Hinkley** (one-sided CUSUM variant) on a weighted ``trend_score``.
     Pure in-file implementation — we intentionally avoid the ``river``
     dependency. Formula from Page (1954) + River's reference impl.
  2. **Classical two-sided CUSUM** on ``direction_score``. Independent signal
     so "both detectors agree" is strong evidence of a real shift.

A hard gate on ATR expansion + volume spike (the crypto "transition signature")
guards the fast path. Both detectors agreeing AND the gate passing is what
triggers ``fast_path_confirm``. Either missing -> slow path / existing debounce.

Integration in regime_router.route_strategies():
    cp = _change_point_detectors.get(symbol) or ChangePointDetector()
    result = cp.update(trend_score, direction_score, atr_14, atr_48_med, vol, vol_20_med)
    if result.fast_path_confirm:
        # Commit pending regime immediately, skip remaining debounce ticks
        state.pending_count = DEBOUNCE_TICKS
        cp.reset()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Tuple


# ---------------------------------------------------------------------------
# Page-Hinkley state (one-sided CUSUM, symmetric pair for up/down)
# ---------------------------------------------------------------------------


@dataclass
class PageHinkleyState:
    """State for the Page-Hinkley test (Page 1954, River reference impl).

    Maintains a forgetting-factor running mean and twin cumulative deviations
    ``u_plus`` / ``u_minus`` plus their extrema for the ``U_t - min(U)`` test.
    """

    mean: float = 0.0
    n: int = 0
    u_plus: float = 0.0
    u_minus: float = 0.0
    u_plus_min: float = 0.0
    u_minus_max: float = 0.0

    def update(self, x: float, delta: float = 0.005, alpha: float = 0.9995) -> None:
        if not math.isfinite(x):
            return
        self.n += 1
        if self.n == 1:
            self.mean = x
        else:
            self.mean = alpha * self.mean + (1.0 - alpha) * x
        dev = x - self.mean
        self.u_plus = max(0.0, self.u_plus + dev - delta)
        self.u_minus = min(0.0, self.u_minus + dev + delta)
        if self.u_plus < self.u_plus_min:
            self.u_plus_min = self.u_plus
        if self.u_minus > self.u_minus_max:
            self.u_minus_max = self.u_minus

    def fired(self, lambda_threshold: float = 10.0, min_instances: int = 12) -> str:
        """Return 'up', 'down', or '' (no fire / still warming up)."""
        if self.n < min_instances:
            return ""
        if (self.u_plus - self.u_plus_min) > lambda_threshold:
            return "up"
        if (self.u_minus_max - self.u_minus) > lambda_threshold:
            return "down"
        return ""

    def reset(self) -> None:
        self.u_plus = 0.0
        self.u_minus = 0.0
        self.u_plus_min = 0.0
        self.u_minus_max = 0.0


# ---------------------------------------------------------------------------
# Classical two-sided CUSUM on direction_score
# ---------------------------------------------------------------------------


@dataclass
class CusumState:
    """Standard Page CUSUM with symmetric S+ / S- accumulators.

    Parameters follow the research doc: ``k=0.2`` (half of delta_min=0.4),
    ``h=1.6`` (≈ 4 * observed sigma of direction_score ~ 0.4) giving
    ARL_0 ≈ 500 ticks (~40h at 5-minute cadence).
    """

    s_plus: float = 0.0
    s_minus: float = 0.0
    n: int = 0

    def update(
        self,
        x: float,
        k: float = 0.2,
        h: float = 1.6,
        min_instances: int = 12,
    ) -> str:
        if not math.isfinite(x):
            return ""
        self.n += 1
        # mu_0 = 0 (no trend) — direction_score is already centered in [-1, 1]
        self.s_plus = max(0.0, self.s_plus + x - k)
        self.s_minus = min(0.0, self.s_minus + x + k)
        if self.n < min_instances:
            return ""
        if self.s_plus > h:
            return "up"
        if self.s_minus < -h:
            return "down"
        return ""

    def reset(self) -> None:
        self.s_plus = 0.0
        self.s_minus = 0.0


# ---------------------------------------------------------------------------
# Hard gate: crypto transition signature (ATR expansion + volume spike)
# ---------------------------------------------------------------------------


def _hard_gate(
    atr_14: float,
    atr_48_median: float,
    volume: float,
    volume_20_median: float,
) -> Tuple[bool, float, float]:
    """Return (passed, atr_ratio, vol_ratio). NaN-safe. See research doc §4."""
    vals = (atr_14, atr_48_median, volume, volume_20_median)
    if any((v is None) or (not math.isfinite(v)) for v in vals):
        return False, 0.0, 0.0
    if atr_48_median <= 0 or volume_20_median <= 0:
        return False, 0.0, 0.0
    atr_ratio = atr_14 / atr_48_median
    vol_ratio = volume / volume_20_median
    return (atr_ratio >= 1.3 and vol_ratio >= 1.5), atr_ratio, vol_ratio


# ---------------------------------------------------------------------------
# Public result + detector
# ---------------------------------------------------------------------------


@dataclass
class ChangePointResult:
    fast_path_confirm: bool
    page_hinkley_fired: bool
    cusum_fired: bool
    hard_gate_passed: bool
    direction: str  # "up" | "down" | "none"
    reason: str


@dataclass
class ChangePointDetector:
    """One detector per symbol. Holds PH + CUSUM state.

    Fast-path confirm requires: both detectors fired AND hard gate passed AND
    both detectors agree on direction.
    """

    ph: PageHinkleyState = field(default_factory=PageHinkleyState)
    cusum: CusumState = field(default_factory=CusumState)

    def update(
        self,
        trend_score: float,
        direction_score: float,
        atr_14: float,
        atr_48_median: float,
        volume: float,
        volume_20_median: float,
    ) -> ChangePointResult:
        """Feed one tick of features and return the change-point verdict."""
        # Advance both detectors independently (they run on different inputs).
        self.ph.update(trend_score)
        ph_dir = self.ph.fired()
        cu_dir = self.cusum.update(direction_score)

        gate_ok, atr_ratio, vol_ratio = _hard_gate(
            atr_14, atr_48_median, volume, volume_20_median
        )

        ph_fired = bool(ph_dir)
        cu_fired = bool(cu_dir)
        both_agree = ph_fired and cu_fired and (ph_dir == cu_dir)

        if both_agree and gate_ok:
            return ChangePointResult(
                fast_path_confirm=True,
                page_hinkley_fired=True,
                cusum_fired=True,
                hard_gate_passed=True,
                direction=ph_dir,
                reason=f"both_fire_{ph_dir}+atr{atr_ratio:.2f}x+vol{vol_ratio:.2f}x",
            )

        if not (ph_fired or cu_fired):
            reason = "no_fire"
        elif ph_fired and cu_fired and not both_agree:
            reason = f"direction_disagree_ph={ph_dir}_cusum={cu_dir}"
        elif not gate_ok and (ph_fired or cu_fired):
            reason = f"signatures_absent(atr{atr_ratio:.2f}x,vol{vol_ratio:.2f}x)"
        else:
            only = ph_dir or cu_dir
            reason = f"single_detector_only_{only}"

        return ChangePointResult(
            fast_path_confirm=False,
            page_hinkley_fired=ph_fired,
            cusum_fired=cu_fired,
            hard_gate_passed=gate_ok,
            direction=(ph_dir or cu_dir or "none"),
            reason=reason,
        )

    def reset(self) -> None:
        """Clear detector state after a confirmed regime flip."""
        self.ph.reset()
        self.cusum.reset()


# ---------------------------------------------------------------------------
# Smoke test — synthetic trend shift, assert detector fires
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import random

    random.seed(42)
    det = ChangePointDetector()

    # 30 ticks of flat chop around 0, then a sharp positive shift.
    fired_tick = None
    first_result = None
    for t in range(80):
        if t < 30:
            trend = random.gauss(0.0, 0.05)
            direction = random.gauss(0.0, 0.1)
            atr_14, atr_48m = 1.0, 1.0
            vol, vol_20m = 1.0, 1.0
        else:
            # Sharp regime flip: trend + direction jump, ATR expands, volume spikes.
            trend = random.gauss(0.6, 0.05)
            direction = random.gauss(0.7, 0.1)
            atr_14, atr_48m = 1.6, 1.0  # 1.6x (>=1.3 gate)
            vol, vol_20m = 2.0, 1.0      # 2.0x (>=1.5 gate)

        result = det.update(trend, direction, atr_14, atr_48m, vol, vol_20m)
        if result.fast_path_confirm and fired_tick is None:
            fired_tick = t
            first_result = result
            break

    assert fired_tick is not None, "detector never fired on a clear trend shift"
    assert 30 <= fired_tick <= 50, f"fired at tick {fired_tick}, expected 30-50"
    assert first_result.direction == "up", f"expected up, got {first_result.direction}"
    print(f"[ok] change-point fired at tick {fired_tick} ({fired_tick - 30} after shift)")
    print(f"[ok] direction={first_result.direction} reason={first_result.reason}")

    # Reset and verify state is clean.
    det.reset()
    assert det.ph.u_plus == 0.0 and det.cusum.s_plus == 0.0
    print("[ok] reset() cleared detector state")
