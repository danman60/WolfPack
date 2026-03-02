"""Funding & Carry Intel — Funding rate analysis and carry trade opportunities."""

from pydantic import BaseModel

from wolfpack.exchanges.base import FundingRate


class FundingOutput(BaseModel):
    symbol: str
    current_rate: float
    annualized_pct: float
    bias: str  # "long_pay", "short_pay", "neutral"
    carry_opportunity: bool
    carry_direction: str  # "long" or "short" for positive carry


class FundingIntel:
    """Analyzes funding rates to identify carry opportunities."""

    def __init__(self, threshold_bps: float = 5.0):
        self.threshold_bps = threshold_bps

    def analyze(self, rates: list[FundingRate]) -> list[FundingOutput]:
        results = []
        for r in rates:
            annualized = r.rate * 3 * 365 * 100  # 8h funding * 3 * 365 = annual %

            if r.rate > self.threshold_bps / 10_000:
                bias = "long_pay"
                carry_direction = "short"
                carry = True
            elif r.rate < -self.threshold_bps / 10_000:
                bias = "short_pay"
                carry_direction = "long"
                carry = True
            else:
                bias = "neutral"
                carry_direction = "none"
                carry = False

            results.append(
                FundingOutput(
                    symbol=r.symbol,
                    current_rate=r.rate,
                    annualized_pct=round(annualized, 2),
                    bias=bias,
                    carry_opportunity=carry,
                    carry_direction=carry_direction,
                )
            )
        return results
