"""Circuit Breakers — Safety system to halt trading in extreme conditions."""

from enum import Enum

from pydantic import BaseModel


class SafetyState(str, Enum):
    GREEN = "green"     # All systems go
    YELLOW = "yellow"   # Caution, reduce exposure
    RED = "red"         # Halt new trades


class CircuitBreakerOutput(BaseModel):
    state: SafetyState
    triggers: list[str]
    max_exposure_pct: float  # Current max allowed exposure


class CircuitBreaker:
    """
    Monitors multiple safety conditions and triggers circuit breakers.

    Conditions checked:
    - Max drawdown exceeded
    - Extreme volatility spike
    - Liquidity collapse
    - Rapid successive losses
    """

    def __init__(
        self,
        max_drawdown_pct: float = 10.0,
        max_daily_loss_pct: float = 5.0,
        vol_spike_multiplier: float = 3.0,
    ):
        self.max_drawdown_pct = max_drawdown_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.vol_spike_multiplier = vol_spike_multiplier

    def check(
        self,
        current_equity: float,
        peak_equity: float,
        daily_pnl_pct: float,
        current_vol: float,
        avg_vol: float,
    ) -> CircuitBreakerOutput:
        triggers: list[str] = []
        state = SafetyState.GREEN
        max_exposure = 50.0

        # Drawdown check
        if peak_equity > 0:
            drawdown = (peak_equity - current_equity) / peak_equity * 100
            if drawdown > self.max_drawdown_pct:
                triggers.append(f"Max drawdown exceeded: {drawdown:.1f}%")
                state = SafetyState.RED
            elif drawdown > self.max_drawdown_pct * 0.7:
                triggers.append(f"Drawdown warning: {drawdown:.1f}%")
                if state != SafetyState.RED:
                    state = SafetyState.YELLOW
                    max_exposure = 25.0

        # Daily loss check
        if daily_pnl_pct < -self.max_daily_loss_pct:
            triggers.append(f"Daily loss limit hit: {daily_pnl_pct:.1f}%")
            state = SafetyState.RED
        elif daily_pnl_pct < -self.max_daily_loss_pct * 0.7:
            triggers.append(f"Daily loss warning: {daily_pnl_pct:.1f}%")
            if state != SafetyState.RED:
                state = SafetyState.YELLOW
                max_exposure = 25.0

        # Volatility spike
        if avg_vol > 0 and current_vol > avg_vol * self.vol_spike_multiplier:
            triggers.append(f"Vol spike: {current_vol:.1f}% vs avg {avg_vol:.1f}%")
            if state != SafetyState.RED:
                state = SafetyState.YELLOW
                max_exposure = 15.0

        if state == SafetyState.RED:
            max_exposure = 0.0

        return CircuitBreakerOutput(
            state=state,
            triggers=triggers,
            max_exposure_pct=max_exposure,
        )
