"""Backtest Harness — Simple vectorized backtesting for strategy validation."""

from pydantic import BaseModel


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
