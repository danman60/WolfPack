"""Funding & Carry Intel — Funding rate z-score analysis, crowding detection, carry opportunities."""

from collections import deque
from typing import Literal

import numpy as np
from pydantic import BaseModel

from wolfpack.exchanges.base import FundingRate


FundingBias = Literal["neutral", "avoid_long", "avoid_short", "extreme_long", "extreme_short"]


class FundingOutput(BaseModel):
    asset: str
    current_rate: float
    annualized_rate_pct: float
    rate_zscore: float
    rate_percentile_7d: float
    funding_bias: FundingBias
    open_interest_usd: float
    oi_change_24h_pct: float
    crowding_score: float
    carry_opportunity: bool
    carry_direction: str  # "long", "short", or "none"
    carry_expected_bps_per_day: float


class FundingIntel:
    """Analyzes funding rates with z-score tracking, crowding detection, and carry signals.

    Maintains a rolling 168-period (7d of hourly) history per asset for z-score
    and percentile computation. Rates are stored on each analyze() call.

    Key computations:
    - Z-score: (current - mean_7d) / std_7d
    - Annualized rate: rate * 8760 * 100
    - Bias from z-score thresholds
    - Crowding: 0.6 * (|z|/3) + 0.4 * (|OI_change|/20%)
    - Carry: direction opposite to funding payer, expected bps/day
    """

    # 168 = 7 days * 24 hours (assuming hourly rate snapshots)
    HISTORY_LEN = 168

    def __init__(self) -> None:
        # Per-asset rate history: asset -> deque of rates
        self._rate_history: dict[str, deque] = {}

    def analyze(
        self,
        funding: FundingRate,
        open_interest_usd: float = 0.0,
        oi_change_24h_pct: float = 0.0,
    ) -> FundingOutput:
        asset = funding.symbol
        rate = funding.rate

        # --- Store rate history ---
        if asset not in self._rate_history:
            self._rate_history[asset] = deque(maxlen=self.HISTORY_LEN)
        self._rate_history[asset].append(rate)

        history = self._rate_history[asset]
        rates_arr = np.array(history, dtype=np.float64)

        # --- Annualized rate ---
        annualized_rate_pct = rate * 8760 * 100

        # --- Z-score ---
        if len(rates_arr) >= 3:
            mean_7d = float(np.mean(rates_arr))
            std_7d = float(np.std(rates_arr, ddof=1))
            if std_7d > 1e-12:
                rate_zscore = (rate - mean_7d) / std_7d
            else:
                rate_zscore = 0.0
        else:
            rate_zscore = 0.0

        # --- Percentile within 7d history ---
        if len(rates_arr) >= 2:
            rate_percentile_7d = float(np.mean(rates_arr <= rate))
        else:
            rate_percentile_7d = 0.5

        # --- Bias from z-score thresholds ---
        funding_bias = self._compute_bias(rate_zscore)

        # --- Crowding score ---
        # 0.6 * (|zscore| / 3.0) + 0.4 * (|OI_change| / 20%)
        z_component = np.clip(abs(rate_zscore) / 3.0, 0.0, 1.0)
        oi_component = np.clip(abs(oi_change_24h_pct) / 20.0, 0.0, 1.0)
        crowding_score = float(0.6 * z_component + 0.4 * oi_component)

        # --- Carry opportunity ---
        carry_opportunity, carry_direction, carry_bps_per_day = self._compute_carry(
            rate, rate_zscore
        )

        return FundingOutput(
            asset=asset,
            current_rate=rate,
            annualized_rate_pct=round(annualized_rate_pct, 2),
            rate_zscore=round(rate_zscore, 2),
            rate_percentile_7d=round(rate_percentile_7d, 4),
            funding_bias=funding_bias,
            open_interest_usd=open_interest_usd,
            oi_change_24h_pct=round(oi_change_24h_pct, 2),
            crowding_score=round(crowding_score, 4),
            carry_opportunity=carry_opportunity,
            carry_direction=carry_direction,
            carry_expected_bps_per_day=round(carry_bps_per_day, 2),
        )

    @staticmethod
    def _compute_bias(zscore: float) -> FundingBias:
        """Map z-score to funding bias category."""
        if zscore >= 2.5:
            return "extreme_long"
        elif zscore >= 1.5:
            return "avoid_long"
        elif zscore <= -2.5:
            return "extreme_short"
        elif zscore <= -1.5:
            return "avoid_short"
        else:
            return "neutral"

    @staticmethod
    def _compute_carry(rate: float, zscore: float) -> tuple[bool, str, float]:
        """Determine carry trade opportunity.

        If funding is significantly elevated (|z| >= 1.5), there's a carry
        opportunity in the direction that collects funding.

        Returns (carry_opportunity, direction, expected_bps_per_day).
        """
        if abs(zscore) < 1.5:
            return False, "none", 0.0

        # rate > 0 means longs pay shorts → short to collect carry
        # rate < 0 means shorts pay longs → long to collect carry
        if rate > 0:
            direction = "short"
        else:
            direction = "long"

        # Expected bps/day: |rate| * 3 payments/day * 10_000 bps
        bps_per_day = abs(rate) * 3 * 10_000
        return True, direction, bps_per_day
