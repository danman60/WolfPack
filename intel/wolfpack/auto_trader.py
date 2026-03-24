"""AutoTrader — autonomous paper trading from high-conviction recommendations.

Operates a separate PaperTradingEngine with its own equity bucket ($5K default).
Automatically executes trades when conviction >= threshold and all safety checks pass.
Stores trades to wp_auto_trades and snapshots to wp_auto_portfolio_snapshots.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from wolfpack.config import settings

logger = logging.getLogger(__name__)


class AutoTrader:
    """Autonomous trading bot with a separate paper trading engine."""

    def __init__(self) -> None:
        from wolfpack.paper_trading import PaperTradingEngine

        self.enabled = settings.auto_trade_enabled
        self.conviction_threshold = settings.auto_trade_conviction_threshold
        self.engine = PaperTradingEngine(starting_equity=settings.auto_trade_equity)
        self._restored = False

    def restore_from_snapshot(self) -> None:
        """Restore auto-trader portfolio from latest Supabase snapshot."""
        if self._restored:
            return
        self._restored = True

        try:
            from wolfpack.db import get_db
            from wolfpack.paper_trading import PaperPosition

            db = get_db()
            result = (
                db.table("wp_auto_portfolio_snapshots")
                .select("*")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                snap = result.data[0]
                p = self.engine.portfolio
                p.equity = snap.get("equity", settings.auto_trade_equity)
                p.free_collateral = snap.get("free_collateral", settings.auto_trade_equity)
                p.realized_pnl = snap.get("realized_pnl", 0.0)
                p.unrealized_pnl = snap.get("unrealized_pnl", 0.0)
                for pos_data in snap.get("positions", []):
                    p.positions.append(PaperPosition(
                        symbol=pos_data["symbol"],
                        direction=pos_data["direction"],
                        entry_price=pos_data["entry_price"],
                        current_price=pos_data.get("current_price", pos_data["entry_price"]),
                        size_usd=pos_data["size_usd"],
                        unrealized_pnl=pos_data.get("unrealized_pnl", 0.0),
                        recommendation_id=pos_data.get("recommendation_id", "auto-restored"),
                        opened_at=pos_data.get("opened_at", "2026-01-01T00:00:00+00:00"),
                    ))
                logger.info(f"[auto-trader] Restored from snapshot: equity=${p.equity}, {len(p.positions)} positions")
        except Exception as e:
            logger.warning(f"[auto-trader] Could not restore from snapshot: {e}")

    async def process_recommendations(
        self,
        recs: list[dict],
        cb_output: Any = None,
        vol_output: Any = None,
        latest_prices: dict[str, float] | None = None,
    ) -> list[dict]:
        """Process recommendations from the intelligence cycle.

        Returns list of auto-executed trade dicts.
        """
        if not self.enabled:
            return []

        self.restore_from_snapshot()

        from wolfpack.veto import BriefVeto
        veto = BriefVeto()

        executed: list[dict] = []

        for rec in recs:
            symbol = rec.get("symbol", "UNKNOWN")
            direction = rec.get("direction", "wait")
            conviction = rec.get("conviction", 0)

            # Skip if direction is wait
            if direction == "wait":
                continue

            # Skip if below conviction threshold
            if conviction < self.conviction_threshold:
                continue

            # Veto check
            cb_dict = cb_output.model_dump() if hasattr(cb_output, "model_dump") else cb_output
            vol_dict = vol_output.model_dump() if hasattr(vol_output, "model_dump") else vol_output
            veto_result = veto.evaluate(rec, cb_output=cb_dict, vol_output=vol_dict)
            if veto_result.action == "reject":
                logger.info(f"[auto-trader] Veto rejected {symbol}: {veto_result.reasons}")
                continue

            # Check circuit breaker
            if cb_output:
                cb_state = cb_dict.get("state", "") if isinstance(cb_dict, dict) else ""
                if cb_state != "ACTIVE":
                    logger.info(f"[auto-trader] CB not active ({cb_state}), skipping {symbol}")
                    continue

            # Get entry price
            entry_price = rec.get("entry_price")
            if not entry_price and latest_prices:
                entry_price = latest_prices.get(symbol)
            if not entry_price:
                logger.warning(f"[auto-trader] No entry price for {symbol}, skipping")
                continue

            # Size using SizingEngine
            try:
                from wolfpack.modules.sizing import SizingEngine
                sizer = SizingEngine(base_pct=rec.get("size_pct") or 10.0)
                sizing = sizer.compute(
                    conviction=veto_result.final_conviction,
                    vol_output=vol_output,
                    regime_output=None,
                    liquidity_output=None,
                )
                size_pct = sizing.final_size_pct
            except Exception:
                size_pct = min(rec.get("size_pct", 10), 15)  # Conservative default

            if size_pct <= 0:
                continue

            # Open position
            pos = self.engine.open_position(
                symbol=symbol,
                direction=direction,
                current_price=round(entry_price, 2),
                size_pct=min(size_pct, 15),  # Auto-trader capped at 15%
                recommendation_id=f"auto-{rec.get('id', 'unknown')}",
            )

            if pos:
                if rec.get("stop_loss"):
                    pos.stop_loss = rec["stop_loss"]
                if rec.get("take_profit"):
                    pos.take_profit = rec["take_profit"]

                # Enable trailing stop if recommended by Brief
                trailing_pct = rec.get("trailing_stop_pct")
                if trailing_pct and trailing_pct > 0:
                    self.engine.enable_trailing_stop(symbol, trailing_pct)

                trade = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "size_usd": pos.size_usd,
                    "size_pct": size_pct,
                    "conviction": veto_result.final_conviction,
                }
                executed.append(trade)

                # Store to wp_auto_trades
                self._store_trade(trade, rec.get("id"))

                # Send Telegram notification
                try:
                    from wolfpack.notifications import send_telegram
                    arrow = "\u2b06\ufe0f" if direction == "long" else "\u2b07\ufe0f"
                    await send_telegram(
                        f"<b>{arrow} Auto-Bot {direction.upper()} {symbol}</b>\n"
                        f"Entry: <code>${entry_price:,.2f}</code>\n"
                        f"Size: <code>${pos.size_usd:,.0f}</code>\n"
                        f"Conviction: {veto_result.final_conviction}%"
                    )
                except Exception:
                    pass

                logger.info(f"[auto-trader] Executed {direction} {symbol} @ ${entry_price:,.2f}, size ${pos.size_usd:,.0f}")

        # Store snapshot after processing
        if executed:
            self._store_snapshot()

        return executed

    async def process_position_actions(
        self,
        actions: list[dict],
        latest_prices: dict[str, float] | None = None,
    ) -> list[dict]:
        """Auto-execute mechanical position actions (close, adjust_stop, adjust_tp).

        Skips reduce (too complex — requires close+reopen logic).
        Returns list of auto-executed action dicts.
        """
        if not self.enabled:
            return []

        self.restore_from_snapshot()

        from wolfpack.db import get_db
        db = get_db()

        executed: list[dict] = []

        for pa in actions:
            action = pa.get("action", "hold")
            pa_symbol = pa.get("symbol", "UNKNOWN")
            action_id = pa.get("id")

            # Only auto-execute mechanical actions
            if action not in ("close", "adjust_stop", "adjust_tp"):
                continue

            pos = next((p for p in self.engine.portfolio.positions if p.symbol == pa_symbol), None)
            if not pos:
                continue

            if action == "close":
                current_price = (latest_prices or {}).get(pa_symbol, pos.current_price)
                self.engine.update_prices({pa_symbol: current_price})
                pnl = self.engine.close_position(pa_symbol)
                executed.append({"action": "close", "symbol": pa_symbol, "realized_pnl": pnl})

                try:
                    from wolfpack.notifications import send_telegram
                    pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                    await send_telegram(
                        f"<b>\U0001f916 Auto-bot CLOSED {pos.direction.upper()} {pa_symbol}</b>\n"
                        f"P&L: <code>{pnl_str}</code>\n"
                        f"Reason: {pa.get('reason', 'Brief recommended close')}"
                    )
                except Exception:
                    pass

            elif action == "adjust_stop":
                new_stop = pa.get("suggested_stop")
                if new_stop:
                    pos.stop_loss = new_stop
                    executed.append({"action": "adjust_stop", "symbol": pa_symbol, "new_stop": new_stop})

                    try:
                        from wolfpack.notifications import send_telegram
                        await send_telegram(
                            f"<b>\U0001f916 Auto-bot adjusted stop for {pa_symbol}</b>\n"
                            f"New stop: <code>${new_stop:,.2f}</code>\n"
                            f"Reason: {pa.get('reason', 'Brief recommended adjustment')}"
                        )
                    except Exception:
                        pass

            elif action == "adjust_tp":
                new_tp = pa.get("suggested_tp")
                if new_tp:
                    pos.take_profit = new_tp
                    executed.append({"action": "adjust_tp", "symbol": pa_symbol, "new_tp": new_tp})

                    try:
                        from wolfpack.notifications import send_telegram
                        await send_telegram(
                            f"<b>\U0001f916 Auto-bot adjusted TP for {pa_symbol}</b>\n"
                            f"New TP: <code>${new_tp:,.2f}</code>\n"
                            f"Reason: {pa.get('reason', 'Brief recommended adjustment')}"
                        )
                    except Exception:
                        pass

            # Update DB status to auto_executed
            if action_id:
                try:
                    db.table("wp_position_actions").update({
                        "status": "auto_executed",
                        "acted_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", action_id).execute()
                except Exception as e:
                    logger.warning(f"[auto-trader] Failed to update action status: {e}")

        if executed:
            self._store_snapshot()

        return executed

    def _store_trade(self, trade: dict, rec_id: str | None = None) -> None:
        """Store an auto-trade to Supabase."""
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_auto_trades").insert({
                "recommendation_id": rec_id,
                "symbol": trade["symbol"],
                "direction": trade["direction"],
                "entry_price": trade["entry_price"],
                "size_usd": trade["size_usd"],
                "size_pct": trade["size_pct"],
                "conviction": trade["conviction"],
                "status": "open",
            }).execute()
        except Exception as e:
            logger.error(f"[auto-trader] Failed to store trade: {e}")

    def _store_snapshot(self) -> None:
        """Store auto-trader portfolio snapshot to Supabase."""
        try:
            from wolfpack.db import get_db
            db = get_db()
            p = self.engine.portfolio
            db.table("wp_auto_portfolio_snapshots").insert({
                "equity": round(p.equity, 2),
                "free_collateral": round(p.free_collateral, 2),
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "realized_pnl": round(p.realized_pnl, 2),
                "positions": [pos.model_dump() for pos in p.positions],
            }).execute()
        except Exception as e:
            logger.error(f"[auto-trader] Failed to store snapshot: {e}")

    def get_status(self) -> dict:
        """Return auto-trader status."""
        self.restore_from_snapshot()
        p = self.engine.portfolio
        return {
            "enabled": self.enabled,
            "conviction_threshold": self.conviction_threshold,
            "equity": round(p.equity, 2),
            "starting_equity": p.starting_equity,
            "realized_pnl": round(p.realized_pnl, 2),
            "unrealized_pnl": round(p.unrealized_pnl, 2),
            "open_positions": len(p.positions),
            "positions": [pos.model_dump() for pos in p.positions],
        }
