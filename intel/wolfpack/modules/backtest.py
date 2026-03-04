"""Backtest Harness — Simple vectorized backtesting for strategy validation."""

from dataclasses import dataclass, field
from pydantic import BaseModel


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
