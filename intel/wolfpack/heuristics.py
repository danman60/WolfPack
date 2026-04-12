"""Phase 3: Human Heuristics — emotional state machine for v3 wallet.

Pure Python. No coupling to the trading engine, no globals, no singletons.
Unit-testable. All DB reads/writes go through the ``db`` argument so the
class can be exercised with a mock.

State is stored per-wallet in ``wp_wallet_state`` and every mutation
appends a row to ``wp_wallet_state_history``. Feature-flagged at the
caller level via ``wallet.config.heuristics_enabled`` — v1/v2 wallets
get default rows but nothing reads from them unless the flag is set.

Drives (all in [0, 1]):
    hunger        — 0 satisfied, 1 desperate for P&L
    satisfaction  — 0 frustrated, 1 content (target met)
    fear          — 0 reckless, 1 risk-averse
    curiosity     — 0 stick to known, 1 explore unknowns
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

BASELINE = 0.5


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class HeuristicState:
    wallet_id: str
    hunger: float = 0.5
    satisfaction: float = 0.5
    fear: float = 0.5
    curiosity: float = 0.5
    loss_streak: int = 0
    win_streak: int = 0
    daily_pnl_target: float = 0.0
    last_updated: datetime | None = None

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def decay(self, cycles: int = 1, half_life_cycles: float = 20.0) -> None:
        """Exponentially pull all 4 drives toward the 0.5 baseline.

        After ``half_life_cycles`` calls (default ~20 intel cycles ≈ 30 min),
        each drive is halfway back to 0.5. Result is clamped to [0, 1].
        """
        if cycles <= 0 or half_life_cycles <= 0:
            return
        # half-life decay: factor = 0.5 ** (cycles / half_life_cycles)
        factor = 0.5 ** (cycles / half_life_cycles)
        for name in ("hunger", "satisfaction", "fear", "curiosity"):
            current = getattr(self, name)
            new = BASELINE + (current - BASELINE) * factor
            setattr(self, name, _clamp(new))

    def on_target_progress(self, daily_pnl: float, target: float) -> None:
        """Update hunger/satisfaction from P&L progress toward daily target.

        - progress >= 1.0 → satisfaction=1.0, hunger=0.1
        - progress < 0    → hunger += 0.15 (cap 1), satisfaction=0.1
        - else            → linear interpolation in [0, 1]
        - target == 0     → no-op (edge)
        """
        if target == 0:
            return
        progress = daily_pnl / target
        if progress >= 1.0:
            self.satisfaction = 1.0
            self.hunger = 0.1
        elif progress < 0:
            self.hunger = _clamp(self.hunger + 0.15)
            self.satisfaction = 0.1
        else:
            # Linear: at progress=0 hunger=0.8/satisfaction=0.2,
            # at progress=1 hunger=0.1/satisfaction=1.0
            self.hunger = _clamp(0.8 - 0.7 * progress)
            self.satisfaction = _clamp(0.2 + 0.8 * progress)

    def on_trade_close(self, pnl: float, hold_hours: float) -> None:
        """Update streaks / fear / satisfaction from a closed trade result."""
        del hold_hours  # reserved for future use (longer holds = less emotional)
        if pnl > 0:
            self.win_streak += 1
            self.loss_streak = 0
            self.satisfaction = _clamp(self.satisfaction + 0.08)
            self.fear = _clamp(self.fear - 0.05)
        elif pnl < 0:
            self.loss_streak += 1
            self.win_streak = 0
            self.fear = _clamp(self.fear + 0.1)
            self.satisfaction = _clamp(self.satisfaction - 0.05)
            if self.loss_streak >= 3:
                self.fear = _clamp(self.fear + 0.15)
        # pnl == 0 is a no-op (scratch trade)

    def on_unfamiliar_setup(self, tier: str) -> None:
        """Bump curiosity when PerformanceTracker has no edge data for a setup."""
        if tier == "none":
            self.curiosity = _clamp(self.curiosity + 0.02)

    # ------------------------------------------------------------------
    # Read-only modifiers used by the trading engine
    # ------------------------------------------------------------------

    def conviction_modifier(self) -> int:
        """±int delta to add to the base conviction floor.

        hunger lowers floor (take more), fear raises floor (be picky),
        satisfaction slightly raises floor (protect gains).
        Clamped to [-12, +20].
        """
        raw = -10 * self.hunger + 15 * self.fear + 5 * self.satisfaction
        return int(max(-12, min(20, round(raw))))

    def size_modifier(self) -> float:
        """Position size multiplier in [0.3, 1.35]."""
        raw = 1.0 + 0.25 * self.hunger - 0.4 * self.fear + 0.15 * self.curiosity
        return max(0.3, min(1.35, raw))

    def exploration_budget(self) -> float:
        """0-1 budget for curiosity-gated exploratory positions."""
        return _clamp(self.curiosity * (1.0 - self.fear))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Serialize for a DB upsert into wp_wallet_state."""
        return {
            "wallet_id": self.wallet_id,
            "hunger": float(self.hunger),
            "satisfaction": float(self.satisfaction),
            "fear": float(self.fear),
            "curiosity": float(self.curiosity),
            "loss_streak": int(self.loss_streak),
            "win_streak": int(self.win_streak),
            "daily_pnl_target": float(self.daily_pnl_target),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # DB adapters
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, wallet_id: str, db: Any) -> "HeuristicState":
        """Fetch from wp_wallet_state. Insert defaults if no row exists."""
        result = (
            db.table("wp_wallet_state")
            .select("*")
            .eq("wallet_id", wallet_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if rows:
            row = rows[0]
            last_updated = row.get("last_updated")
            if isinstance(last_updated, str):
                try:
                    last_updated = datetime.fromisoformat(
                        last_updated.replace("Z", "+00:00")
                    )
                except Exception:
                    last_updated = None
            return cls(
                wallet_id=wallet_id,
                hunger=float(row.get("hunger", 0.5)),
                satisfaction=float(row.get("satisfaction", 0.5)),
                fear=float(row.get("fear", 0.5)),
                curiosity=float(row.get("curiosity", 0.5)),
                loss_streak=int(row.get("loss_streak", 0)),
                win_streak=int(row.get("win_streak", 0)),
                daily_pnl_target=float(row.get("daily_pnl_target", 0.0)),
                last_updated=last_updated,
            )

        # Fresh default row
        fresh = cls(wallet_id=wallet_id)
        db.table("wp_wallet_state").upsert(
            fresh.snapshot(), on_conflict="wallet_id"
        ).execute()
        return fresh

    def save(
        self,
        db: Any,
        event: str | None = None,
        daily_pnl: float = 0.0,
        equity: float = 0.0,
    ) -> None:
        """Upsert current state and append a history row."""
        snap = self.snapshot()
        db.table("wp_wallet_state").upsert(snap, on_conflict="wallet_id").execute()

        history_row = {
            "wallet_id": self.wallet_id,
            "hunger": float(self.hunger),
            "satisfaction": float(self.satisfaction),
            "fear": float(self.fear),
            "curiosity": float(self.curiosity),
            "loss_streak": int(self.loss_streak),
            "win_streak": int(self.win_streak),
            "daily_pnl": float(daily_pnl),
            "equity": float(equity),
            "event": event,
        }
        db.table("wp_wallet_state_history").insert(history_row).execute()
