"""Circuit Breaker — Stateful safety system with ACTIVE / SUSPENDED / EMERGENCY_STOP state machine."""

import time
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from wolfpack.risk_controls import HardLimits, SoftLimits


CBState = Literal["ACTIVE", "SUSPENDED", "EMERGENCY_STOP"]


class CircuitBreakerOutput(BaseModel):
    state: CBState
    reason: str
    violations: list[str]
    cooldown_remaining_s: float
    trades_today: int
    trades_remaining: int
    daily_pnl_pct: float
    rolling_24h_pnl_pct: float
    current_drawdown_pct: float
    total_exposure_pct: float
    allow_new_entry: bool
    allow_exit: bool
    allow_increase: bool


class CircuitBreaker:
    """Stateful circuit breaker with three-state machine: ACTIVE, SUSPENDED, EMERGENCY_STOP.

    State transitions:
    - ACTIVE -> EMERGENCY_STOP: any CRITICAL violation
        * drawdown >= 10%
        * daily_pnl <= -3%
        * rolling_24h_pnl <= -3%
    - ACTIVE -> SUSPENDED (30 min cooldown): any SOFT violation
        * exposure > 50%
        * trades_today >= 4
        * data_age > 120s
    - SUSPENDED -> ACTIVE: cooldown expired AND no active violations
    - EMERGENCY_STOP -> ACTIVE: manual reset only

    Hard constraints:
        max_drawdown = 10%
        max_trades_per_day = 4
        worst_24h_pnl = -3%
        max_exposure = 50%

    Trades-today counter resets at UTC midnight.
    """

    # All thresholds sourced from unified risk policy
    _hard = HardLimits()
    _soft = SoftLimits()

    MAX_DRAWDOWN_PCT = _hard.max_drawdown_pct          # 10.0
    MAX_TRADES_PER_DAY = _soft.max_trades_per_day      # 4
    WORST_DAILY_PNL_PCT = _hard.daily_pnl_floor_pct   # -3.0
    WORST_24H_PNL_PCT = _hard.rolling_24h_pnl_floor_pct  # -3.0
    MAX_EXPOSURE_PCT = _soft.max_exposure_pct           # 50.0
    COOLDOWN_SECONDS = _soft.cooldown_seconds           # 1800.0
    MAX_DATA_AGE_S = _soft.max_data_age_s               # 120.0

    def __init__(self, wallet_id: str | None = None) -> None:
        self.wallet_id = wallet_id  # Wave 4: per-wallet independent state
        self._state: CBState = "ACTIVE"
        self._reason: str = ""
        self._cooldown_start: float = 0.0
        self._trades_today: int = 0
        self._last_trade_date: str = ""  # ISO date string for midnight reset

    @property
    def state(self) -> CBState:
        return self._state

    def record_trade(self) -> None:
        """Call this when a trade is executed to increment today's counter."""
        self._reset_daily_counter_if_needed()
        self._trades_today += 1

    def restore_state(self, state: CBState, reason: str = "Restored from DB") -> None:
        """Restore state from persisted DB row (used on startup)."""
        if state in ("ACTIVE", "SUSPENDED", "EMERGENCY_STOP"):
            self._state = state
            self._reason = reason
            if state == "SUSPENDED":
                self._cooldown_start = time.time()  # Restart cooldown from now

    def manual_reset(self) -> None:
        """Manually reset from EMERGENCY_STOP back to ACTIVE."""
        self._state = "ACTIVE"
        self._reason = "Manual reset"
        self._cooldown_start = 0.0

    def check(
        self,
        daily_pnl_pct: float,
        rolling_24h_pnl_pct: float,
        current_drawdown_pct: float,
        total_exposure_pct: float,
        data_age_s: float = 0.0,
    ) -> CircuitBreakerOutput:
        """Evaluate all conditions and return current circuit breaker state.

        Args:
            daily_pnl_pct: Today's PnL as percentage (negative = loss).
            rolling_24h_pnl_pct: Rolling 24-hour PnL percentage.
            current_drawdown_pct: Current drawdown from peak as positive percentage.
            total_exposure_pct: Total portfolio exposure as percentage of equity.
            data_age_s: Age of most recent market data in seconds.
        """
        self._reset_daily_counter_if_needed()
        now = time.time()

        violations: list[str] = []
        critical = False
        soft = False

        # ===================== CRITICAL violations =====================
        if current_drawdown_pct >= self.MAX_DRAWDOWN_PCT:
            violations.append("max_drawdown_breached")
            critical = True

        if daily_pnl_pct <= self.WORST_DAILY_PNL_PCT:
            violations.append("daily_pnl_limit_breached")
            critical = True

        if rolling_24h_pnl_pct <= self.WORST_24H_PNL_PCT:
            violations.append("rolling_24h_pnl_breached")
            critical = True

        # ===================== SOFT violations =====================
        if total_exposure_pct > self.MAX_EXPOSURE_PCT:
            violations.append("exposure_exceeded")
            soft = True

        if self._trades_today >= self.MAX_TRADES_PER_DAY:
            violations.append("max_trades_reached")
            soft = True

        if data_age_s > self.MAX_DATA_AGE_S:
            violations.append("stale_data")
            soft = True

        # Soft warning levels (not violations, but informational)
        if daily_pnl_pct <= -2.0 and daily_pnl_pct > self.WORST_DAILY_PNL_PCT:
            violations.append("daily_pnl_warning")

        if current_drawdown_pct >= 7.0 and current_drawdown_pct < self.MAX_DRAWDOWN_PCT:
            violations.append("drawdown_warning")

        # ===================== State transitions =====================

        # From EMERGENCY_STOP: only manual reset can change state
        if self._state == "EMERGENCY_STOP":
            pass  # Stays in EMERGENCY_STOP regardless

        # From ACTIVE
        elif self._state == "ACTIVE":
            if critical:
                self._state = "EMERGENCY_STOP"
                self._reason = self._build_reason(violations, critical=True)
            elif soft:
                self._state = "SUSPENDED"
                self._cooldown_start = now
                self._reason = self._build_reason(violations, critical=False)

        # From SUSPENDED
        elif self._state == "SUSPENDED":
            if critical:
                # Escalate to emergency
                self._state = "EMERGENCY_STOP"
                self._reason = self._build_reason(violations, critical=True)
            else:
                # Check if cooldown expired AND no violations remain
                elapsed = now - self._cooldown_start
                if elapsed >= self.COOLDOWN_SECONDS and not soft:
                    self._state = "ACTIVE"
                    self._reason = "Cooldown expired, no active violations"
                    self._cooldown_start = 0.0

        # ===================== Compute outputs =====================
        cooldown_remaining = 0.0
        if self._state == "SUSPENDED" and self._cooldown_start > 0:
            elapsed = now - self._cooldown_start
            cooldown_remaining = max(0.0, self.COOLDOWN_SECONDS - elapsed)

        trades_remaining = max(0, self.MAX_TRADES_PER_DAY - self._trades_today)

        # Permissions
        allow_new_entry = self._state == "ACTIVE"
        allow_exit = self._state != "EMERGENCY_STOP"  # Can always exit unless emergency
        allow_increase = self._state == "ACTIVE"

        # In SUSPENDED, allow exits but not entries
        if self._state == "SUSPENDED":
            allow_exit = True

        return CircuitBreakerOutput(
            state=self._state,
            reason=self._reason if self._reason else "All clear",
            violations=violations,
            cooldown_remaining_s=round(cooldown_remaining, 1),
            trades_today=self._trades_today,
            trades_remaining=trades_remaining,
            daily_pnl_pct=round(daily_pnl_pct, 2),
            rolling_24h_pnl_pct=round(rolling_24h_pnl_pct, 2),
            current_drawdown_pct=round(current_drawdown_pct, 2),
            total_exposure_pct=round(total_exposure_pct, 2),
            allow_new_entry=allow_new_entry,
            allow_exit=allow_exit,
            allow_increase=allow_increase,
        )

    def _reset_daily_counter_if_needed(self) -> None:
        """Reset trades_today at UTC midnight."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._last_trade_date != today:
            self._trades_today = 0
            self._last_trade_date = today

    @staticmethod
    def _build_reason(violations: list[str], critical: bool) -> str:
        """Build a human-readable reason string from violations."""
        severity = "CRITICAL" if critical else "SOFT"
        labels = {
            "max_drawdown_breached": "Max drawdown limit breached",
            "daily_pnl_limit_breached": "Daily PnL limit breached",
            "rolling_24h_pnl_breached": "Rolling 24h PnL limit breached",
            "exposure_exceeded": "Total exposure exceeds limit",
            "max_trades_reached": "Max daily trades reached",
            "stale_data": "Market data is stale",
            "daily_pnl_warning": "Daily PnL limit approaching",
            "drawdown_warning": "Drawdown approaching limit",
        }

        descriptions = [labels.get(v, v) for v in violations if v in labels]
        if not descriptions:
            return f"{severity}: Unknown violation"

        return f"{severity}: {'; '.join(descriptions)}"
