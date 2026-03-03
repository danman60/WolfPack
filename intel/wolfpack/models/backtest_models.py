"""Pydantic models for the backtesting system."""

from pydantic import BaseModel


class BacktestConfig(BaseModel):
    symbol: str
    exchange: str
    interval: str = "1h"
    start_time: int  # epoch ms
    end_time: int  # epoch ms
    starting_equity: float = 10000.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    strategy: str = "regime_momentum"
    strategy_params: dict = {}
    max_position_pct: float = 25.0
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


class TradeRecord(BaseModel):
    entry_time: int
    exit_time: int
    direction: str  # "long" or "short"
    entry_price: float
    exit_price: float
    size_usd: float
    pnl_usd: float
    pnl_pct: float
    exit_reason: str  # "signal_change" | "stop_loss" | "take_profit" | "end_of_data"
    holding_bars: int


class BacktestMetrics(BaseModel):
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_duration_bars: int
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl_pct: float
    avg_winning_pct: float
    avg_losing_pct: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_holding_bars: float
    expectancy_pct: float


class BacktestResult(BaseModel):
    run_id: str
    config: BacktestConfig
    metrics: BacktestMetrics
    equity_curve: list[dict]  # [{time, equity, drawdown_pct}]
    monthly_returns: list[dict]  # [{month, return_pct}]
    trades: list[TradeRecord]
    duration_seconds: float
