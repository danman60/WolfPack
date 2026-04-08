"""AutoTrader — autonomous paper trading from high-conviction recommendations.

Operates a separate PaperTradingEngine with its own equity bucket ($5K default).
Automatically executes trades when conviction >= threshold and all safety checks pass.
Stores trades to wp_auto_trades and snapshots to wp_auto_portfolio_snapshots.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from wolfpack.config import settings
from wolfpack.risk_controls import RISK_PRESETS, YOLO_LEVEL_MAP, get_preset

logger = logging.getLogger(__name__)

# Static defaults — used as fallback when < 30 total strategy trades
STRATEGY_ALLOCATIONS = {
    # Trending strategies
    "ema_crossover": 0.15,
    "turtle_donchian": 0.10,
    "orb_session": 0.10,
    # Ranging strategies
    "mean_reversion": 0.30,
    "measured_move": 0.10,
    # Brief-driven: remaining ~25%
}

# Dynamic allocation cache (module-level, shared across AutoTrader instances)
_dynamic_allocations: dict[str, float] | None = None
_dynamic_alloc_time: datetime | None = None
_DYNAMIC_ALLOC_TTL_SECONDS = 3600  # recompute hourly


def _get_dynamic_allocations(perf_tracker) -> dict[str, float]:
    """Get dynamic strategy allocations, cached for 1 hour.

    Falls back to static STRATEGY_ALLOCATIONS if < 30 total trades.
    Logs allocation shifts > 5%.
    """
    global _dynamic_allocations, _dynamic_alloc_time

    now = datetime.now(timezone.utc)
    if (
        _dynamic_allocations is not None
        and _dynamic_alloc_time is not None
        and (now - _dynamic_alloc_time).total_seconds() < _DYNAMIC_ALLOC_TTL_SECONDS
    ):
        return _dynamic_allocations

    new_alloc = perf_tracker.get_strategy_allocations(
        default_allocations=STRATEGY_ALLOCATIONS,
        min_total_trades=30,
        min_strategy_trades=10,
    )

    # Log shifts > 5%
    old = _dynamic_allocations or STRATEGY_ALLOCATIONS
    for strat in set(list(old.keys()) + list(new_alloc.keys())):
        old_val = old.get(strat, 0)
        new_val = new_alloc.get(strat, 0)
        if abs(new_val - old_val) > 0.05:
            logger.info(
                f"[auto-trader] Allocation shift: {strat} "
                f"{old_val:.1%} -> {new_val:.1%} "
                f"(delta {new_val - old_val:+.1%})"
            )

    _dynamic_allocations = new_alloc
    _dynamic_alloc_time = now
    return _dynamic_allocations


# Which candle timeframe each strategy expects
STRATEGY_TIMEFRAMES = {
    "ema_crossover": "1h",
    "turtle_donchian": "1h",
    "mean_reversion": "1h",
    "orb_session": "5m",
    "measured_move": "5m",
}

# conviction_threshold is NOT part of risk_controls (it's auto_trader-specific)
# because it gates whether the autotrader even considers a rec, before veto runs.
_CONVICTION_THRESHOLDS = {1: 85, 2: 75, 3: 65, 4: 55, 5: 45}
_LABELS = {1: "Cautious", 2: "Balanced", 3: "Aggressive", 4: "YOLO", 5: "Full Send"}

def _build_yolo_profiles() -> dict:
    """Build YOLO_PROFILES dict from RISK_PRESETS for backward compatibility."""
    profiles = {}
    for level, name in YOLO_LEVEL_MAP.items():
        policy = RISK_PRESETS[name]
        profiles[level] = {
            "label": _LABELS[level],
            "conviction_threshold": _CONVICTION_THRESHOLDS[level],
            "veto_floor": policy.soft.conviction_floor,
            "max_trades_per_day": policy.soft.max_trades_per_day,
            "penalty_multiplier": policy.soft.penalty_multiplier,
            "cooldown_seconds": int(policy.soft.cooldown_seconds),
            "max_size_pct": int(policy.hard.max_position_size_pct),
            "rejection_cooldown_hours": policy.soft.rejection_cooldown_hours,
            "base_pct": int(policy.soft.base_pct),
            "max_positions_per_symbol": policy.soft.max_positions_per_symbol,
        }
    return profiles

YOLO_PROFILES = _build_yolo_profiles()


class AutoTrader:
    """Autonomous trading bot with a separate paper trading engine."""

    def __init__(self) -> None:
        from wolfpack.paper_trading import PaperTradingEngine
        from wolfpack.performance_tracker import PerformanceTracker

        self.enabled = settings.auto_trade_enabled
        self.conviction_threshold = settings.auto_trade_conviction_threshold

        # Select engine based on strategy mode
        import wolfpack.api as api_mod
        mode = getattr(api_mod, "_strategy_mode", "paper")
        if mode == "live":
            from wolfpack.live_trading import LiveTradingEngine
            self.engine = LiveTradingEngine()
            logger.info("[auto-trader] LIVE MODE — using real Hyperliquid execution")
        else:
            self.engine = PaperTradingEngine(starting_equity=settings.auto_trade_equity)

        self._restored = False
        self._last_trade_at: datetime | None = None
        self.yolo_level = 4  # Default to YOLO for paper trading
        self._last_strategy_signals: list[dict] = []
        self._current_regime: str = "unknown"
        self._perf_tracker = PerformanceTracker(rolling_window=50)
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

    def set_regime(self, macro_regime: str) -> None:
        """Store current macro regime for filtering decisions."""
        self._current_regime = macro_regime

    def _is_pumping(self, symbol: str, latest_prices: dict[str, float]) -> bool:
        """Check if price moved up >2% recently by comparing to 1h-ago snapshot.

        Uses the last stored price from wp_auto_portfolio_snapshots as baseline.
        Conservative: only blocks shorts, never blocks longs.
        """
        try:
            current = latest_prices.get(symbol)
            if not current:
                return False
            from wolfpack.db import get_db
            db = get_db()
            # Get price from ~1 hour ago via candle data or snapshot
            result = (
                db.table("wp_auto_portfolio_snapshots")
                .select("positions")
                .order("created_at", desc=True)
                .limit(12)  # ~1 hour of 5-min snapshots
                .execute()
            )
            if not result.data:
                return False
            # Find the oldest snapshot's price for this symbol
            for snap in reversed(result.data):
                for pos in (snap.get("positions") or []):
                    if pos.get("symbol") == symbol and pos.get("entry_price"):
                        old_price = pos["entry_price"]
                        move_pct = (current - old_price) / old_price * 100
                        if move_pct > 2.0:
                            return True
                        return False
            return False
        except Exception:
            return False

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

        # Check regime transition cooldown
        if recs:
            symbol = recs[0].get("symbol", "UNKNOWN")
            from wolfpack.modules.regime_transition import get_transition_manager
            tm = get_transition_manager()
            if tm.is_in_cooldown(symbol):
                logger.info(f"[auto-trader] {symbol} in regime transition cooldown, blocking new entries")
                return []

        for rec in recs:
            symbol = rec.get("symbol", "UNKNOWN")
            direction = rec.get("direction", "wait")
            conviction = rec.get("conviction", 0)

            # Skip if direction is wait
            if direction == "wait":
                continue

            # Dynamic threshold based on performance
            dynamic_threshold = self._perf_tracker.get_threshold(symbol, direction, self.conviction_threshold)
            if conviction < dynamic_threshold:
                logger.info(f"[auto-trader] {symbol} {direction} conviction {conviction} < dynamic threshold {dynamic_threshold}, skipping")
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

            # Penalize (don't block) mean_reversion longs in RANGING regime
            strategy = rec.get("strategy", "")
            if self._current_regime == "RANGING" and direction == "long" and strategy == "mean_reversion":
                conviction = max(conviction - 10, 0)
                logger.info(f"[auto-trader] {symbol} long penalized -10 conviction in RANGING (now {conviction})")

            # Trading hours restriction — only open new positions during allowed UTC hours
            current_utc_hour = datetime.now(timezone.utc).hour
            if not (settings.trading_hours_start <= current_utc_hour < settings.trading_hours_end):
                logger.info(f"[auto-trader] {symbol} {direction} blocked: UTC hour {current_utc_hour} outside {settings.trading_hours_start}-{settings.trading_hours_end}")
                continue

            # Pump guard — cap short exposure to prevent cascade losses on sudden pumps
            if direction == "short":
                open_shorts = sum(1 for p in self.engine.portfolio.positions if p.direction == "short")
                if open_shorts >= 3:
                    logger.info(f"[auto-trader] {symbol} short blocked: {open_shorts} shorts open (max 3)")
                    continue
                # Don't open new shorts if any watched symbol pumped >2% in last hour
                if latest_prices and self._is_pumping(symbol, latest_prices):
                    logger.info(f"[auto-trader] {symbol} short blocked: pump detected (>2% move in last hour)")
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

            # Check if mechanical strategies have a matching signal
            has_mechanical = any(
                s.get("symbol") == symbol and s.get("direction") == direction
                for s in getattr(self, "_last_strategy_signals", [])
            )

            # Apply conviction multiplier based on mechanical confirmation
            if has_mechanical:
                size_multiplier = 1.0  # Full size -- Brief + mechanical agree
                logger.info(f"[auto-trader] Brief+mechanical aligned for {symbol} {direction}")
            else:
                size_multiplier = 0.25  # Quarter size -- Brief only

            size_pct = min(size_pct * size_multiplier, profile["max_size_pct"])

            # Apply performance-based size multiplier
            perf_mult = self._perf_tracker.get_size_multiplier(symbol, direction)
            size_pct = size_pct * perf_mult

            if size_pct <= 0:
                continue

            # Trade spacing cooldown (5 minutes between trades)
            if self._last_trade_at:
                elapsed = (datetime.now(timezone.utc) - self._last_trade_at).total_seconds()
                if elapsed < 300:
                    logger.info(f"[auto-trader] Trade spacing: {300 - elapsed:.0f}s remaining")
                    continue

            # Enforce $3K-$5K position size sweet spot
            estimated_usd = self.engine.portfolio.equity * (size_pct / 100)
            if estimated_usd < settings.min_position_usd:
                logger.info(f"[auto-trader] {symbol} {direction} skipped: ${estimated_usd:.0f} < ${settings.min_position_usd:.0f} minimum")
                continue
            if estimated_usd > settings.max_position_usd:
                size_pct = (settings.max_position_usd / self.engine.portfolio.equity) * 100
                logger.info(f"[auto-trader] {symbol} {direction} capped at ${settings.max_position_usd:.0f}")

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
                self._last_trade_at = datetime.now(timezone.utc)
                if rec.get("stop_loss"):
                    pos.stop_loss = rec["stop_loss"]
                if rec.get("take_profit"):
                    pos.take_profit = rec["take_profit"]

                # Place exchange stop orders (live mode only)
                if hasattr(self.engine, 'place_exchange_stops'):
                    self.engine.place_exchange_stops(symbol)

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
                    "strategy": rec.get("strategy", "brief"),
                }
                executed.append(trade)

                # Store to wp_auto_trades
                self._store_trade(trade, rec.get("id"))

                # Send notification via digest
                try:
                    from wolfpack.notification_digest import get_digest
                    digest = get_digest()
                    arrow = "\u2b06\ufe0f" if direction == "long" else "\u2b07\ufe0f"
                    digest.add({
                        "type": "trade_open",
                        "symbol": symbol,
                        "direction": direction,
                        "size": pos.size_usd,
                        "entry_price": entry_price,
                        "conviction": veto_result.final_conviction,
                        "details": f"{arrow} {direction.upper()} {symbol} @ ${entry_price:,.2f} (${pos.size_usd:,.0f})",
                    })
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
                    from wolfpack.notification_digest import get_digest
                    digest = get_digest()
                    pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                    digest.add({
                        "type": "trade_close",
                        "symbol": pa_symbol,
                        "direction": pos.direction,
                        "pnl": pnl,
                        "details": f"CLOSED {pos.direction.upper()} {pa_symbol}: {pnl_str}",
                    })
                except Exception:
                    pass

            elif action == "adjust_stop":
                new_stop = pa.get("suggested_stop")
                if new_stop:
                    pos.stop_loss = new_stop
                    # Place exchange stop orders (live mode only)
                    if hasattr(self.engine, 'place_exchange_stops'):
                        self.engine.place_exchange_stops(pa_symbol)
                    executed.append({"action": "adjust_stop", "symbol": pa_symbol, "new_stop": new_stop})

                    try:
                        from wolfpack.notification_digest import get_digest
                        digest = get_digest()
                        digest.add({
                            "type": "stop_adjusted",
                            "symbol": pa_symbol,
                            "details": f"Stop adjusted to ${new_stop:,.2f} — {pa.get('reason', 'Brief recommended adjustment')}",
                        })
                    except Exception:
                        pass

            elif action == "adjust_tp":
                new_tp = pa.get("suggested_tp")
                if new_tp:
                    pos.take_profit = new_tp
                    # Place exchange stop orders (live mode only)
                    if hasattr(self.engine, 'place_exchange_stops'):
                        self.engine.place_exchange_stops(pa_symbol)
                    executed.append({"action": "adjust_tp", "symbol": pa_symbol, "new_tp": new_tp})

                    try:
                        from wolfpack.notification_digest import get_digest
                        digest = get_digest()
                        digest.add({
                            "type": "stop_adjusted",
                            "symbol": pa_symbol,
                            "details": f"TP adjusted to ${new_tp:,.2f} — {pa.get('reason', 'Brief recommended adjustment')}",
                        })
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
            row = {
                "recommendation_id": rec_id,
                "symbol": trade["symbol"],
                "direction": trade["direction"],
                "entry_price": trade["entry_price"],
                "size_usd": trade["size_usd"],
                "size_pct": trade["size_pct"],
                "conviction": trade["conviction"],
                "status": "open",
            }
            # Include strategy if present
            if trade.get("strategy"):
                row["strategy"] = trade["strategy"]
            db.table("wp_auto_trades").insert(row).execute()
        except Exception as e:
            logger.error(f"[auto-trader] Failed to store trade: {e}")

    def _store_snapshot(self) -> None:
        """Store auto-trader portfolio snapshot to Supabase.

        Resilient to missing DB columns — retries without problematic fields.
        """
        try:
            from wolfpack.db import get_db
            db = get_db()
            p = self.engine.portfolio
            snapshot = {
                "equity": round(p.equity, 2),
                "free_collateral": round(p.free_collateral, 2),
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "realized_pnl": round(p.realized_pnl, 2),
                "positions": [pos.model_dump(mode="json") for pos in p.positions],
            }
            try:
                db.table("wp_auto_portfolio_snapshots").insert(snapshot).execute()
            except Exception as e:
                error_msg = str(e).lower()
                if "column" in error_msg and "schema" in error_msg:
                    # Missing column — retry without newer fields
                    for key in ["friction_costs"]:
                        snapshot.pop(key, None)
                    db.table("wp_auto_portfolio_snapshots").insert(snapshot).execute()
                else:
                    raise
        except Exception as e:
            logger.warning(f"[auto-trader] Failed to store snapshot: {e}")

    def process_strategy_signals(
        self,
        candles: list,
        symbol: str,
        regime_output=None,
        vol_output=None,
        timeframe: str = "1h",
    ) -> list[dict]:
        """Run mechanical strategies and open/close positions from their signals.

        Args:
            candles: List of Candle objects (with .timestamp, .open, .high, .low, .close, .volume)
            symbol: Asset symbol (e.g., "BTC")
            regime_output: Regime detector output for routing (None = run all strategies)
            vol_output: Volatility module output for routing

        Returns:
            List of executed trade dicts from strategy signals.
        """
        if not self.enabled or not candles:
            return []

        self.restore_from_snapshot()

        from wolfpack.strategies import STRATEGIES
        from wolfpack.strategies.regime_router import route_strategies

        routing = route_strategies(regime_output, vol_output, symbol=symbol)
        allowed = routing.get("allowed")
        debounce = routing.get("debounce", "")
        logger.info(f"[auto-trader] Regime routing: {routing['macro_regime']} -- {routing['reason']} [{debounce}]")

        # VOLATILE: tighten trailing stops, no new entries
        if routing["macro_regime"] == "VOLATILE":
            for pos in self.engine.portfolio.positions:
                if pos.trailing_stop_pct and pos.trailing_stop_pct > 1.5:
                    pos.trailing_stop_pct = max(1.5, pos.trailing_stop_pct * 0.5)
            self._store_snapshot()
            return []

        # Check regime transition cooldown
        from wolfpack.modules.regime_transition import get_transition_manager
        tm = get_transition_manager()
        if tm.is_in_cooldown(symbol):
            logger.info(f"[auto-trader] {symbol} in regime transition cooldown, blocking new entries")
            return []

        profile = YOLO_PROFILES.get(self.yolo_level, YOLO_PROFILES[2])
        executed: list[dict] = []
        current_idx = len(candles) - 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

        # Use dynamic allocations (falls back to static if insufficient data)
        active_allocations = _get_dynamic_allocations(self._perf_tracker)

        for strategy_name, strategy_cls in STRATEGIES.items():
            allocation = active_allocations.get(strategy_name)
            if allocation is None:
                continue

            # Regime-based strategy filter
            if allowed is not None and strategy_name not in allowed:
                continue

            # Check timeframe compatibility
            expected_tf = STRATEGY_TIMEFRAMES.get(strategy_name, "1h")
            if expected_tf != timeframe:
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

                # Block mean_reversion longs in RANGING regime
                if routing["macro_regime"] == "RANGING" and direction == "long" and strategy_name == "mean_reversion":
                    logger.info(f"[auto-trader] {symbol} long blocked: mean_reversion longs disabled in RANGING regime")
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

                # Trading hours restriction — only open new positions during allowed UTC hours
                current_utc_hour = datetime.now(timezone.utc).hour
                if not (settings.trading_hours_start <= current_utc_hour < settings.trading_hours_end):
                    logger.info(f"[auto-trader] Strategy {strategy_name} {symbol} {direction} blocked: UTC hour {current_utc_hour} outside trading hours")
                    continue

                # Trade spacing cooldown (5 minutes between trades)
                if self._last_trade_at:
                    elapsed = (datetime.now(timezone.utc) - self._last_trade_at).total_seconds()
                    if elapsed < 300:
                        logger.info(f"[auto-trader] Trade spacing: {300 - elapsed:.0f}s remaining, skipping {strategy_name}")
                        continue

                # Size based on strategy allocation
                size_pct = allocation * 100  # e.g. 0.20 -> 20%
                size_pct = min(size_pct, profile["max_size_pct"])

                # Enforce $3K-$5K position size sweet spot
                estimated_usd = self.engine.portfolio.equity * (size_pct / 100)
                if estimated_usd < settings.min_position_usd:
                    logger.info(f"[auto-trader] Strategy {strategy_name} {symbol} {direction} skipped: ${estimated_usd:.0f} < ${settings.min_position_usd:.0f} minimum")
                    continue
                if estimated_usd > settings.max_position_usd:
                    size_pct = (settings.max_position_usd / self.engine.portfolio.equity) * 100
                    logger.info(f"[auto-trader] Strategy {strategy_name} {symbol} {direction} capped at ${settings.max_position_usd:.0f}")

                pos = self.engine.open_position(
                    symbol=symbol,
                    direction=direction,
                    current_price=round(signal.get("entry_price", candles[current_idx].close), 2),
                    size_pct=size_pct,
                    recommendation_id=rec_id,
                    max_positions_per_symbol=profile.get("max_positions_per_symbol", 1),
                )

                if pos:
                    self._last_trade_at = datetime.now(timezone.utc)

                    # Set stop_loss/take_profit from strategy signal
                    if signal.get("stop_loss"):
                        pos.stop_loss = signal["stop_loss"]
                    if signal.get("take_profit"):
                        pos.take_profit = signal["take_profit"]

                    # Place exchange stop orders (live mode only)
                    if hasattr(self.engine, 'place_exchange_stops'):
                        self.engine.place_exchange_stops(symbol)

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

        self._last_strategy_signals = executed
        return executed

    def update_htf_trailing(self, candles_4h: list, symbol: str) -> None:
        """Trail stops on 4h bar structure for all positions in symbol."""
        if not candles_4h or len(candles_4h) < 2:
            return

        self.restore_from_snapshot()

        current_bar = candles_4h[-1]
        prev_bar = candles_4h[-2]
        changed = False

        for pos in self.engine.portfolio.positions:
            if pos.symbol != symbol or pos.stop_loss is None:
                continue

            if pos.direction == "long":
                if current_bar.high > prev_bar.high:
                    buffer = current_bar.close * 0.005
                    new_stop = current_bar.low - buffer
                    if new_stop > pos.stop_loss:
                        pos.stop_loss = round(new_stop, 2)
                        changed = True
                        logger.info(f"[auto-trader] HTF trailing: {symbol} long stop -> ${new_stop:,.2f}")

            elif pos.direction == "short":
                if current_bar.low < prev_bar.low:
                    buffer = current_bar.close * 0.005
                    new_stop = current_bar.high + buffer
                    if new_stop < pos.stop_loss:
                        pos.stop_loss = round(new_stop, 2)
                        changed = True
                        logger.info(f"[auto-trader] HTF trailing: {symbol} short stop -> ${new_stop:,.2f}")

        if changed:
            self._store_snapshot()

    def get_status(self) -> dict:
        """Return auto-trader status."""
        self.restore_from_snapshot()
        import wolfpack.api as api_mod
        mode = getattr(api_mod, "_strategy_mode", "paper")
        p = self.engine.portfolio
        return {
            "enabled": self.enabled,
            "mode": mode,
            "conviction_threshold": self.conviction_threshold,
            "equity": round(p.equity, 2),
            "starting_equity": p.starting_equity,
            "realized_pnl": round(p.realized_pnl, 2),
            "unrealized_pnl": round(p.unrealized_pnl, 2),
            "total_fees": round(p.total_fees, 2),
            "friction_costs": round(getattr(p, "friction_costs", 0), 2),
            "open_positions": len(p.positions),
            "positions": [pos.model_dump(mode="json") for pos in p.positions],
            "yolo_level": self.yolo_level,
            "yolo_profile": YOLO_PROFILES.get(self.yolo_level, YOLO_PROFILES[2]),
            "type": "AutoBot",
        }
