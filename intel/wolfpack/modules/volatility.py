"""Volatility & Risk Budget — Position sizing based on volatility regime."""

from pydantic import BaseModel


class VolatilityOutput(BaseModel):
    current_vol: float          # Current annualized volatility
    vol_percentile: float       # Where current vol sits historically (0-1)
    suggested_position_pct: float  # Suggested max position size as % of equity
    risk_budget_used: float     # Fraction of total risk budget consumed


class VolatilitySignal:
    """
    Computes realized volatility and maps it to position sizing constraints.
    Higher volatility → smaller positions.
    """

    def __init__(self, max_risk_pct: float = 2.0, max_position_pct: float = 25.0):
        self.max_risk_pct = max_risk_pct  # Max risk per trade as % of equity
        self.max_position_pct = max_position_pct

    def analyze(self, closes: list[float], lookback: int = 30) -> VolatilityOutput:
        if len(closes) < lookback + 1:
            return VolatilityOutput(
                current_vol=0, vol_percentile=0, suggested_position_pct=self.max_position_pct, risk_budget_used=0
            )

        # Log returns
        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(-lookback, 0)
            if closes[i - 1] != 0
        ]
        if not returns:
            return VolatilityOutput(
                current_vol=0, vol_percentile=0, suggested_position_pct=self.max_position_pct, risk_budget_used=0
            )

        # Realized vol (annualized)
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        daily_vol = variance ** 0.5
        annual_vol = daily_vol * (365 ** 0.5) * 100

        # Vol percentile (simple: compare to longer history if available)
        vol_pct = min(annual_vol / 150, 1.0)  # 150% annual vol = 100th percentile

        # Position sizing: inverse volatility scaling
        if annual_vol > 0:
            suggested = min(self.max_risk_pct / (daily_vol * 100) * 100, self.max_position_pct)
        else:
            suggested = self.max_position_pct

        return VolatilityOutput(
            current_vol=round(annual_vol, 2),
            vol_percentile=round(vol_pct, 3),
            suggested_position_pct=round(suggested, 1),
            risk_budget_used=round(vol_pct, 3),
        )
