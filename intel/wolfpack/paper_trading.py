"""Paper trading engine — simulates trades from approved recommendations.

Tracks virtual positions, P&L, and portfolio equity.
Stores snapshots to wp_portfolio_snapshots for the frontend equity curve.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from wolfpack.price_utils import round_price

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Market friction constants (easy to tune)
# ---------------------------------------------------------------------------

# Entry/exit slippage in basis points per asset class
# BTC/ETH: 2-5 bps (deep books), altcoins: 5-15 bps (thinner books)
SLIPPAGE_BPS: dict[str, int] = {
    "BTC": 3, "ETH": 4,
    "SOL": 8, "AVAX": 10, "DOGE": 10, "ARB": 12, "LINK": 8,
}
DEFAULT_SLIPPAGE_BPS: int = 10

# Extra adverse slippage on stop-loss fills (forced liquidation into thin book)
STOP_SLIPPAGE_BPS: int = 15  # 0.15%

# Conservative funding rate estimate: 0.005% per hour ≈ 4.4% annualized
FUNDING_RATE_HOURLY: float = 0.00005

# Minimum age (seconds) before a position can be stopped out.
# One full tick cycle (5 min) — simulates signal-to-fill delay.
FILL_DELAY_SECONDS: int = 300


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
    # Wave 2 enrichment fields — all default so existing callers keep working
    mfe: float = 0.0  # max favorable excursion (best unrealized P&L seen)
    mae: float = 0.0  # max adverse excursion (worst unrealized P&L seen)
    accumulated_funding: float = 0.0  # per-position funding cost accumulator
    regime_at_entry: str | None = None
    conviction_at_entry: int | None = None
    entry_slippage_bps: float | None = None


class PaperPortfolio(BaseModel):
    """Current state of the paper trading portfolio."""

    starting_equity: float = 10000.0
    equity: float = 10000.0
    free_collateral: float = 10000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_fees: float = 0.0
    friction_costs: float = 0.0  # Total slippage + funding deducted
    positions: list[PaperPosition] = []
    closed_trades: int = 0
    winning_trades: int = 0


class PaperTradingEngine:
    """Manages a simulated portfolio from approved trade recommendations."""

    def __init__(
        self,
        starting_equity: float = 10000.0,
        commission_bps: float = 5.0,
        persist_trades: bool = True,
        wallet_id: str | None = None,
    ):
        self.commission_bps = commission_bps
        self.persist_trades = persist_trades  # False for backtest — avoids polluting wp_trade_history
        self.wallet_id = wallet_id  # Wave 2: canonical wallet binding
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
        regime_at_entry: str | None = None,
        conviction_at_entry: int | None = None,
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

        # Apply adverse entry slippage (taker spread + market impact)
        slippage_bps = SLIPPAGE_BPS.get(symbol, DEFAULT_SLIPPAGE_BPS)
        slippage_pct = slippage_bps / 10000.0
        if direction == "long":
            entry_price = current_price * (1 + slippage_pct)  # Buy higher
        else:
            entry_price = current_price * (1 - slippage_pct)  # Sell lower
        slippage_cost = abs(entry_price - current_price) / current_price * size_usd
        self.portfolio.friction_costs += slippage_cost
        logger.info(f"Entry slippage {slippage_bps}bps on {symbol}: market ${current_price:.2f} → fill ${entry_price:.2f} (cost ${slippage_cost:.2f})")

        position = PaperPosition(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            current_price=current_price,
            size_usd=size_usd,
            unrealized_pnl=0.0,
            recommendation_id=recommendation_id,
            opened_at=datetime.now(timezone.utc),
            regime_at_entry=regime_at_entry,
            conviction_at_entry=conviction_at_entry,
            entry_slippage_bps=float(slippage_bps),
        )

        # Deduct entry commission
        fee = size_usd * (self.commission_bps / 10000.0)
        self.portfolio.total_fees += fee
        self.portfolio.free_collateral -= fee

        self.portfolio.positions.append(position)
        self.portfolio.free_collateral -= size_usd
        logger.info(f"Opened paper {direction} {symbol} @ ${entry_price:.2f} (mkt ${current_price:.2f}), size ${size_usd:.2f} (fee ${fee:.2f})")
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

            # Apply funding cost (1/12 of hourly rate per 5-min tick)
            funding_cost = self._apply_funding(pos)
            pos.unrealized_pnl -= funding_cost
            pos.accumulated_funding += funding_cost
            self.portfolio.total_fees += funding_cost
            self.portfolio.friction_costs += funding_cost

            # Wave 2: track per-position MFE / MAE for exit analytics
            if pos.unrealized_pnl > pos.mfe:
                pos.mfe = pos.unrealized_pnl
            if pos.unrealized_pnl < pos.mae:
                pos.mae = pos.unrealized_pnl

            total_unrealized += pos.unrealized_pnl

        self.portfolio.unrealized_pnl = total_unrealized
        self.portfolio.equity = (
            self.portfolio.starting_equity
            + self.portfolio.realized_pnl
            + self.portfolio.unrealized_pnl
        )

    def close_position(
        self,
        symbol: str,
        exit_reason: str = "manual",
        regime_at_exit: str | None = None,
    ) -> float:
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

        # Apply adverse exit slippage before calculating P&L
        slippage_bps = SLIPPAGE_BPS.get(pos.symbol, DEFAULT_SLIPPAGE_BPS)
        slippage_pct = slippage_bps / 10000.0
        pre_slip_price = pos.current_price
        if pos.direction == "long":
            pos.current_price = pre_slip_price * (1 - slippage_pct)  # Sell lower
        else:
            pos.current_price = pre_slip_price * (1 + slippage_pct)  # Buy higher
        slippage_cost = abs(pos.current_price - pre_slip_price) / pre_slip_price * pos.size_usd
        self.portfolio.friction_costs += slippage_cost
        self._update_position_pnl(pos)
        logger.info(f"Exit slippage {slippage_bps}bps on {symbol}: ${pre_slip_price:.2f} → ${pos.current_price:.2f} (cost ${slippage_cost:.2f})")

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

        # Compute hold duration for enrichment
        closed_at = datetime.now(timezone.utc)
        try:
            hold_duration_seconds = int((closed_at - pos.opened_at).total_seconds())
        except Exception:
            hold_duration_seconds = None

        # Store closed trade to history with Wave 2 enrichment fields
        self._store_closed_trade(
            pos,
            realized,
            exit_reason=exit_reason,
            regime_at_exit=regime_at_exit,
            hold_duration_seconds=hold_duration_seconds,
            exit_slippage_bps=float(slippage_bps),
        )

        # Recalculate
        self.portfolio.unrealized_pnl = sum(p.unrealized_pnl for p in self.portfolio.positions)
        self.portfolio.equity = (
            self.portfolio.starting_equity
            + self.portfolio.realized_pnl
            + self.portfolio.unrealized_pnl
        )

        logger.info(f"Closed paper {pos.direction} {symbol}: P&L ${realized:.2f}")
        return realized

    def _store_closed_trade(
        self,
        pos: PaperPosition,
        pnl: float,
        exit_reason: str | None = None,
        regime_at_exit: str | None = None,
        hold_duration_seconds: int | None = None,
        exit_slippage_bps: float | None = None,
    ) -> None:
        """Store a closed trade to wp_trade_history. Skipped in backtest mode."""
        if not self.persist_trades:
            return
        try:
            from wolfpack.db import get_db
            db = get_db()
            # Extract strategy name from recommendation_id (pattern: strat-{name}-{symbol}-{ts})
            strategy = None
            rec_id = pos.recommendation_id
            if rec_id and rec_id.startswith("strat-"):
                import re
                m = re.match(r"strat-(.+)-[A-Z]+-\d+$", rec_id)
                if m:
                    strategy = m.group(1)

            row: dict[str, Any] = {
                "symbol": pos.symbol,
                "direction": pos.direction,
                "entry_price": pos.entry_price,
                "exit_price": pos.current_price,
                "size_usd": pos.size_usd,
                "pnl_usd": round(pnl, 2),
                "recommendation_id": pos.recommendation_id,
                "source": "manual",
                "opened_at": pos.opened_at.isoformat(),
                "strategy": strategy,
                # Wave 2 enrichment
                "wallet_id": self.wallet_id,
                "exit_reason": exit_reason,
                "hold_duration_seconds": hold_duration_seconds,
                "entry_slippage_bps": pos.entry_slippage_bps,
                "exit_slippage_bps": exit_slippage_bps,
                "funding_cost_usd": round(pos.accumulated_funding, 4),
                "regime_at_entry": pos.regime_at_entry,
                "regime_at_exit": regime_at_exit,
                "conviction_at_entry": pos.conviction_at_entry,
                "max_favorable_excursion": round(pos.mfe, 4),
                "max_adverse_excursion": round(pos.mae, 4),
            }
            db.table("wp_trade_history").upsert(
                row, on_conflict="recommendation_id"
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to store closed trade: {e}")

    def check_stops(self, prices: dict[str, float]) -> list[tuple[str, str]]:
        """Check stop-losses and take-profits against current prices.
        Skips positions opened less than 60 seconds ago to prevent same-cycle TP/SL triggers.
        Returns list of (symbol, reason) tuples for closed positions."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        triggered: list[tuple[str, str]] = []
        for pos in list(self.portfolio.positions):
            price = prices.get(pos.symbol)
            if price is None:
                continue
            # Skip positions opened recently (signal-to-fill delay simulation)
            if (now - pos.opened_at).total_seconds() < FILL_DELAY_SECONDS:
                continue
            reason = self._check_stop_trigger(pos, price, price)
            if reason:
                if reason == "stop_loss":
                    # Stops fill worse than the stop price (slippage on forced exit)
                    stop_slip = STOP_SLIPPAGE_BPS / 10000.0
                    if pos.direction == "long":
                        pos.current_price = pos.stop_loss * (1 - stop_slip)  # type: ignore[operator]
                    else:
                        pos.current_price = pos.stop_loss * (1 + stop_slip)  # type: ignore[operator]
                    slip_cost = abs(pos.current_price - pos.stop_loss) / pos.stop_loss * pos.size_usd  # type: ignore[operator]
                    self.portfolio.friction_costs += slip_cost
                    logger.info(f"Stop slippage {STOP_SLIPPAGE_BPS}bps on {pos.symbol}: stop ${pos.stop_loss} → fill ${pos.current_price:.2f}")
                else:
                    # TP fills at the take-profit level (already optimistic)
                    pos.current_price = pos.take_profit  # type: ignore[assignment]
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
                if reason == "stop_loss":
                    # Stops fill worse than the stop price
                    stop_slip = STOP_SLIPPAGE_BPS / 10000.0
                    if pos.direction == "long":
                        pos.current_price = pos.stop_loss * (1 - stop_slip)  # type: ignore[operator]
                    else:
                        pos.current_price = pos.stop_loss * (1 + stop_slip)  # type: ignore[operator]
                    slip_cost = abs(pos.current_price - pos.stop_loss) / pos.stop_loss * pos.size_usd  # type: ignore[operator]
                    self.portfolio.friction_costs += slip_cost
                    logger.info(f"Stop slippage {STOP_SLIPPAGE_BPS}bps on {pos.symbol} (OHLC): stop ${pos.stop_loss} → fill ${pos.current_price:.2f}")
                else:
                    pos.current_price = pos.take_profit  # type: ignore[assignment]
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

    @staticmethod
    def _apply_funding(pos: PaperPosition) -> float:
        """Apply Hyperliquid funding rate cost. Called every tick (5 min).

        Funding is paid/received every hour on Hyperliquid.
        We apply 1/12th per tick (5 min tick, 60 min funding period).
        Conservatively charges both longs and shorts.
        """
        return pos.size_usd * FUNDING_RATE_HOURLY / 12

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
                pos.stop_loss = round_price(new_stop)
        else:
            # Short: track lowest price seen
            if pos.trailing_stop_peak is None or pos.current_price < pos.trailing_stop_peak:
                pos.trailing_stop_peak = pos.current_price
            # Trailing stop = trough * (1 + trail%)
            new_stop = pos.trailing_stop_peak * (1.0 + trail_frac)
            # Only tighten (lower for shorts), never loosen
            if pos.stop_loss is None or new_stop < pos.stop_loss:
                pos.stop_loss = round_price(new_stop)

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
            "friction_costs": round(self.portfolio.friction_costs, 2),
            "positions": positions_data,
        }

    def store_snapshot(self, exchange: str, regime_state: str | None = None) -> dict:
        """Take a snapshot and store it to Supabase.

        Resilient to missing DB columns — retries without problematic fields.
        """
        from wolfpack.db import get_db

        snapshot = self.take_snapshot(exchange)

        # Wave 2 enrichment: wallet_id + position/exposure/regime columns
        snapshot["wallet_id"] = self.wallet_id
        snapshot["open_position_count"] = len(self.portfolio.positions)
        snapshot["total_exposure_usd"] = round(
            sum(p.size_usd for p in self.portfolio.positions), 2
        )
        snapshot["regime_state"] = regime_state

        db = get_db()
        try:
            result = db.table("wp_portfolio_snapshots").insert(snapshot).execute()
            return result.data[0] if result.data else snapshot
        except Exception as e:
            error_msg = str(e).lower()
            if "column" in error_msg and "schema" in error_msg:
                # Missing column — retry without newer fields
                for key in [
                    "friction_costs",
                    "wallet_id",
                    "open_position_count",
                    "total_exposure_usd",
                    "regime_state",
                ]:
                    snapshot.pop(key, None)
                try:
                    result = db.table("wp_portfolio_snapshots").insert(snapshot).execute()
                    return result.data[0] if result.data else snapshot
                except Exception:
                    pass
            logger.warning(f"Failed to store snapshot: {e}")
            return snapshot
