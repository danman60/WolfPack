"""Live Trading Engine — wraps HyperliquidTrader with PaperTradingEngine's interface.

Allows AutoTrader to execute real trades on Hyperliquid without changing its logic.
The adapter pattern: AutoTrader calls self.engine.open_position() — this class routes
to HyperliquidTrader.place_order() instead of simulating.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from wolfpack.config import settings
from wolfpack.price_utils import round_price

logger = logging.getLogger(__name__)


@dataclass
class LivePosition:
    """Mirrors PaperPosition but tracks real exchange state."""

    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    current_price: float
    size_usd: float
    size_units: float  # actual asset units on exchange
    unrealized_pnl: float = 0.0
    recommendation_id: str = ""
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stop_loss: float | None = None
    take_profit: float | None = None
    stop_order_id: int | None = None  # exchange order ID for SL
    tp_order_id: int | None = None  # exchange order ID for TP
    trailing_stop_pct: float | None = None
    trailing_stop_peak: float | None = None  # match PaperPosition field name
    # Wave 3 enrichment fields — defaults keep existing callers working
    mfe: float = 0.0
    mae: float = 0.0
    accumulated_funding: float = 0.0
    regime_at_entry: str | None = None
    conviction_at_entry: int | None = None
    entry_slippage_bps: float | None = None


@dataclass
class LivePortfolio:
    """Portfolio state from real Hyperliquid account."""

    starting_equity: float = 1000.0
    equity: float = 1000.0
    free_collateral: float = 1000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_fees: float = 0.0
    positions: list[LivePosition] = field(default_factory=list)
    closed_trades: int = 0
    winning_trades: int = 0


class LiveTradingEngine:
    """Drop-in replacement for PaperTradingEngine that executes on Hyperliquid.

    All public methods are synchronous to match PaperTradingEngine's interface.
    Async HyperliquidTrader calls are bridged via _run_async().
    """

    def __init__(
        self,
        starting_equity: float = 1000.0,
        commission_bps: float = 5.0,
        persist_trades: bool = True,
        wallet_id: str | None = None,
    ):
        from wolfpack.exchanges.hyperliquid_trading import HyperliquidTrader

        if not settings.hyperliquid_private_key:
            raise ValueError("HYPERLIQUID_PRIVATE_KEY required for live trading")

        self._trader = HyperliquidTrader(settings.hyperliquid_private_key)
        self.commission_bps = commission_bps
        self.persist_trades = persist_trades
        self.wallet_id = wallet_id  # Wave 3: canonical wallet binding
        self.portfolio = LivePortfolio(
            starting_equity=starting_equity,
            equity=starting_equity,
            free_collateral=starting_equity,
        )
        self._synced = False

    def _run_async(self, coro):
        """Bridge async coroutine to sync context.

        Handles the case where we're called from within an already-running
        event loop (e.g., FastAPI/uvicorn) by using a new thread.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an async context — run in a separate thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=30)
        else:
            return asyncio.run(coro)

    async def sync_from_exchange(self):
        """Pull real portfolio state from Hyperliquid clearinghouse."""
        try:
            positions = await self._trader.get_positions()
            self.portfolio.positions.clear()
            total_unrealized = 0.0

            for pos_data in positions:
                pos_info = pos_data.get("position", {})
                coin = pos_info.get("coin", "")
                size = float(pos_info.get("szi", "0"))
                if abs(size) < 1e-10:
                    continue

                entry_px = float(pos_info.get("entryPx", "0"))
                unrealized = float(pos_info.get("unrealizedPnl", "0"))

                live_pos = LivePosition(
                    symbol=coin,
                    direction="long" if size > 0 else "short",
                    entry_price=entry_px,
                    current_price=entry_px,
                    size_usd=abs(size) * entry_px,
                    size_units=abs(size),
                    unrealized_pnl=unrealized,
                )
                self.portfolio.positions.append(live_pos)
                total_unrealized += unrealized

            self.portfolio.unrealized_pnl = total_unrealized
            self._synced = True

        except Exception as e:
            logger.error(f"[live-engine] Failed to sync from exchange: {e}")

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
    ) -> Optional[LivePosition]:
        """Open a real position on Hyperliquid.

        Signature matches PaperTradingEngine.open_position() exactly so
        AutoTrader can use this as a drop-in replacement.
        """
        # Check existing positions in this symbol
        existing = [pos for pos in self.portfolio.positions if pos.symbol == symbol]
        if len(existing) >= max_positions_per_symbol:
            logger.warning(f"[live-engine] Already have {len(existing)} positions in {symbol} (max {max_positions_per_symbol})")
            return None
        # Block opposite-direction entries (no hedging)
        for pos in existing:
            if pos.direction != direction:
                logger.warning(f"[live-engine] Cannot open {direction} {symbol} — already have {pos.direction} position (no hedging)")
                return None

        size_usd = self.portfolio.equity * (min(size_pct, 25) / 100.0)

        if size_usd > self.portfolio.free_collateral:
            logger.warning(f"[live-engine] Insufficient collateral: need ${size_usd:.2f}, have ${self.portfolio.free_collateral:.2f}")
            return None

        # Minimum equity guard
        if self.portfolio.equity < 100:
            logger.warning(f"[live-engine] Equity below $100 floor (${self.portfolio.equity:.2f}), blocking trade")
            return None

        if current_price <= 0:
            logger.error(f"[live-engine] Invalid entry price: {current_price}")
            return None

        # Convert USD to asset units
        size_units = size_usd / current_price
        is_buy = direction == "long"

        # Apply slippage for market order (0.1%)
        if is_buy:
            order_price = round_price(current_price * 1.001)
        else:
            order_price = round_price(current_price * 0.999)

        # Place the order on exchange
        try:
            result = self._run_async(
                self._trader.place_order(
                    symbol=symbol,
                    is_buy=is_buy,
                    size=round(size_units, 6),
                    price=order_price,
                    order_type="market",
                )
            )

            if result.get("status") == "err":
                logger.error(f"[live-engine] Order rejected: {result}")
                return None

            logger.info(f"[live-engine] LIVE ORDER: {direction} {symbol} ${size_usd:.2f} ({size_units:.6f} units) @ ${order_price}")

        except Exception as e:
            logger.error(f"[live-engine] Order failed: {e}")
            return None

        # Deduct commission
        fee = size_usd * (self.commission_bps / 10000.0)
        self.portfolio.total_fees += fee
        self.portfolio.free_collateral -= fee

        # Create position tracking
        # Market-order slippage pad = 0.1% = 10 bps (from order_price calc above)
        pos = LivePosition(
            symbol=symbol,
            direction=direction,
            entry_price=current_price,
            current_price=current_price,
            size_usd=size_usd,
            size_units=size_units,
            unrealized_pnl=0.0,
            recommendation_id=recommendation_id,
            regime_at_entry=regime_at_entry,
            conviction_at_entry=conviction_at_entry,
            entry_slippage_bps=10.0,
        )

        self.portfolio.positions.append(pos)
        self.portfolio.free_collateral -= size_usd

        # Store to DB
        if self.persist_trades:
            self._store_open_trade(pos)

        return pos

    def close_position(
        self,
        symbol: str,
        exit_reason: str = "manual",
        regime_at_exit: str | None = None,
    ) -> float:
        """Close a real position via reduce-only market order. Returns realized P&L."""
        pos = None
        idx = -1
        for i, p in enumerate(self.portfolio.positions):
            if p.symbol == symbol:
                pos = p
                idx = i
                break

        if pos is None:
            logger.warning(f"[live-engine] No position found for {symbol}")
            return 0.0

        is_buy = pos.direction == "short"  # opposite direction to close

        # Wide slippage for market close (0.5% = 50 bps)
        exit_slippage_bps = 50.0
        if is_buy:
            close_price = round_price(pos.current_price * 1.005)
        else:
            close_price = round_price(pos.current_price * 0.995)

        try:
            result = self._run_async(
                self._trader.place_order(
                    symbol=symbol,
                    is_buy=is_buy,
                    size=round(pos.size_units, 6),
                    price=close_price,
                    reduce_only=True,
                    order_type="market",
                )
            )

            if result.get("status") == "err":
                logger.error(f"[live-engine] Close rejected: {result}")
                return 0.0

        except Exception as e:
            logger.error(f"[live-engine] Close failed: {e}")
            return 0.0

        # Cancel any SL/TP orders
        self._cancel_stop_orders(pos)

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

        # Store closed trade with Wave 3 enrichment
        self._store_closed_trade(
            pos,
            realized,
            exit_reason=exit_reason,
            regime_at_exit=regime_at_exit,
            hold_duration_seconds=hold_duration_seconds,
            exit_slippage_bps=exit_slippage_bps,
        )

        # Recalculate
        self.portfolio.unrealized_pnl = sum(p.unrealized_pnl for p in self.portfolio.positions)
        self.portfolio.equity = (
            self.portfolio.starting_equity
            + self.portfolio.realized_pnl
            + self.portfolio.unrealized_pnl
        )

        logger.info(f"[live-engine] CLOSED {pos.direction} {symbol}: P&L ${realized:.2f}")
        return realized

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices for all open positions and recalculate P&L."""
        for pos in self.portfolio.positions:
            if pos.symbol in prices:
                pos.current_price = prices[pos.symbol]

            # Update trailing stop
            if pos.trailing_stop_pct is not None and pos.trailing_stop_pct > 0:
                self._update_trailing_stop(pos)

            if pos.direction == "long":
                pnl_pct = (pos.current_price - pos.entry_price) / pos.entry_price
            else:
                pnl_pct = (pos.entry_price - pos.current_price) / pos.entry_price
            pos.unrealized_pnl = pos.size_usd * pnl_pct

        self.portfolio.unrealized_pnl = sum(p.unrealized_pnl for p in self.portfolio.positions)
        self.portfolio.equity = (
            self.portfolio.starting_equity
            + self.portfolio.realized_pnl
            + self.portfolio.unrealized_pnl
        )

    def check_stops(self, prices: dict[str, float]) -> list[tuple[str, str]]:
        """Check SL/TP levels against current prices.

        In live mode, SL/TP are also placed as exchange limit orders (belt-and-suspenders).
        This method acts as a safety net and handles trailing stops.
        Skips positions opened less than 60 seconds ago to prevent same-cycle triggers.
        Returns list of (symbol, reason) tuples for closed positions.
        """
        now = datetime.now(timezone.utc)
        triggered: list[tuple[str, str]] = []

        for pos in list(self.portfolio.positions):
            price = prices.get(pos.symbol)
            if price is None:
                continue

            # Skip positions opened in the same cycle
            if (now - pos.opened_at).total_seconds() < 60:
                continue

            pos.current_price = price

            # Update trailing stop
            if pos.trailing_stop_pct is not None and pos.trailing_stop_pct > 0:
                old_stop = pos.stop_loss
                self._update_trailing_stop(pos)
                # If trailing stop tightened, update exchange order
                if pos.stop_loss != old_stop and pos.stop_loss is not None:
                    self._cancel_stop_orders(pos, tp=False)
                    self._place_stop_order(pos, pos.stop_loss)

            # Calculate unrealized PnL
            if pos.direction == "long":
                pnl_pct = (price - pos.entry_price) / pos.entry_price
            else:
                pnl_pct = (pos.entry_price - price) / pos.entry_price
            pos.unrealized_pnl = pos.size_usd * pnl_pct

            # Check triggers (safety net — exchange orders should fire first)
            reason = self._check_stop_trigger(pos, price, price)
            if reason:
                pos.current_price = pos.stop_loss if reason == "stop_loss" else pos.take_profit  # type: ignore[assignment]
                self._update_position_pnl(pos)
                self.close_position(pos.symbol)
                triggered.append((pos.symbol, reason))

        # Recalculate portfolio
        self.portfolio.unrealized_pnl = sum(p.unrealized_pnl for p in self.portfolio.positions)
        self.portfolio.equity = (
            self.portfolio.starting_equity
            + self.portfolio.realized_pnl
            + self.portfolio.unrealized_pnl
        )

        return triggered

    def check_stops_ohlc(self, candles: dict[str, Any]) -> list[tuple[str, str]]:
        """Check stops against OHLC candle data.

        For live trading, stops are on exchange — this is a safety net.
        Uses high/low to catch intra-bar triggers.
        """
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
                self._update_trailing_stop(pos)
                logger.info(f"[live-engine] Trailing stop enabled for {symbol}: {trail_pct}% trail from {pos.current_price}")
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
                "size_units": p.size_units,
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
            "source": "live",
        }

    def store_snapshot(self, exchange: str) -> dict:
        """Take a snapshot and store it to Supabase."""
        from wolfpack.db import get_db

        snapshot = self.take_snapshot(exchange)
        db = get_db()
        result = db.table("wp_portfolio_snapshots").insert(snapshot).execute()
        return result.data[0] if result.data else snapshot

    def place_exchange_stops(self, symbol: str) -> dict:
        """Place SL/TP orders on exchange for an open position. Call after setting pos.stop_loss/take_profit."""
        result = {"sl_placed": False, "tp_placed": False}
        for pos in self.portfolio.positions:
            if pos.symbol == symbol:
                if pos.stop_loss and not pos.stop_order_id:
                    self._place_stop_order(pos, pos.stop_loss)
                    result["sl_placed"] = pos.stop_order_id is not None
                    if not result["sl_placed"]:
                        logger.critical(f"[live-engine] SL ORDER FAILED for {symbol} @ ${pos.stop_loss}")
                if pos.take_profit and not pos.tp_order_id:
                    self._place_tp_order(pos, pos.take_profit)
                    result["tp_placed"] = pos.tp_order_id is not None
                break
        return result

    def verify_stops(self) -> list[dict]:
        """Cross-reference exchange open orders vs positions with SL/TP. Returns list of issues."""
        issues = []
        try:
            open_orders = self._run_async(self._trader.get_open_orders())
            order_ids = {o.get("oid") for o in open_orders}

            for pos in self.portfolio.positions:
                if pos.stop_loss and pos.stop_order_id and pos.stop_order_id not in order_ids:
                    issues.append({"symbol": pos.symbol, "issue": "SL order missing from exchange", "expected_id": pos.stop_order_id})
                    # Re-place the stop
                    self._place_stop_order(pos, pos.stop_loss)
                if pos.take_profit and pos.tp_order_id and pos.tp_order_id not in order_ids:
                    issues.append({"symbol": pos.symbol, "issue": "TP order missing from exchange", "expected_id": pos.tp_order_id})
                    self._place_tp_order(pos, pos.take_profit)
        except Exception as e:
            logger.error(f"[live-engine] Stop verification failed: {e}")
        return issues

    # --- Exchange order management ---

    def _place_stop_order(self, pos: LivePosition, stop_price: float):
        """Place a stop-loss limit order on exchange."""
        try:
            is_buy = pos.direction == "short"  # opposite direction
            result = self._run_async(
                self._trader.place_order(
                    symbol=pos.symbol,
                    is_buy=is_buy,
                    size=round(pos.size_units, 6),
                    price=round_price(stop_price),
                    reduce_only=True,
                    order_type="limit",
                )
            )
            if result.get("status") != "err":
                statuses = result.get("response", {}).get("data", {}).get("statuses", [])
                if statuses and "resting" in statuses[0]:
                    pos.stop_order_id = statuses[0]["resting"].get("oid")
            logger.info(f"[live-engine] SL order placed for {pos.symbol} @ ${stop_price}")
        except Exception as e:
            logger.error(f"[live-engine] Failed to place SL order: {e}")

    def _place_tp_order(self, pos: LivePosition, tp_price: float):
        """Place a take-profit limit order on exchange."""
        try:
            is_buy = pos.direction == "short"
            result = self._run_async(
                self._trader.place_order(
                    symbol=pos.symbol,
                    is_buy=is_buy,
                    size=round(pos.size_units, 6),
                    price=round_price(tp_price),
                    reduce_only=True,
                    order_type="limit",
                )
            )
            if result.get("status") != "err":
                statuses = result.get("response", {}).get("data", {}).get("statuses", [])
                if statuses and "resting" in statuses[0]:
                    pos.tp_order_id = statuses[0]["resting"].get("oid")
            logger.info(f"[live-engine] TP order placed for {pos.symbol} @ ${tp_price}")
        except Exception as e:
            logger.error(f"[live-engine] Failed to place TP order: {e}")

    def _cancel_stop_orders(self, pos: LivePosition, sl: bool = True, tp: bool = True):
        """Cancel SL and/or TP orders on exchange."""
        try:
            if sl and pos.stop_order_id:
                self._run_async(
                    self._trader.cancel_order(pos.symbol, pos.stop_order_id)
                )
                pos.stop_order_id = None
            if tp and pos.tp_order_id:
                self._run_async(
                    self._trader.cancel_order(pos.symbol, pos.tp_order_id)
                )
                pos.tp_order_id = None
        except Exception as e:
            logger.error(f"[live-engine] Failed to cancel orders: {e}")

    # --- Stop/TP trigger logic (mirrors PaperTradingEngine) ---

    @staticmethod
    def _check_stop_trigger(pos: LivePosition, high: float, low: float) -> str | None:
        """Check if a position's SL/TP was triggered given price range."""
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
    def _update_position_pnl(pos: LivePosition) -> None:
        """Recalculate unrealized P&L for a single position."""
        if pos.direction == "long":
            pnl_pct = (pos.current_price - pos.entry_price) / pos.entry_price
        else:
            pnl_pct = (pos.entry_price - pos.current_price) / pos.entry_price
        pos.unrealized_pnl = pos.size_usd * pnl_pct

    @staticmethod
    def _update_trailing_stop(pos: LivePosition) -> None:
        """Update trailing stop peak and dynamically tighten stop-loss."""
        if pos.trailing_stop_pct is None or pos.trailing_stop_pct <= 0:
            return

        trail_frac = pos.trailing_stop_pct / 100.0

        if pos.direction == "long":
            if pos.trailing_stop_peak is None or pos.current_price > pos.trailing_stop_peak:
                pos.trailing_stop_peak = pos.current_price
            new_stop = pos.trailing_stop_peak * (1.0 - trail_frac)
            if pos.stop_loss is None or new_stop > pos.stop_loss:
                pos.stop_loss = round_price(new_stop)
        else:
            if pos.trailing_stop_peak is None or pos.current_price < pos.trailing_stop_peak:
                pos.trailing_stop_peak = pos.current_price
            new_stop = pos.trailing_stop_peak * (1.0 + trail_frac)
            if pos.stop_loss is None or new_stop < pos.stop_loss:
                pos.stop_loss = round_price(new_stop)

    # --- DB persistence ---

    def _store_open_trade(self, pos: LivePosition) -> None:
        """Store an opened live trade.

        NOTE: wp_auto_trades writes removed (legacy table, nothing reads it).
        Trades are persisted via _store_closed_trade -> wp_trade_history.
        """
        # Intentionally no-op — kept as hook for future auditing if needed.
        pass

    def _store_closed_trade(
        self,
        pos: LivePosition,
        pnl: float,
        exit_reason: str | None = None,
        regime_at_exit: str | None = None,
        hold_duration_seconds: int | None = None,
        exit_slippage_bps: float | None = None,
    ) -> None:
        """Store a closed live trade to wp_trade_history."""
        if not self.persist_trades:
            return
        try:
            from wolfpack.db import get_db
            import re

            db = get_db()
            # Extract strategy name from recommendation_id
            strategy = None
            rec_id = pos.recommendation_id
            if rec_id and rec_id.startswith("strat-"):
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
                "source": "live",
                "opened_at": pos.opened_at.isoformat(),
                "strategy": strategy,
                # Wave 3 enrichment
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
            logger.warning(f"[live-engine] Failed to store closed trade: {e}")

    # --- Position reconciliation ---

    async def reconcile(self) -> dict:
        """Compare internal positions vs exchange. Returns drift report."""
        try:
            exchange_positions = await self._trader.get_positions()

            # Build exchange state map: {symbol: {size, entry_price}}
            exchange_map = {}
            for pos_data in exchange_positions:
                pos_info = pos_data.get("position", {})
                coin = pos_info.get("coin", "")
                size = float(pos_info.get("szi", "0"))
                if abs(size) > 1e-10:
                    exchange_map[coin] = {
                        "size": abs(size),
                        "direction": "long" if size > 0 else "short",
                        "entry_price": float(pos_info.get("entryPx", "0")),
                    }

            # Build internal state map
            internal_map = {pos.symbol: pos for pos in self.portfolio.positions}

            orphaned_internal = []  # in our list but not on exchange
            orphaned_exchange = []  # on exchange but not in our list
            mismatched = []

            for sym, pos in internal_map.items():
                if sym not in exchange_map:
                    orphaned_internal.append(sym)
                else:
                    ex = exchange_map[sym]
                    if abs(pos.size_units - ex["size"]) / max(pos.size_units, 0.001) > 0.01:
                        mismatched.append({"symbol": sym, "internal_size": pos.size_units, "exchange_size": ex["size"]})

            for sym in exchange_map:
                if sym not in internal_map:
                    orphaned_exchange.append(sym)

            has_drift = bool(orphaned_internal or orphaned_exchange or mismatched)

            # Auto-fix orphaned internal (exchange closed them)
            for sym in orphaned_internal:
                logger.warning(f"[reconcile] Removing orphaned internal position: {sym}")
                self.portfolio.positions = [p for p in self.portfolio.positions if p.symbol != sym]

            if has_drift:
                from wolfpack.notifications import send_telegram
                msg = f"\u26a0\ufe0f POSITION DRIFT DETECTED\n"
                if orphaned_internal:
                    msg += f"Removed (not on exchange): {orphaned_internal}\n"
                if orphaned_exchange:
                    msg += f"On exchange but not tracked: {orphaned_exchange}\n"
                if mismatched:
                    msg += f"Size mismatch: {mismatched}\n"
                try:
                    await send_telegram(msg)
                except Exception:
                    pass

            return {
                "has_drift": has_drift,
                "orphaned_internal": orphaned_internal,
                "orphaned_exchange": orphaned_exchange,
                "mismatched": mismatched,
            }
        except Exception as e:
            logger.error(f"[reconcile] Failed: {e}")
            return {"has_drift": False, "error": str(e)}

    # --- Emergency ---

    async def emergency_close_all(self) -> list[dict]:
        """Emergency: close all positions immediately."""
        results = []
        for pos in list(self.portfolio.positions):
            try:
                self._cancel_stop_orders(pos)
                pnl = self.close_position(pos.symbol)
                results.append({"symbol": pos.symbol, "pnl": pnl, "status": "closed"})
            except Exception as e:
                results.append({"symbol": pos.symbol, "error": str(e), "status": "failed"})
        return results
