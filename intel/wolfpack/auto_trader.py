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

STRATEGY_ALLOCATIONS = {
    "regime_momentum": 0.20,  # 20% of equity
    "vol_breakout": 0.15,     # 15%
    "ema_crossover": 0.15,    # 15%
    # remaining 50% is Brief-driven (existing logic)
}

YOLO_PROFILES = {
    1: {  # Cautious
        "label": "Cautious",
        "conviction_threshold": 85,
        "veto_floor": 60,
        "max_trades_per_day": 3,
        "penalty_multiplier": 1.5,
        "cooldown_seconds": 2700,  # 45 min
        "max_size_pct": 10,
        "rejection_cooldown_hours": 4,
        "base_pct": 5,
        "max_positions_per_symbol": 1,
    },
    2: {  # Balanced
        "label": "Balanced",
        "conviction_threshold": 75,
        "veto_floor": 55,
        "max_trades_per_day": 4,
        "penalty_multiplier": 1.0,
        "cooldown_seconds": 1800,  # 30 min
        "max_size_pct": 15,
        "rejection_cooldown_hours": 2,
        "base_pct": 10,
        "max_positions_per_symbol": 1,
    },
    3: {  # Aggressive
        "label": "Aggressive",
        "conviction_threshold": 65,
        "veto_floor": 45,
        "max_trades_per_day": 8,
        "penalty_multiplier": 0.5,
        "cooldown_seconds": 900,  # 15 min
        "max_size_pct": 20,
        "rejection_cooldown_hours": 0.5,
        "base_pct": 12,
        "max_positions_per_symbol": 2,
    },
    4: {  # YOLO
        "label": "YOLO",
        "conviction_threshold": 55,
        "veto_floor": 35,
        "max_trades_per_day": 12,
        "penalty_multiplier": 0.25,
        "cooldown_seconds": 300,  # 5 min
        "max_size_pct": 25,
        "rejection_cooldown_hours": 0.25,
        "base_pct": 15,
        "max_positions_per_symbol": 3,
    },
    5: {  # Full Send
        "label": "Full Send",
        "conviction_threshold": 45,
        "veto_floor": 25,
        "max_trades_per_day": 20,
        "penalty_multiplier": 0.0,
        "cooldown_seconds": 0,
        "max_size_pct": 25,
        "rejection_cooldown_hours": 0,
        "base_pct": 20,
        "max_positions_per_symbol": 4,
    },
}


class AutoTrader:
    """Autonomous trading bot with a separate paper trading engine."""

    def __init__(self) -> None:
        from wolfpack.paper_trading import PaperTradingEngine

        self.enabled = settings.auto_trade_enabled
        self.conviction_threshold = settings.auto_trade_conviction_threshold
        self.engine = PaperTradingEngine(starting_equity=settings.auto_trade_equity)
        self._restored = False
        self.yolo_level = 4  # Default to YOLO for paper trading
        self._apply_yolo_profile()

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
                snap_equity = snap.get("equity", settings.auto_trade_equity)
                # If snapshot equity is less than configured starting equity and
                # there are no positions/PnL, use the configured value (equity was raised)
                if snap_equity < settings.auto_trade_equity and not snap.get("positions") and snap.get("realized_pnl", 0) == 0:
                    snap_equity = settings.auto_trade_equity
                    logger.info(f"[auto-trader] Snapshot equity ${snap.get('equity')} < configured ${settings.auto_trade_equity}, using configured value")
                p.equity = snap_equity
                p.free_collateral = max(snap.get("free_collateral", settings.auto_trade_equity), snap_equity)
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
                        stop_loss=pos_data.get("stop_loss"),
                        take_profit=pos_data.get("take_profit"),
                        trailing_stop_pct=pos_data.get("trailing_stop_pct"),
                        trailing_stop_peak=pos_data.get("trailing_stop_peak"),
                    ))
                logger.info(f"[auto-trader] Restored from snapshot: equity=${p.equity}, {len(p.positions)} positions")
        except Exception as e:
            logger.warning(f"[auto-trader] Could not restore from snapshot: {e}")

    def _apply_yolo_profile(self) -> None:
        """Apply YOLO profile settings to all throttle layers."""
        profile = YOLO_PROFILES.get(self.yolo_level, YOLO_PROFILES[2])
        self.conviction_threshold = profile["conviction_threshold"]
        self._yolo_profile = profile

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
        profile = YOLO_PROFILES.get(self.yolo_level, YOLO_PROFILES[2])
        veto = BriefVeto(
            conviction_floor=profile["veto_floor"],
            penalty_multiplier=profile["penalty_multiplier"],
            rejection_cooldown_hours=profile["rejection_cooldown_hours"],
            require_stop_loss=(self.yolo_level < 4),
        )

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
                if cb_state == "EMERGENCY_STOP":
                    logger.info(f"[auto-trader] CB emergency stop, skipping {symbol}")
                    continue
                if cb_state == "SUSPENDED" and self.yolo_level < 4:
                    logger.info(f"[auto-trader] CB suspended and YOLO level {self.yolo_level} < 4, skipping {symbol}")
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
                sizer = SizingEngine(base_pct=rec.get("size_pct") or profile.get("base_pct", 10.0))
                sizing = sizer.compute(
                    conviction=veto_result.final_conviction,
                    vol_output=vol_output,
                    regime_output=None,
                    liquidity_output=None,
                )
                size_pct = sizing.final_size_pct
            except Exception:
                size_pct = min(rec.get("size_pct", 10), profile["max_size_pct"])

            if size_pct <= 0:
                continue

            # Open position
            pos = self.engine.open_position(
                symbol=symbol,
                direction=direction,
                current_price=round(entry_price, 2),
                size_pct=min(size_pct, profile["max_size_pct"]),
                recommendation_id=f"auto-{rec.get('id', 'unknown')}",
                max_positions_per_symbol=profile.get("max_positions_per_symbol", 1),
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
                "positions": [pos.model_dump(mode="json") for pos in p.positions],
            }).execute()
        except Exception as e:
            logger.error(f"[auto-trader] Failed to store snapshot: {e}")

    def process_strategy_signals(
        self,
        candles: list,
        symbol: str,
    ) -> list[dict]:
        """Run mechanical strategies and open/close positions from their signals.

        Args:
            candles: List of Candle objects (with .timestamp, .open, .high, .low, .close, .volume)
            symbol: Asset symbol (e.g., "BTC")

        Returns:
            List of executed trade dicts from strategy signals.
        """
        if not self.enabled or not candles:
            return []

        self.restore_from_snapshot()

        from wolfpack.strategies import STRATEGIES

        profile = YOLO_PROFILES.get(self.yolo_level, YOLO_PROFILES[2])
        executed: list[dict] = []
        current_idx = len(candles) - 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

        for strategy_name, strategy_cls in STRATEGIES.items():
            allocation = STRATEGY_ALLOCATIONS.get(strategy_name)
            if allocation is None:
                continue

            try:
                strategy = strategy_cls()
                if current_idx < strategy.warmup_bars:
                    continue

                signal = strategy.evaluate(candles, current_idx)
                if signal is None:
                    continue

                direction = signal.get("direction", "wait")
                if direction == "wait":
                    continue

                rec_id = f"strat-{strategy_name}-{symbol}-{timestamp}"

                # Handle close signals — close positions with matching strategy tag
                if direction == "close":
                    for pos in list(self.engine.portfolio.positions):
                        if pos.symbol == symbol and pos.recommendation_id.startswith(f"strat-{strategy_name}-"):
                            pnl = self.engine.close_position(symbol)
                            executed.append({
                                "symbol": symbol,
                                "direction": "close",
                                "strategy": strategy_name,
                                "realized_pnl": pnl,
                            })
                    continue

                # Size based on strategy allocation
                size_pct = allocation * 100  # e.g. 0.20 -> 20%
                size_pct = min(size_pct, profile["max_size_pct"])

                pos = self.engine.open_position(
                    symbol=symbol,
                    direction=direction,
                    current_price=round(signal.get("entry_price", candles[current_idx].close), 2),
                    size_pct=size_pct,
                    recommendation_id=rec_id,
                    max_positions_per_symbol=profile.get("max_positions_per_symbol", 1),
                )

                if pos:
                    # Set stop_loss/take_profit from strategy signal
                    if signal.get("stop_loss"):
                        pos.stop_loss = signal["stop_loss"]
                    if signal.get("take_profit"):
                        pos.take_profit = signal["take_profit"]

                    # Default trailing stop of 3% if no stop_loss set
                    if pos.stop_loss is None:
                        self.engine.enable_trailing_stop(symbol, 3.0)

                    trade = {
                        "symbol": symbol,
                        "direction": direction,
                        "entry_price": pos.entry_price,
                        "size_usd": pos.size_usd,
                        "size_pct": size_pct,
                        "conviction": signal.get("conviction", 75),
                        "strategy": strategy_name,
                    }
                    executed.append(trade)
                    self._store_trade(trade, rec_id)

                    logger.info(f"[auto-trader] Strategy {strategy_name} executed {direction} {symbol} @ ${pos.entry_price:,.2f}, size ${pos.size_usd:,.0f}")

            except Exception as e:
                logger.warning(f"[auto-trader] Strategy {strategy_name} error for {symbol}: {e}")

        if executed:
            self._store_snapshot()

        return executed

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
            "positions": [pos.model_dump(mode="json") for pos in p.positions],
            "yolo_level": self.yolo_level,
            "yolo_profile": YOLO_PROFILES.get(self.yolo_level, YOLO_PROFILES[2]),
            "type": "AutoBot",
        }
