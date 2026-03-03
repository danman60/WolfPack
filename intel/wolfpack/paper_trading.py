"""Paper trading engine — simulates trades from approved recommendations.

Tracks virtual positions, P&L, and portfolio equity.
Stores snapshots to wp_portfolio_snapshots for the frontend equity curve.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PaperPosition(BaseModel):
    """A simulated open position."""

    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    current_price: float
    size_usd: float
    unrealized_pnl: float
    recommendation_id: str
    opened_at: datetime
    stop_loss: float | None = None
    take_profit: float | None = None


class PaperPortfolio(BaseModel):
    """Current state of the paper trading portfolio."""

    starting_equity: float = 10000.0
    equity: float = 10000.0
    free_collateral: float = 10000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    positions: list[PaperPosition] = []
    closed_trades: int = 0
    winning_trades: int = 0


class PaperTradingEngine:
    """Manages a simulated portfolio from approved trade recommendations."""

    def __init__(self, starting_equity: float = 10000.0):
        self.portfolio = PaperPortfolio(
            starting_equity=starting_equity,
            equity=starting_equity,
            free_collateral=starting_equity,
        )

    def open_position(
        self,
        symbol: str,
        direction: str,
        current_price: float,
        size_pct: float,
        recommendation_id: str,
    ) -> PaperPosition | None:
        """Open a new paper position.

        Args:
            symbol: Asset symbol (e.g., "BTC")
            direction: "long" or "short"
            current_price: Current market price (used as entry)
            size_pct: Position size as % of equity (1-25)
            recommendation_id: ID of the approved recommendation
        """
        # Check if already have a position in this symbol
        for pos in self.portfolio.positions:
            if pos.symbol == symbol:
                logger.warning(f"Already have a {pos.direction} position in {symbol}")
                return None

        size_usd = self.portfolio.equity * (min(size_pct, 25) / 100.0)
        if size_usd > self.portfolio.free_collateral:
            logger.warning(f"Insufficient collateral for {symbol}: need ${size_usd:.2f}, have ${self.portfolio.free_collateral:.2f}")
            return None

        position = PaperPosition(
            symbol=symbol,
            direction=direction,
            entry_price=current_price,
            current_price=current_price,
            size_usd=size_usd,
            unrealized_pnl=0.0,
            recommendation_id=recommendation_id,
            opened_at=datetime.now(timezone.utc),
        )

        self.portfolio.positions.append(position)
        self.portfolio.free_collateral -= size_usd
        logger.info(f"Opened paper {direction} {symbol} @ ${current_price:.2f}, size ${size_usd:.2f}")
        return position

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices for all open positions and recalculate P&L."""
        total_unrealized = 0.0

        for pos in self.portfolio.positions:
            if pos.symbol in prices:
                pos.current_price = prices[pos.symbol]

            # Calculate unrealized P&L
            if pos.direction == "long":
                pnl_pct = (pos.current_price - pos.entry_price) / pos.entry_price
            else:
                pnl_pct = (pos.entry_price - pos.current_price) / pos.entry_price

            pos.unrealized_pnl = pos.size_usd * pnl_pct
            total_unrealized += pos.unrealized_pnl

        self.portfolio.unrealized_pnl = total_unrealized
        self.portfolio.equity = (
            self.portfolio.starting_equity
            + self.portfolio.realized_pnl
            + self.portfolio.unrealized_pnl
        )

    def close_position(self, symbol: str) -> float:
        """Close a position and realize P&L. Returns realized P&L."""
        pos = None
        idx = -1
        for i, p in enumerate(self.portfolio.positions):
            if p.symbol == symbol:
                pos = p
                idx = i
                break

        if pos is None:
            logger.warning(f"No open position in {symbol}")
            return 0.0

        realized = pos.unrealized_pnl
        self.portfolio.realized_pnl += realized
        self.portfolio.free_collateral += pos.size_usd + realized
        self.portfolio.positions.pop(idx)

        self.portfolio.closed_trades += 1
        if realized > 0:
            self.portfolio.winning_trades += 1

        # Recalculate
        self.portfolio.unrealized_pnl = sum(p.unrealized_pnl for p in self.portfolio.positions)
        self.portfolio.equity = (
            self.portfolio.starting_equity
            + self.portfolio.realized_pnl
            + self.portfolio.unrealized_pnl
        )

        logger.info(f"Closed paper {pos.direction} {symbol}: P&L ${realized:.2f}")
        return realized

    def check_stops(self, prices: dict[str, float]) -> list[tuple[str, str]]:
        """Check stop-losses and take-profits against current prices.
        Returns list of (symbol, reason) tuples for closed positions."""
        triggered: list[tuple[str, str]] = []
        for pos in list(self.portfolio.positions):
            price = prices.get(pos.symbol)
            if price is None:
                continue
            reason = self._check_stop_trigger(pos, price, price)
            if reason:
                pos.current_price = pos.stop_loss if reason == "stop_loss" else pos.take_profit  # type: ignore[assignment]
                self._update_position_pnl(pos)
                self.close_position(pos.symbol)
                triggered.append((pos.symbol, reason))
        return triggered

    def check_stops_ohlc(self, candles: dict[str, Any]) -> list[tuple[str, str]]:
        """Check stop-losses and take-profits against OHLC candle data.
        Uses high/low to catch intra-bar triggers. Exit price = stop/TP level.
        candles: {symbol: object with .high, .low attributes}
        Returns list of (symbol, reason) tuples for closed positions."""
        triggered: list[tuple[str, str]] = []
        for pos in list(self.portfolio.positions):
            candle = candles.get(pos.symbol)
            if candle is None:
                continue
            high = candle.high if hasattr(candle, "high") else candle["high"]
            low = candle.low if hasattr(candle, "low") else candle["low"]
            reason = self._check_stop_trigger(pos, high, low)
            if reason:
                exit_price = pos.stop_loss if reason == "stop_loss" else pos.take_profit  # type: ignore[assignment]
                pos.current_price = exit_price  # type: ignore[assignment]
                self._update_position_pnl(pos)
                self.close_position(pos.symbol)
                triggered.append((pos.symbol, reason))
        return triggered

    def _check_stop_trigger(self, pos: PaperPosition, high: float, low: float) -> str | None:
        """Check if a position's SL/TP was triggered given price range.
        Returns 'stop_loss', 'take_profit', or None."""
        if pos.direction == "long":
            if pos.stop_loss is not None and low <= pos.stop_loss:
                return "stop_loss"
            if pos.take_profit is not None and high >= pos.take_profit:
                return "take_profit"
        else:  # short
            if pos.stop_loss is not None and high >= pos.stop_loss:
                return "stop_loss"
            if pos.take_profit is not None and low <= pos.take_profit:
                return "take_profit"
        return None

    def _update_position_pnl(self, pos: PaperPosition) -> None:
        """Recalculate unrealized P&L for a single position."""
        if pos.direction == "long":
            pnl_pct = (pos.current_price - pos.entry_price) / pos.entry_price
        else:
            pnl_pct = (pos.entry_price - pos.current_price) / pos.entry_price
        pos.unrealized_pnl = pos.size_usd * pnl_pct

    def take_snapshot(self, exchange: str) -> dict[str, Any]:
        """Generate a portfolio snapshot dict for Supabase storage."""
        positions_data = [
            {
                "symbol": p.symbol,
                "direction": p.direction,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "size_usd": p.size_usd,
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "recommendation_id": p.recommendation_id,
                "opened_at": p.opened_at.isoformat(),
            }
            for p in self.portfolio.positions
        ]

        return {
            "exchange_id": exchange,
            "equity": round(self.portfolio.equity, 2),
            "free_collateral": round(self.portfolio.free_collateral, 2),
            "unrealized_pnl": round(self.portfolio.unrealized_pnl, 2),
            "realized_pnl": round(self.portfolio.realized_pnl, 2),
            "positions": positions_data,
        }

    def store_snapshot(self, exchange: str) -> dict:
        """Take a snapshot and store it to Supabase."""
        from wolfpack.db import get_db

        snapshot = self.take_snapshot(exchange)
        db = get_db()
        result = db.table("wp_portfolio_snapshots").insert(snapshot).execute()
        return result.data[0] if result.data else snapshot
