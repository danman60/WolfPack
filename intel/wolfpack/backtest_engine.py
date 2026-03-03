"""Backtest engine — replays candles through PaperTradingEngine bar-by-bar.

Production parity: uses the REAL PaperTradingEngine for position management,
P&L math, stop-loss/take-profit, and snapshots. The only difference from
live/paper trading is the price feed source (historical candles vs real-time).
"""

import logging
import math
import time
from collections import defaultdict
from datetime import datetime, timezone

from wolfpack.exchanges.base import Candle
from wolfpack.models.backtest_models import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    TradeRecord,
)
from wolfpack.paper_trading import PaperTradingEngine
from wolfpack.strategies import STRATEGIES

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Thin orchestrator that replays candles through PaperTradingEngine."""

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.paper = PaperTradingEngine(starting_equity=config.starting_equity)
        strategy_cls = STRATEGIES.get(config.strategy)
        if strategy_cls is None:
            raise ValueError(f"Unknown strategy: {config.strategy}")
        self.strategy = strategy_cls()
        self.trades: list[TradeRecord] = []
        self.equity_curve: list[dict] = []
        self._open_trade_entry: dict | None = None
        self._bar_index = 0

    async def run(self, candles: list[Candle], progress_cb=None) -> BacktestResult:
        """Run backtest over candles. Returns full result with metrics."""
        start_time = time.time()
        cost_pct = (self.config.commission_bps + self.config.slippage_bps) / 10_000
        warmup = self.strategy.warmup_bars
        total_bars = len(candles)

        for i in range(warmup, total_bars):
            self._bar_index = i
            candle = candles[i]
            price = candle.close

            # 1. Update prices — SAME as live cycle
            self.paper.update_prices({self.config.symbol: price})

            # 2. Check stops against OHLC — upgraded from placeholder
            triggered = self.paper.check_stops_ohlc({self.config.symbol: candle})
            for sym, reason in triggered:
                self._record_trade_close(candle, reason)

            # 3. Get strategy recommendation — same format as Brief
            rec = self.strategy.evaluate(candles, i, **self.config.strategy_params)

            # 4. Process recommendation through PaperTradingEngine
            if rec and self._should_act(rec):
                current_pos = self._get_current_position()

                if current_pos and rec["direction"] == "close":
                    self.paper.close_position(self.config.symbol)
                    self._record_trade_close(candle, "signal_change")

                elif current_pos and rec["direction"] != current_pos.direction:
                    # Reverse: close then open
                    self.paper.close_position(self.config.symbol)
                    self._record_trade_close(candle, "signal_change")
                    self._open_via_engine(rec, candle, cost_pct)

                elif not current_pos and rec["direction"] in ("long", "short"):
                    self._open_via_engine(rec, candle, cost_pct)

            # 5. Snapshot — record equity curve point
            self._record_equity(candle)

            # Progress callback
            if progress_cb and i % 50 == 0:
                pct = (i - warmup) / max(total_bars - warmup, 1) * 100
                await progress_cb(pct)

        # Close any remaining position at end of data
        if self.paper.portfolio.positions:
            last_candle = candles[-1]
            self.paper.update_prices({self.config.symbol: last_candle.close})
            self.paper.close_position(self.config.symbol)
            self._record_trade_close(last_candle, "end_of_data")

        duration = time.time() - start_time
        metrics = self._compute_metrics()
        monthly = self._compute_monthly_returns(candles)

        return BacktestResult(
            run_id="",  # filled by caller
            config=self.config,
            metrics=metrics,
            equity_curve=self.equity_curve,
            monthly_returns=monthly,
            trades=self.trades,
            duration_seconds=round(duration, 2),
        )

    def _open_via_engine(self, rec: dict, candle: Candle, cost_pct: float):
        """Open position through PaperTradingEngine — same as approval endpoint."""
        slippage_mult = 1 + cost_pct if rec["direction"] == "long" else 1 - cost_pct
        entry = candle.close * slippage_mult
        size_pct = min(rec.get("size_pct", self.config.max_position_pct), self.config.max_position_pct)

        pos = self.paper.open_position(
            symbol=self.config.symbol,
            direction=rec["direction"],
            current_price=entry,
            size_pct=size_pct,
            recommendation_id=f"bt-{candle.timestamp}",
        )

        if pos:
            # Set stop/TP from recommendation or config defaults
            pos.stop_loss = rec.get("stop_loss") or self._calc_stop(entry, rec["direction"])
            pos.take_profit = rec.get("take_profit") or self._calc_tp(entry, rec["direction"])
            self._open_trade_entry = {
                "time": candle.timestamp,
                "price": entry,
                "direction": rec["direction"],
                "size_usd": pos.size_usd,
                "bar_index": self._bar_index,
            }

    def _calc_stop(self, entry: float, direction: str) -> float | None:
        if self.config.stop_loss_pct is None:
            return None
        pct = self.config.stop_loss_pct / 100.0
        if direction == "long":
            return entry * (1 - pct)
        return entry * (1 + pct)

    def _calc_tp(self, entry: float, direction: str) -> float | None:
        if self.config.take_profit_pct is None:
            return None
        pct = self.config.take_profit_pct / 100.0
        if direction == "long":
            return entry * (1 + pct)
        return entry * (1 - pct)

    def _record_trade_close(self, candle: Candle, reason: str):
        if self._open_trade_entry is None:
            return

        entry = self._open_trade_entry
        exit_price = candle.close
        direction = entry["direction"]
        size_usd = entry["size_usd"]

        if direction == "long":
            pnl_pct = (exit_price - entry["price"]) / entry["price"]
        else:
            pnl_pct = (entry["price"] - exit_price) / entry["price"]

        pnl_usd = size_usd * pnl_pct
        holding_bars = self._bar_index - entry["bar_index"]

        self.trades.append(
            TradeRecord(
                entry_time=entry["time"],
                exit_time=candle.timestamp,
                direction=direction,
                entry_price=round(entry["price"], 2),
                exit_price=round(exit_price, 2),
                size_usd=round(size_usd, 2),
                pnl_usd=round(pnl_usd, 2),
                pnl_pct=round(pnl_pct * 100, 4),
                exit_reason=reason,
                holding_bars=holding_bars,
            )
        )
        self._open_trade_entry = None

    def _record_equity(self, candle: Candle):
        equity = self.paper.portfolio.equity
        peak = max(
            (p["equity"] for p in self.equity_curve),
            default=self.config.starting_equity,
        )
        peak = max(peak, equity)
        dd_pct = ((peak - equity) / peak * 100) if peak > 0 else 0

        self.equity_curve.append({
            "time": candle.timestamp,
            "equity": round(equity, 2),
            "drawdown_pct": round(dd_pct, 4),
        })

    def _should_act(self, rec: dict) -> bool:
        """Check if we should act on a recommendation."""
        if rec["direction"] == "close":
            # Only act on close if we have a position
            return self._get_current_position() is not None
        return True

    def _get_current_position(self):
        for pos in self.paper.portfolio.positions:
            if pos.symbol == self.config.symbol:
                return pos
        return None

    def _compute_metrics(self) -> BacktestMetrics:
        trades = self.trades
        equity_curve = self.equity_curve

        if not trades:
            return BacktestMetrics(
                total_return_pct=0, sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
                max_drawdown_pct=0, max_drawdown_duration_bars=0, win_rate=0,
                profit_factor=0, total_trades=0, avg_trade_pnl_pct=0,
                avg_winning_pct=0, avg_losing_pct=0, max_consecutive_wins=0,
                max_consecutive_losses=0, avg_holding_bars=0, expectancy_pct=0,
            )

        # Basic trade stats
        total_trades = len(trades)
        winners = [t for t in trades if t.pnl_usd > 0]
        losers = [t for t in trades if t.pnl_usd <= 0]
        win_rate = len(winners) / total_trades if total_trades else 0

        avg_pnl_pct = sum(t.pnl_pct for t in trades) / total_trades
        avg_winning = sum(t.pnl_pct for t in winners) / len(winners) if winners else 0
        avg_losing = sum(t.pnl_pct for t in losers) / len(losers) if losers else 0

        gross_profit = sum(t.pnl_usd for t in winners)
        gross_loss = abs(sum(t.pnl_usd for t in losers))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        avg_holding = sum(t.holding_bars for t in trades) / total_trades
        expectancy = win_rate * avg_winning + (1 - win_rate) * avg_losing

        # Consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_streak = 0
        last_was_win = None
        for t in trades:
            is_win = t.pnl_usd > 0
            if is_win == last_was_win:
                current_streak += 1
            else:
                current_streak = 1
            last_was_win = is_win
            if is_win:
                max_consec_wins = max(max_consec_wins, current_streak)
            else:
                max_consec_losses = max(max_consec_losses, current_streak)

        # Return
        final_equity = equity_curve[-1]["equity"] if equity_curve else self.config.starting_equity
        total_return_pct = (final_equity / self.config.starting_equity - 1) * 100

        # Drawdown
        max_dd = max((p["drawdown_pct"] for p in equity_curve), default=0)

        # Max drawdown duration (bars in drawdown)
        max_dd_duration = 0
        current_dd_duration = 0
        for p in equity_curve:
            if p["drawdown_pct"] > 0.01:
                current_dd_duration += 1
                max_dd_duration = max(max_dd_duration, current_dd_duration)
            else:
                current_dd_duration = 0

        # Sharpe / Sortino / Calmar from equity curve returns
        if len(equity_curve) > 1:
            equities = [p["equity"] for p in equity_curve]
            returns = []
            for j in range(1, len(equities)):
                if equities[j - 1] > 0:
                    returns.append((equities[j] - equities[j - 1]) / equities[j - 1])
            if returns:
                import numpy as np
                ret_arr = np.array(returns)
                mean_ret = float(np.mean(ret_arr))
                std_ret = float(np.std(ret_arr, ddof=1)) if len(ret_arr) > 1 else 0

                # Annualize (assume hourly bars)
                ann_factor = math.sqrt(8760)
                sharpe = (mean_ret / std_ret * ann_factor) if std_ret > 0 else 0

                downside = ret_arr[ret_arr < 0]
                downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0
                sortino = (mean_ret / downside_std * ann_factor) if downside_std > 0 else 0

                calmar = (total_return_pct / max_dd) if max_dd > 0 else 0
            else:
                sharpe = sortino = calmar = 0.0
        else:
            sharpe = sortino = calmar = 0.0

        return BacktestMetrics(
            total_return_pct=round(total_return_pct, 4),
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(sortino, 4),
            calmar_ratio=round(calmar, 4),
            max_drawdown_pct=round(max_dd, 4),
            max_drawdown_duration_bars=max_dd_duration,
            win_rate=round(win_rate, 4),
            profit_factor=round(min(profit_factor, 999.99), 4),
            total_trades=total_trades,
            avg_trade_pnl_pct=round(avg_pnl_pct, 4),
            avg_winning_pct=round(avg_winning, 4),
            avg_losing_pct=round(avg_losing, 4),
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses,
            avg_holding_bars=round(avg_holding, 2),
            expectancy_pct=round(expectancy, 4),
        )

    def _compute_monthly_returns(self, candles: list[Candle]) -> list[dict]:
        """Group equity curve into monthly return buckets."""
        if len(self.equity_curve) < 2:
            return []

        monthly: dict[str, list[float]] = defaultdict(list)
        for i, point in enumerate(self.equity_curve):
            dt = datetime.fromtimestamp(point["time"] / 1000, tz=timezone.utc)
            key = dt.strftime("%Y-%m")
            monthly[key].append(point["equity"])

        results = []
        sorted_months = sorted(monthly.keys())
        prev_equity = self.config.starting_equity

        for month in sorted_months:
            equities = monthly[month]
            end_equity = equities[-1]
            ret_pct = (end_equity / prev_equity - 1) * 100 if prev_equity > 0 else 0
            results.append({"month": month, "return_pct": round(ret_pct, 4)})
            prev_equity = end_equity

        return results
