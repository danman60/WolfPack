"""Backtest Harness — Vectorized backtesting with overfitting detection for strategy validation."""

from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel, Field


@dataclass
class GraduationCriteria:
    """Minimum thresholds a strategy must meet before live deployment."""

    min_sharpe: float = 1.5
    max_drawdown: float = 15.0  # percent
    min_trades: int = 20
    min_win_rate: float = 0.45  # 45%
    min_profit_factor: float = 1.3


@dataclass
class GraduationResult:
    """Outcome of a graduation check."""

    passed: bool
    criteria: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def check_graduation(
    metrics: dict,
    criteria: GraduationCriteria | None = None,
) -> GraduationResult:
    """Check if backtest metrics meet graduation criteria for live trading.

    Args:
        metrics: Dict with keys: sharpe_ratio, max_drawdown_pct, total_trades,
                 win_rate, profit_factor (optional, computed from avg_trade_pnl_pct).
        criteria: Custom thresholds (uses defaults if None).
    """
    if criteria is None:
        criteria = GraduationCriteria()

    failures: list[str] = []
    checks: dict = {}

    sharpe = metrics.get("sharpe_ratio", 0)
    checks["sharpe_ratio"] = {"value": sharpe, "min": criteria.min_sharpe, "passed": sharpe >= criteria.min_sharpe}
    if sharpe < criteria.min_sharpe:
        failures.append(f"Sharpe {sharpe:.2f} < {criteria.min_sharpe}")

    max_dd = metrics.get("max_drawdown_pct", 100)
    checks["max_drawdown"] = {"value": max_dd, "max": criteria.max_drawdown, "passed": max_dd <= criteria.max_drawdown}
    if max_dd > criteria.max_drawdown:
        failures.append(f"Max drawdown {max_dd:.1f}% > {criteria.max_drawdown}%")

    trades = metrics.get("total_trades", 0)
    checks["total_trades"] = {"value": trades, "min": criteria.min_trades, "passed": trades >= criteria.min_trades}
    if trades < criteria.min_trades:
        failures.append(f"Only {trades} trades < {criteria.min_trades} minimum")

    win_rate = metrics.get("win_rate", 0)
    checks["win_rate"] = {"value": win_rate, "min": criteria.min_win_rate, "passed": win_rate >= criteria.min_win_rate}
    if win_rate < criteria.min_win_rate:
        failures.append(f"Win rate {win_rate:.1%} < {criteria.min_win_rate:.0%}")

    # Profit factor: approximate from avg_trade_pnl if not directly available
    pf = metrics.get("profit_factor", None)
    if pf is None:
        avg_pnl = metrics.get("avg_trade_pnl_pct", 0)
        # Rough proxy: if avg PnL > 0 and win_rate > 0, estimate PF
        if win_rate > 0 and win_rate < 1 and avg_pnl != 0:
            avg_win = abs(avg_pnl) / win_rate if avg_pnl > 0 else abs(avg_pnl)
            avg_loss = abs(avg_pnl) / (1 - win_rate) if avg_pnl < 0 else abs(avg_pnl)
            pf = (win_rate * avg_win) / ((1 - win_rate) * avg_loss) if avg_loss > 0 else 0
        else:
            pf = 0
    checks["profit_factor"] = {"value": round(pf, 2), "min": criteria.min_profit_factor, "passed": pf >= criteria.min_profit_factor}
    if pf < criteria.min_profit_factor:
        failures.append(f"Profit factor {pf:.2f} < {criteria.min_profit_factor}")

    return GraduationResult(
        passed=len(failures) == 0,
        criteria=checks,
        failures=failures,
    )


class BacktestResult(BaseModel):
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    avg_trade_pnl_pct: float


class BacktestHarness:
    """
    Lightweight vectorized backtester.
    Runs a signal series against historical prices to validate strategies.
    """

    def __init__(self, commission_bps: float = 5.0, slippage_bps: float = 5.0):
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        self.total_cost_pct = (commission_bps + slippage_bps) / 10_000

    def run(self, closes: list[float], signals: list[int]) -> BacktestResult:
        """
        Run a backtest.

        Args:
            closes: List of close prices
            signals: List of position signals (-1=short, 0=flat, 1=long)
                     Must be same length as closes.
        """
        n = min(len(closes), len(signals))
        if n < 2:
            return BacktestResult(
                total_return_pct=0, sharpe_ratio=0, max_drawdown_pct=0,
                win_rate=0, total_trades=0, avg_trade_pnl_pct=0,
            )

        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        trade_returns: list[float] = []
        prev_signal = 0

        for i in range(1, n):
            ret = (closes[i] - closes[i - 1]) / closes[i - 1] if closes[i - 1] != 0 else 0
            position_ret = signals[i - 1] * ret

            # Apply costs on signal change
            if signals[i] != prev_signal:
                position_ret -= self.total_cost_pct
                if prev_signal != 0:
                    trade_returns.append(position_ret)

            equity *= (1 + position_ret)
            peak = max(peak, equity)
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)
            prev_signal = signals[i]

        total_return = (equity - 1) * 100
        wins = sum(1 for r in trade_returns if r > 0)
        win_rate = wins / len(trade_returns) if trade_returns else 0
        avg_pnl = sum(trade_returns) / len(trade_returns) * 100 if trade_returns else 0

        # Sharpe (simplified, daily returns assumed)
        daily_returns = []
        eq = 1.0
        for i in range(1, n):
            ret = (closes[i] - closes[i - 1]) / closes[i - 1] if closes[i - 1] != 0 else 0
            r = signals[i - 1] * ret
            daily_returns.append(r)
            eq *= (1 + r)

        if daily_returns:
            mean_r = sum(daily_returns) / len(daily_returns)
            std_r = (sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
            sharpe = (mean_r / std_r * (365 ** 0.5)) if std_r > 0 else 0
        else:
            sharpe = 0

        return BacktestResult(
            total_return_pct=round(total_return, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown_pct=round(max_dd * 100, 2),
            win_rate=round(win_rate, 3),
            total_trades=len(trade_returns),
            avg_trade_pnl_pct=round(avg_pnl, 4),
        )


class OverfitScore(BaseModel):
    """Overfitting risk assessment — consumed by agents to discount backtest confidence."""

    overfit_risk: str = Field(description="'low', 'moderate', 'high', 'critical'")
    overfit_score: float = Field(ge=0.0, le=1.0, description="0=clean, 1=severely overfit")
    is_sharpe_ratio: float = Field(description="In-sample Sharpe")
    oos_sharpe_ratio: float = Field(description="Out-of-sample Sharpe")
    sharpe_decay_pct: float = Field(description="% drop from IS to OOS Sharpe")
    is_return_pct: float
    oos_return_pct: float
    return_decay_pct: float
    calmar_ratio: float = Field(description="Annualized return / max drawdown")
    conviction_adjustment: int = Field(description="Points to add/subtract from conviction (-15 to +5)")
    warnings: list[str] = Field(default_factory=list)


class OverfitDetector:
    """Detects overfitting by comparing in-sample vs out-of-sample backtest performance.

    Splits data into training (70%) and test (30%) periods.
    Large decay between IS and OOS performance = overfitting.
    This runs automatically before any recommendation — wolves see the score,
    user just sees better-calibrated conviction levels.
    """

    def __init__(self, is_fraction: float = 0.7):
        self.is_fraction = is_fraction

    def check(
        self,
        closes: list[float],
        signals: list[int],
        commission_bps: float = 5.0,
        slippage_bps: float = 5.0,
    ) -> OverfitScore:
        """Run overfitting check by splitting data into IS/OOS and comparing metrics.

        Args:
            closes: Full price series
            signals: Full signal series (same length as closes)
            commission_bps: Commission in basis points
            slippage_bps: Slippage in basis points
        """
        n = min(len(closes), len(signals))
        if n < 40:  # Need at least 40 bars for meaningful split
            return OverfitScore(
                overfit_risk="critical",
                overfit_score=1.0,
                is_sharpe_ratio=0.0,
                oos_sharpe_ratio=0.0,
                sharpe_decay_pct=100.0,
                is_return_pct=0.0,
                oos_return_pct=0.0,
                return_decay_pct=100.0,
                calmar_ratio=0.0,
                conviction_adjustment=-15,
                warnings=["Insufficient data for overfitting check (<40 bars)"],
            )

        split_idx = int(n * self.is_fraction)

        harness = BacktestHarness(commission_bps=commission_bps, slippage_bps=slippage_bps)

        # In-sample
        is_result = harness.run(closes[:split_idx], signals[:split_idx])

        # Out-of-sample
        oos_result = harness.run(closes[split_idx:], signals[split_idx:])

        # Full-period for Calmar
        full_result = harness.run(closes[:n], signals[:n])

        # Sharpe decay
        if is_result.sharpe_ratio > 0.01:
            sharpe_decay = max(0, (1 - oos_result.sharpe_ratio / is_result.sharpe_ratio) * 100)
        else:
            sharpe_decay = 0.0 if oos_result.sharpe_ratio <= 0.01 else 0.0

        # Return decay
        if is_result.total_return_pct > 0.01:
            return_decay = max(0, (1 - oos_result.total_return_pct / is_result.total_return_pct) * 100)
        else:
            return_decay = 0.0 if oos_result.total_return_pct <= 0.01 else 0.0

        # Calmar ratio: annualized return / max drawdown
        # Approximate annualization assuming hourly data (8760 bars/year)
        bars_per_year = 8760
        ann_return = full_result.total_return_pct * (bars_per_year / n) if n > 0 else 0
        calmar = ann_return / full_result.max_drawdown_pct if full_result.max_drawdown_pct > 0.01 else 10.0
        calmar = min(calmar, 10.0)

        # Compute overfit score (0-1)
        warnings: list[str] = []
        score_components: list[float] = []

        # Sharpe decay component (0-1, higher = more overfit)
        sharpe_comp = min(sharpe_decay / 80.0, 1.0)  # 80%+ decay = max overfit
        score_components.append(sharpe_comp * 0.40)

        # Return decay component
        return_comp = min(return_decay / 80.0, 1.0)
        score_components.append(return_comp * 0.30)

        # OOS goes negative
        if oos_result.total_return_pct < 0:
            score_components.append(0.20)
            warnings.append(f"OOS returns negative ({oos_result.total_return_pct:.1f}%) — strategy may not generalize")
        else:
            score_components.append(0.0)

        # Calmar too low
        if calmar < 1.0:
            score_components.append(0.10)
            warnings.append(f"Calmar ratio {calmar:.1f} < 1.0 — risk-adjusted returns poor")
        else:
            score_components.append(0.0)

        overfit_score = min(sum(score_components), 1.0)

        # Additional warnings
        if sharpe_decay > 50:
            warnings.append(f"Sharpe decays {sharpe_decay:.0f}% out-of-sample — likely overfit")
        if is_result.sharpe_ratio > 3.0:
            warnings.append(f"IS Sharpe {is_result.sharpe_ratio:.1f} suspiciously high — check for look-ahead bias")
        if full_result.total_trades < 20:
            warnings.append(f"Only {full_result.total_trades} trades — insufficient for statistical significance")

        # Grade
        if overfit_score >= 0.7:
            risk = "critical"
        elif overfit_score >= 0.5:
            risk = "high"
        elif overfit_score >= 0.3:
            risk = "moderate"
        else:
            risk = "low"

        # Conviction adjustment
        if overfit_score >= 0.7:
            conv_adj = -15
        elif overfit_score >= 0.5:
            conv_adj = -10
        elif overfit_score >= 0.3:
            conv_adj = -5
        elif overfit_score < 0.15 and calmar >= 3.0:
            conv_adj = 5  # Boost for clean, high-Calmar strategies
        else:
            conv_adj = 0

        return OverfitScore(
            overfit_risk=risk,
            overfit_score=round(overfit_score, 3),
            is_sharpe_ratio=round(is_result.sharpe_ratio, 2),
            oos_sharpe_ratio=round(oos_result.sharpe_ratio, 2),
            sharpe_decay_pct=round(sharpe_decay, 1),
            is_return_pct=round(is_result.total_return_pct, 2),
            oos_return_pct=round(oos_result.total_return_pct, 2),
            return_decay_pct=round(return_decay, 1),
            calmar_ratio=round(calmar, 2),
            conviction_adjustment=conv_adj,
            warnings=warnings,
        )
