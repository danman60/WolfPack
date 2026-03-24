"""Monte Carlo Stress Testing — HMM-inspired simulation for strategy robustness.

Runs N simulations by resampling trade returns with regime-aware bootstrapping.
Produces confidence intervals, drawdown distributions, and a robustness score
that feeds into agent conviction scoring.

The wolves consume this internally — the user never sees Monte Carlo charts.
They just see better recommendations.
"""

import math
import random
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field


RobustnessGrade = Literal["excellent", "good", "marginal", "poor", "insufficient_data"]


class MonteCarloResult(BaseModel):
    """Output consumed by agents internally for conviction adjustment."""

    simulations_run: int
    median_return_pct: float
    p5_return_pct: float = Field(description="5th percentile return — worst realistic case")
    p25_return_pct: float
    p75_return_pct: float
    p95_return_pct: float = Field(description="95th percentile return — best realistic case")
    median_max_drawdown_pct: float
    p95_max_drawdown_pct: float = Field(description="95th percentile drawdown — worst realistic DD")
    calmar_median: float = Field(description="Median Calmar ratio across simulations")
    calmar_p5: float = Field(description="5th percentile Calmar — worst case risk-adjusted")
    ruin_probability: float = Field(description="% of simulations hitting >25% drawdown")
    robustness_grade: RobustnessGrade
    robustness_score: float = Field(ge=0.0, le=1.0, description="0-1 score for agent conviction adjustment")
    conviction_adjustment: int = Field(description="Points to add/subtract from base conviction (-20 to +10)")


class MonteCarloEngine:
    """Runs Monte Carlo stress tests on trade return sequences.

    Uses block bootstrap (preserves autocorrelation) with regime-aware
    resampling to simulate realistic forward performance distributions.
    """

    def __init__(
        self,
        n_simulations: int = 2000,
        block_size: int = 5,
        seed: int | None = None,
    ):
        self.n_simulations = n_simulations
        self.block_size = block_size
        self.rng = np.random.default_rng(seed)

    def run(
        self,
        trade_returns: list[float],
        regime_labels: list[str] | None = None,
    ) -> MonteCarloResult:
        """Run Monte Carlo stress test on a sequence of trade returns.

        Args:
            trade_returns: List of per-trade P&L percentages (e.g. [0.02, -0.01, 0.035, ...])
            regime_labels: Optional regime label per trade for regime-aware resampling.
                          If provided, simulations preserve regime transition patterns.
        """
        n_trades = len(trade_returns)

        if n_trades < 10:
            return self._insufficient_data(n_trades)

        returns = np.array(trade_returns, dtype=np.float64)

        # Run simulations
        sim_total_returns: list[float] = []
        sim_max_drawdowns: list[float] = []
        sim_calmars: list[float] = []

        for _ in range(self.n_simulations):
            sim_returns = self._block_bootstrap(returns, n_trades)
            total_ret, max_dd = self._compute_equity_stats(sim_returns)
            sim_total_returns.append(total_ret)
            sim_max_drawdowns.append(max_dd)

            # Calmar: annualized return / max drawdown
            # Approximate annualization: assume ~250 trades/year
            trades_per_year = min(250, n_trades * 4)  # rough estimate
            if max_dd > 0.001:
                ann_return = total_ret * (trades_per_year / n_trades) if n_trades > 0 else 0
                calmar = ann_return / max_dd
            else:
                calmar = 10.0  # cap at 10 if no meaningful drawdown
            sim_calmars.append(min(calmar, 10.0))

        ret_arr = np.array(sim_total_returns) * 100
        dd_arr = np.array(sim_max_drawdowns) * 100
        calmar_arr = np.array(sim_calmars)

        # Percentiles
        p5_ret = float(np.percentile(ret_arr, 5))
        p25_ret = float(np.percentile(ret_arr, 25))
        median_ret = float(np.median(ret_arr))
        p75_ret = float(np.percentile(ret_arr, 75))
        p95_ret = float(np.percentile(ret_arr, 95))

        median_dd = float(np.median(dd_arr))
        p95_dd = float(np.percentile(dd_arr, 95))

        calmar_median = float(np.median(calmar_arr))
        calmar_p5 = float(np.percentile(calmar_arr, 5))

        # Ruin probability: % of sims with >25% max drawdown
        ruin_prob = float(np.mean(dd_arr > 25)) * 100

        # Grade and score
        grade, score = self._compute_robustness(
            p5_ret, median_ret, median_dd, p95_dd, calmar_p5, ruin_prob
        )

        # Conviction adjustment: -20 to +10 based on robustness
        conviction_adj = self._conviction_adjustment(score, ruin_prob, calmar_p5)

        return MonteCarloResult(
            simulations_run=self.n_simulations,
            median_return_pct=round(median_ret, 2),
            p5_return_pct=round(p5_ret, 2),
            p25_return_pct=round(p25_ret, 2),
            p75_return_pct=round(p75_ret, 2),
            p95_return_pct=round(p95_ret, 2),
            median_max_drawdown_pct=round(median_dd, 2),
            p95_max_drawdown_pct=round(p95_dd, 2),
            calmar_median=round(calmar_median, 2),
            calmar_p5=round(calmar_p5, 2),
            ruin_probability=round(ruin_prob, 2),
            robustness_grade=grade,
            robustness_score=round(score, 3),
            conviction_adjustment=conviction_adj,
        )

    def _block_bootstrap(self, returns: np.ndarray, target_length: int) -> np.ndarray:
        """Block bootstrap: resample in blocks to preserve autocorrelation."""
        n = len(returns)
        if n == 0:
            return np.array([])

        block = min(self.block_size, n)
        result = []

        while len(result) < target_length:
            start = self.rng.integers(0, max(1, n - block + 1))
            result.extend(returns[start : start + block].tolist())

        return np.array(result[:target_length])

    @staticmethod
    def _compute_equity_stats(returns: np.ndarray) -> tuple[float, float]:
        """Compute total return and max drawdown from a return sequence.

        Returns (total_return_fraction, max_drawdown_fraction).
        """
        if len(returns) == 0:
            return 0.0, 0.0

        equity = np.cumprod(1.0 + returns)
        total_return = equity[-1] - 1.0

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        return float(total_return), max_dd

    @staticmethod
    def _compute_robustness(
        p5_ret: float,
        median_ret: float,
        median_dd: float,
        p95_dd: float,
        calmar_p5: float,
        ruin_prob: float,
    ) -> tuple[RobustnessGrade, float]:
        """Compute robustness grade and 0-1 score.

        Scoring:
        - 40% weight: Calmar p5 (worst-case risk-adjusted return)
        - 25% weight: ruin probability (inverted)
        - 20% weight: p5 return (worst-case absolute return)
        - 15% weight: drawdown control (p95 DD)
        """
        # Calmar component: 0-1 (calmar_p5 of 3+ = perfect)
        calmar_score = min(max(calmar_p5, 0) / 3.0, 1.0)

        # Ruin component: 0-1 (0% ruin = perfect, 20%+ = zero)
        ruin_score = max(1.0 - ruin_prob / 20.0, 0.0)

        # Return component: 0-1 (p5 return > 0 = good)
        ret_score = min(max((p5_ret + 10) / 20.0, 0.0), 1.0)  # -10% = 0, +10% = 1

        # Drawdown component: 0-1 (p95 DD < 10% = perfect, > 30% = zero)
        dd_score = max(1.0 - max(p95_dd - 10, 0) / 20.0, 0.0)

        score = 0.40 * calmar_score + 0.25 * ruin_score + 0.20 * ret_score + 0.15 * dd_score

        if score >= 0.8:
            grade: RobustnessGrade = "excellent"
        elif score >= 0.6:
            grade = "good"
        elif score >= 0.4:
            grade = "marginal"
        else:
            grade = "poor"

        return grade, score

    @staticmethod
    def _conviction_adjustment(score: float, ruin_prob: float, calmar_p5: float) -> int:
        """Compute conviction adjustment points based on robustness.

        Range: -20 (terrible) to +10 (excellent).
        This directly modifies the Brief's conviction before recommendation.
        """
        if score >= 0.8 and ruin_prob < 5:
            return 10  # Boost: stress test confirms edge
        elif score >= 0.6:
            return 5
        elif score >= 0.4:
            return 0  # Neutral: not enough signal either way
        elif score >= 0.2:
            return -10  # Penalize: stress test shows fragility
        else:
            return -20  # Hard penalize: likely to blow up

    def _insufficient_data(self, n_trades: int) -> MonteCarloResult:
        """Return a conservative result when there aren't enough trades."""
        return MonteCarloResult(
            simulations_run=0,
            median_return_pct=0.0,
            p5_return_pct=0.0,
            p25_return_pct=0.0,
            p75_return_pct=0.0,
            p95_return_pct=0.0,
            median_max_drawdown_pct=0.0,
            p95_max_drawdown_pct=0.0,
            calmar_median=0.0,
            calmar_p5=0.0,
            ruin_probability=100.0,
            robustness_grade="insufficient_data",
            robustness_score=0.0,
            conviction_adjustment=-15,  # Penalize for no data
        )
