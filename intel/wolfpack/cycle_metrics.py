"""CycleMetricsRecorder — async context manager that collects per-cycle telemetry.

Writes one row to wp_cycle_metrics at cycle end. All record methods are
defensive: if no methods are called, an all-defaults row still lands at
__aexit__ time. Insert failures are logged but never re-raised — telemetry
must NEVER break a live trading cycle.

Part of Phase 1 of the profitability + guarantees plan
(/home/danman60/.claude/plans/crystalline-splashing-cerf.md).
"""

from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class CycleMetricsRecorder:
    """Collects metrics for a single intelligence cycle and inserts one row
    into wp_cycle_metrics at exit.

    Usage:
        async with CycleMetricsRecorder() as rec:
            rec.record_symbols_processed(1)
            rec.record_rec("produced")
            ...

    cycle_id is generated on __aenter__ and exposed via the `.cycle_id`
    attribute so callers (veto, auto_trader) can thread it into their
    audit writes.
    """

    def __init__(self) -> None:
        self.cycle_id: str = str(uuid.uuid4())
        self.started_at: datetime = datetime.now(timezone.utc)
        self.finished_at: datetime | None = None

        # Counters
        self.symbols_processed: int = 0
        self.recs_produced: int = 0
        self.recs_veto_rejected: int = 0
        self.recs_veto_adjusted: int = 0
        self.recs_passed: int = 0
        self.sizing_blocked_count: int = 0
        self.positions_opened: int = 0
        self.positions_closed: int = 0

        # Structured aggregates
        self.agent_outputs_stored: dict[str, dict[str, int]] = {}
        self.strategies_activated: dict[str, int] = {}
        self.sizing_blocked_reasons: list[dict[str, Any]] = []
        self.regime_state_per_symbol: dict[str, str] = {}
        self.regime_changed_symbols: list[str] = []

        # Circuit breaker snapshot
        self.cb_state: str | None = None
        self.cb_allow_new_entry: bool | None = None

    # ── Lifecycle ──

    async def __aenter__(self) -> "CycleMetricsRecorder":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.finished_at = datetime.now(timezone.utc)
        duration_ms = int((self.finished_at - self.started_at).total_seconds() * 1000)
        row = {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_ms": duration_ms,
            "symbols_processed": self.symbols_processed,
            "agent_outputs_stored": self.agent_outputs_stored,
            "recs_produced": self.recs_produced,
            "recs_veto_rejected": self.recs_veto_rejected,
            "recs_veto_adjusted": self.recs_veto_adjusted,
            "recs_passed": self.recs_passed,
            "strategies_activated": self.strategies_activated,
            "sizing_blocked_count": self.sizing_blocked_count,
            "sizing_blocked_reasons": self.sizing_blocked_reasons,
            "positions_opened": self.positions_opened,
            "positions_closed": self.positions_closed,
            "cb_state": self.cb_state,
            "cb_allow_new_entry": self.cb_allow_new_entry,
            "regime_state_per_symbol": self.regime_state_per_symbol,
            "regime_changed_symbols": self.regime_changed_symbols,
        }
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_cycle_metrics").insert(row).execute()
        except Exception as e:
            # Telemetry must NEVER break the trading cycle.
            logger.warning(f"[cycle_metrics] failed to insert row: {e}")

    # ── Record methods ──

    def record_symbols_processed(self, n: int = 1) -> None:
        self.symbols_processed += int(n or 0)

    def record_agent_output(self, agent_name: str, status: str) -> None:
        """status ∈ success|fail|truncated."""
        if not agent_name:
            return
        bucket = self.agent_outputs_stored.setdefault(
            agent_name, {"success": 0, "fail": 0, "truncated": 0}
        )
        key = status if status in ("success", "fail", "truncated") else "fail"
        bucket[key] = bucket.get(key, 0) + 1

    def record_rec(self, action: str) -> None:
        """action ∈ produced|rejected|adjusted|passed."""
        if action == "produced":
            self.recs_produced += 1
        elif action == "rejected":
            self.recs_veto_rejected += 1
        elif action == "adjusted":
            self.recs_veto_adjusted += 1
        elif action == "passed":
            self.recs_passed += 1

    def record_strategy_activation(self, strategy_name: str, count: int = 1) -> None:
        if not strategy_name:
            return
        self.strategies_activated[strategy_name] = (
            self.strategies_activated.get(strategy_name, 0) + int(count or 0)
        )

    def record_sizing_block(
        self,
        symbol: str,
        direction: str,
        attempted_usd: float | None,
        floor_usd: float | None,
        reason: str,
        size_multiplier: float | None = None,
        perf_mult: float | None = None,
    ) -> None:
        self.sizing_blocked_count += 1
        self.sizing_blocked_reasons.append(
            {
                "symbol": symbol,
                "direction": direction,
                "attempted_usd": attempted_usd,
                "floor_usd": floor_usd,
                "reason": reason,
                "size_multiplier": size_multiplier,
                "perf_mult": perf_mult,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def record_position_opened(self, n: int = 1) -> None:
        self.positions_opened += int(n or 0)

    def record_position_closed(self, n: int = 1) -> None:
        self.positions_closed += int(n or 0)

    def set_cb_state(self, state: str | None, allow_new_entry: bool | None) -> None:
        self.cb_state = state
        self.cb_allow_new_entry = allow_new_entry

    def set_regime(self, symbol: str, regime: str | None) -> None:
        if not symbol:
            return
        self.regime_state_per_symbol[symbol] = regime or ""

    def mark_regime_changed(self, symbol: str) -> None:
        if symbol and symbol not in self.regime_changed_symbols:
            self.regime_changed_symbols.append(symbol)


def _log_stderr(msg: str) -> None:
    """Small helper — used by other Phase 1 writers that must never raise."""
    try:
        print(msg, file=sys.stderr, flush=True)
    except Exception:
        pass
