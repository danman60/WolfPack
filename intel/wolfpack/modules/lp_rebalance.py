"""LP Rebalance Engine — debounced rebalance triggers for LP positions.

Cooldown state persisted to DB so it survives service restarts.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

REBALANCE_DEBOUNCE_TICKS = 3   # consecutive OOR ticks before rebalance
REBALANCE_COOLDOWN_MINUTES = 120  # 2 hours between rebalances per pool
IL_REBALANCE_THRESHOLD = 5.0   # IL % that triggers rebalance


@dataclass
class RebalanceState:
    pool_address: str
    out_of_range_count: int = 0
    last_rebalance_at: datetime | None = None
    total_rebalances: int = 0


class LPRebalanceEngine:
    def __init__(self):
        self._states: dict[str, RebalanceState] = {}
        self._restored = False

    def _restore_from_db(self) -> None:
        """Load last rebalance timestamps from wp_lp_events on first use."""
        if self._restored:
            return
        self._restored = True
        try:
            from wolfpack.db import get_db
            db = get_db()
            # Get the most recent rebalance per pool
            result = (
                db.table("wp_lp_events")
                .select("details, created_at")
                .eq("event_type", "rebalance")
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            )
            seen_pools: set[str] = set()
            for row in (result.data or []):
                pool = (row.get("details") or {}).get("pool", "")
                if pool and pool not in seen_pools:
                    seen_pools.add(pool)
                    state = self._get_state(pool)
                    ts = row.get("created_at", "")
                    if ts:
                        state.last_rebalance_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if seen_pools:
                logger.info(f"[rebalance] Restored cooldown state for {len(seen_pools)} pools from DB")
        except Exception as e:
            logger.warning(f"[rebalance] Failed to restore from DB: {e}")

    def evaluate(self, position, recommended_range, pool_address: str = "") -> dict | None:
        """Evaluate if position needs rebalancing.

        Respects time-based cooldown (persisted to DB, survives restarts).
        """
        self._restore_from_db()
        state_key = pool_address or position.pool_address
        state = self._get_state(state_key)

        # Check cooldown — time-based, not tick-based
        if state.last_rebalance_at:
            elapsed = (datetime.now(timezone.utc) - state.last_rebalance_at).total_seconds() / 60
            if elapsed < REBALANCE_COOLDOWN_MINUTES:
                return None

        # Trigger 1: Out of range (debounced)
        in_range = position.tick_lower <= position.current_tick <= position.tick_upper
        if not in_range:
            state.out_of_range_count += 1
            if state.out_of_range_count >= REBALANCE_DEBOUNCE_TICKS:
                return self._build_rebalance_action(position, recommended_range, "out_of_range", state)
        else:
            state.out_of_range_count = 0

        # Trigger 2: IL threshold
        if abs(position.il_pct) >= IL_REBALANCE_THRESHOLD:
            return self._build_rebalance_action(position, recommended_range, "il_threshold", state)

        # Trigger 3: Range width shift >50%
        if recommended_range:
            current_width = position.tick_upper - position.tick_lower
            new_width = recommended_range.tick_upper - recommended_range.tick_lower
            if current_width > 0 and abs(new_width - current_width) / current_width > 0.50:
                return self._build_rebalance_action(position, recommended_range, "vol_shift", state)

        return None

    def record_rebalance(self, position_id: str, pool_address: str = ""):
        """Record that a rebalance was executed. Timestamp persisted via event storage."""
        state_key = pool_address or position_id
        state = self._get_state(state_key)
        state.last_rebalance_at = datetime.now(timezone.utc)
        state.total_rebalances += 1
        state.out_of_range_count = 0

    def _get_state(self, key: str) -> RebalanceState:
        if key not in self._states:
            self._states[key] = RebalanceState(pool_address=key)
        return self._states[key]

    def _build_rebalance_action(self, position, recommended_range, reason: str, state: RebalanceState) -> dict:
        return {
            "action": "rebalance",
            "position_id": position.position_id,
            "pool_address": position.pool_address,
            "pair": f"{position.token0_symbol}/{position.token1_symbol}",
            "old_range": [position.tick_lower, position.tick_upper],
            "new_range": [recommended_range.tick_lower, recommended_range.tick_upper] if recommended_range else None,
            "reason": reason,
            "il_pct": position.il_pct,
            "out_of_range_ticks": state.out_of_range_count,
        }
