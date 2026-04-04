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
    trailing_stop_pct: float | None = None  # e.g. 2.0 = trail 2% from peak
    trailing_stop_peak: float | None = None  # highest (long) or lowest (short) price seen


class PaperPortfolio(BaseModel):
    """Current state of the paper trading portfolio."""

    starting_equity: float = 10000.0
    equity: float = 10000.0
    free_collateral: float = 10000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_fees: float = 0.0
    positions: list[PaperPosition] = []
    closed_trades: int = 0
    winning_trades: int = 0


class PaperTradingEngine:
    """Manages a simulated portfolio from approved trade recommendations."""

    def __init__(self, starting_equity: float = 10000.0, commission_bps: float = 5.0, persist_trades: bool = True):
        self.commission_bps = commission_bps
        self.persist_trades = persist_trades  # False for backtest — avoids polluting wp_trade_history
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
        max_positions_per_symbol: int = 3,
    ) -> PaperPosition | None:
        """Open a new paper position.

        Args:
            symbol: Asset symbol (e.g., "BTC")
            direction: "long" or "short"
            current_price: Current market price (used as entry)
            size_pct: Position size as % of equity (1-25)
            recommendation_id: ID of the approved recommendation
            max_positions_per_symbol: Max concurrent positions allowed per symbol (pyramiding)
        """
        # Check existing positions in this symbol
        existing = [pos for pos in self.portfolio.positions if pos.symbol == symbol]
        if len(existing) >= max_positions_per_symbol:
            logger.warning(f"Already have {len(existing)} positions in {symbol} (max {max_positions_per_symbol})")
            return None
        # Block opposite-direction entries (no hedging) — only allow same-direction pyramiding
        for pos in existing:
            if pos.direction != direction:
                logger.warning(f"Cannot open {direction} {symbol} — already have {pos.direction} position (no hedging)")
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

        # Deduct entry commission
        fee = size_usd * (self.commission_bps / 10000.0)
        self.portfolio.total_fees += fee
        self.portfolio.free_collateral -= fee

        self.portfolio.positions.append(position)
        self.portfolio.free_collateral -= size_usd
        logger.info(f"Opened paper {direction} {symbol} @ ${current_price:.2f}, size ${size_usd:.2f} (fee ${fee:.2f})")
        return position

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices for all open positions and recalculate P&L.

        Also updates trailing stop peaks and dynamically adjusts stop-loss
        levels for positions with trailing stops enabled.
        """
        total_unrealized = 0.0

        for pos in self.portfolio.positions:
            if pos.symbol in prices:
                pos.current_price = prices[pos.symbol]

            # Update trailing stop peak and adjust stop level
            if pos.trailing_stop_pct is not None and pos.trailing_stop_pct > 0:
                self._update_trailing_stop(pos)

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

        # Deduct exit commission
        fee = pos.size_usd * (self.commission_bps / 10000.0)
        self.portfolio.total_fees += fee
        realized = pos.unrealized_pnl - fee
        self.portfolio.realized_pnl += realized
        self.portfolio.free_collateral += pos.size_usd + realized
        self.portfolio.positions.pop(idx)

        self.portfolio.closed_trades += 1
        if realized > 0:
            self.portfolio.winning_trades += 1

        # Store closed trade to history
        self._store_closed_trade(pos, realized)

        # Recalculate
        self.portfolio.unrealized_pnl = sum(p.unrealized_pnl for p in self.portfolio.positions)
        self.portfolio.equity = (
            self.portfolio.starting_equity
            + self.portfolio.realized_pnl
            + self.portfolio.unrealized_pnl
        )

        logger.info(f"Closed paper {pos.direction} {symbol}: P&L ${realized:.2f}")
        return realized

    def _store_closed_trade(self, pos: PaperPosition, pnl: float) -> None:
        """Store a closed trade to wp_trade_history. Skipped in backtest mode."""
        if not self.persist_trades:
            return
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_trade_history").upsert({
                "symbol": pos.symbol,
                "direction": pos.direction,
                "entry_price": pos.entry_price,
                "exit_price": pos.current_price,
                "size_usd": pos.size_usd,
                "pnl_usd": round(pnl, 2),
                "recommendation_id": pos.recommendation_id,
                "source": "manual",
                "opened_at": pos.opened_at.isoformat(),
            }, on_conflict="recommendation_id").execute()
        except Exception as e:
            logger.warning(f"Failed to store closed trade: {e}")

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

    @staticmethod
    def _update_trailing_stop(pos: PaperPosition) -> None:
        """Update trailing stop peak and dynamically tighten stop-loss.

        For longs: tracks highest price, stop trails below peak
        For shorts: tracks lowest price, stop trails above trough
        """
        if pos.trailing_stop_pct is None or pos.trailing_stop_pct <= 0:
            return

        trail_frac = pos.trailing_stop_pct / 100.0

        if pos.direction == "long":
            # Track highest price seen
            if pos.trailing_stop_peak is None or pos.current_price > pos.trailing_stop_peak:
                pos.trailing_stop_peak = pos.current_price
            # Trailing stop = peak * (1 - trail%)
            new_stop = pos.trailing_stop_peak * (1.0 - trail_frac)
            # Only tighten, never loosen
            if pos.stop_loss is None or new_stop > pos.stop_loss:
                pos.stop_loss = round(new_stop, 2)
        else:
            # Short: track lowest price seen
            if pos.trailing_stop_peak is None or pos.current_price < pos.trailing_stop_peak:
                pos.trailing_stop_peak = pos.current_price
            # Trailing stop = trough * (1 + trail%)
            new_stop = pos.trailing_stop_peak * (1.0 + trail_frac)
            # Only tighten (lower for shorts), never loosen
            if pos.stop_loss is None or new_stop < pos.stop_loss:
                pos.stop_loss = round(new_stop, 2)

    def enable_trailing_stop(self, symbol: str, trail_pct: float) -> bool:
        """Enable trailing stop on an open position.

        Args:
            symbol: Asset symbol
            trail_pct: Trail distance as percentage (e.g. 2.0 = 2%)

        Returns True if trailing stop was enabled, False if position not found.
        """
        for pos in self.portfolio.positions:
            if pos.symbol == symbol:
                pos.trailing_stop_pct = trail_pct
                pos.trailing_stop_peak = pos.current_price
                # Immediately set initial trailing stop
                self._update_trailing_stop(pos)
                logger.info(f"Trailing stop enabled for {symbol}: {trail_pct}% trail from {pos.current_price}")
                return True
        return False

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
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "trailing_stop_pct": p.trailing_stop_pct,
                "trailing_stop_peak": p.trailing_stop_peak,
            }
            for p in self.portfolio.positions
        ]

        return {
            "exchange_id": exchange,
            "equity": round(self.portfolio.equity, 2),
            "free_collateral": round(self.portfolio.free_collateral, 2),
            "unrealized_pnl": round(self.portfolio.unrealized_pnl, 2),
            "realized_pnl": round(self.portfolio.realized_pnl, 2),
            "total_fees": round(self.portfolio.total_fees, 2),
            "positions": positions_data,
        }

    def store_snapshot(self, exchange: str) -> dict:
        """Take a snapshot and store it to Supabase."""
        from wolfpack.db import get_db

        snapshot = self.take_snapshot(exchange)
        db = get_db()
        result = db.table("wp_portfolio_snapshots").insert(snapshot).execute()
        return result.data[0] if result.data else snapshot
