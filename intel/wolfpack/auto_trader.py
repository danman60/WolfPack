"""AutoTrader — autonomous paper trading from high-conviction recommendations.

Operates a separate PaperTradingEngine with its own equity bucket ($5K default).
Automatically executes trades when conviction >= threshold and all safety checks pass.
Stores trades to wp_auto_trades and snapshots to wp_auto_portfolio_snapshots.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from wolfpack.config import settings
from wolfpack.risk_controls import RISK_PRESETS, YOLO_LEVEL_MAP, get_preset

logger = logging.getLogger(__name__)

# Static defaults — used as fallback when < 30 total strategy trades
STRATEGY_ALLOCATIONS = {
    # Trending strategies
    "ema_crossover": 0.10,
    "turtle_donchian": 0.10,
    "trend_pullback": 0.15,   # mid-trend continuation, highest freq in TRENDING
    "orb_session": 0.05,
    # Ranging strategies
    "mean_reversion": 0.15,
    "band_fade": 0.15,
    "measured_move": 0.05,
    # Ranging-regime exploration probes (2026-04-13)
    "slow_drift_follow": 0.05,
    "range_breakout": 0.05,
    # Brief-driven: remaining ~15%
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
    "band_fade": "1h",
    "trend_pullback": "1h",
    "slow_drift_follow": "1h",
    "range_breakout": "1h",
    "orb_session": "5m",
    "measured_move": "5m",
}

# conviction_threshold is NOT part of risk_controls (it's auto_trader-specific)
# because it gates whether the autotrader even considers a rec, before veto runs.
_CONVICTION_THRESHOLDS = {1: 85, 2: 75, 3: 65, 4: 55, 5: 45}
_LABELS = {1: "Cautious", 2: "Balanced", 3: "Aggressive", 4: "YOLO", 5: "Full Send"}

# Per-level sizing overrides — controls the entire sizing chain aggressiveness
# brief_only_mult: multiplier when only Brief recommends (no mechanical strategy alignment)
# min_perf_mult: floor for PerformanceTracker size multiplier (prevents TOXIC from zeroing out)
# min_position_usd: minimum position size to open (below this, trade is skipped)
# trade_spacing_s: minimum seconds between consecutive trades
_YOLO_SIZING = {
    1: {"brief_only_mult": 0.10, "min_perf_mult": 0.15, "min_position_usd": 500, "trade_spacing_s": 600},
    2: {"brief_only_mult": 0.25, "min_perf_mult": 0.15, "min_position_usd": 200, "trade_spacing_s": 300},
    3: {"brief_only_mult": 0.40, "min_perf_mult": 0.30, "min_position_usd": 150, "trade_spacing_s": 180},
    4: {"brief_only_mult": 0.60, "min_perf_mult": 0.50, "min_position_usd": 100, "trade_spacing_s": 120},
    5: {"brief_only_mult": 1.00, "min_perf_mult": 0.85, "min_position_usd": 50,  "trade_spacing_s": 30},
}

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


from wolfpack.price_utils import round_price


def _compute_default_stop_loss(symbol: str, direction: str, entry_price: float) -> float:
    """Compute a mechanical stop_loss price based on per-symbol bps distance.

    Called when Brief (or a strategy signal) doesn't include an explicit
    stop_loss. Each position gets defined risk so one bad move can't blow
    up the portfolio. Longer-tail alts get a wider SL than majors.

    bps distances are configured in config.py:
      default_stop_loss_bps_btc (default 200 = 2.0%)
      default_stop_loss_bps_eth (default 250 = 2.5%)
      default_stop_loss_bps_alt (default 350 = 3.5%)
    """
    sym = (symbol or "").upper()
    if sym == "BTC":
        bps = settings.default_stop_loss_bps_btc
    elif sym == "ETH":
        bps = settings.default_stop_loss_bps_eth
    else:
        bps = settings.default_stop_loss_bps_alt
    frac = bps / 10000.0
    if direction == "long":
        return round_price(entry_price * (1 - frac))
    else:  # short
        return round_price(entry_price * (1 + frac))


class AutoTrader:
    """Autonomous trading bot with a separate paper trading engine."""

    def __init__(self, wallet_id: str | None = None, engine_mode: str = "paper", wallet_config: dict | None = None) -> None:
        from wolfpack.paper_trading import PaperTradingEngine
        from wolfpack.performance_tracker import PerformanceTracker

        self.enabled = settings.auto_trade_enabled
        # conviction_threshold is set exclusively by _apply_yolo_profile() — NOT from settings
        self.conviction_threshold = 75  # placeholder; overwritten by _apply_yolo_profile()
        self.wallet_id = wallet_id
        self._wallet_config = wallet_config or {}

        # Select engine based on explicit mode param (wave 3: no more _strategy_mode import)
        if engine_mode == "live":
            from wolfpack.live_trading import LiveTradingEngine
            self.engine = LiveTradingEngine(wallet_id=wallet_id)
            logger.info("[auto-trader] LIVE MODE — using real Hyperliquid execution")
        else:
            self.engine = PaperTradingEngine(
                starting_equity=settings.auto_trade_equity,
                wallet_id=wallet_id,
            )

        self._restored = False
        self._last_trade_at: datetime | None = None
        self.yolo_level = self._load_yolo_level()  # Restore from DB or default to 4
        self._last_strategy_signals: list[dict] = []
        self._current_regime: str = "unknown"
        self._latest_vwaps: dict[str, float] = {}  # symbol -> VWAP
        self._perf_tracker = PerformanceTracker(rolling_window=50)
        # Phase 3: human heuristics (v3 wallets only, gated by config.heuristics_enabled)
        self._heuristic_state: Any = None  # HeuristicState | None — lazy import
        self._heuristics_enabled: bool = False
        self._heuristics_last_close_check: datetime | None = None
        self._apply_yolo_profile()
        self._apply_wallet_config()  # Per-wallet overrides on top

    def restore_from_snapshot(self) -> None:
        """Restore auto-trader portfolio from latest Supabase snapshot."""
        if self._restored:
            return
        self._restored = True

        try:
            from wolfpack.db import get_db
            from wolfpack.paper_trading import PaperPosition

            db = get_db()
            # Wave 3: prefer wp_portfolio_snapshots filtered by wallet_id
            result = None
            if self.wallet_id:
                try:
                    result = (
                        db.table("wp_portfolio_snapshots")
                        .select("*")
                        .eq("wallet_id", self.wallet_id)
                        .order("created_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                except Exception as e:
                    logger.warning(f"[auto-trader] wp_portfolio_snapshots read failed, falling back: {e}")
                    result = None

            # Fallback: legacy wp_auto_portfolio_snapshots (transition period)
            if not result or not result.data:
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
                    restored_sl = pos_data.get("stop_loss")
                    if restored_sl is None:
                        # Backfill a mechanical SL on restored positions that
                        # don't have one (e.g., old positions opened before
                        # auto-SL landed). Same per-symbol bps distances as
                        # new opens.
                        restored_sl = _compute_default_stop_loss(
                            symbol=pos_data["symbol"],
                            direction=pos_data["direction"],
                            entry_price=pos_data["entry_price"],
                        )
                        logger.info(
                            f"[auto-trader] Backfilled stop_loss on restored "
                            f"{pos_data['symbol']} {pos_data['direction']} "
                            f"@ ${restored_sl:.4f}"
                        )
                    p.positions.append(PaperPosition(
                        symbol=pos_data["symbol"],
                        direction=pos_data["direction"],
                        entry_price=pos_data["entry_price"],
                        current_price=pos_data.get("current_price", pos_data["entry_price"]),
                        size_usd=pos_data["size_usd"],
                        unrealized_pnl=pos_data.get("unrealized_pnl", 0.0),
                        recommendation_id=pos_data.get("recommendation_id", "auto-restored"),
                        opened_at=pos_data.get("opened_at", "2026-01-01T00:00:00+00:00"),
                        stop_loss=restored_sl,
                        take_profit=pos_data.get("take_profit"),
                        trailing_stop_pct=pos_data.get("trailing_stop_pct"),
                        trailing_stop_peak=pos_data.get("trailing_stop_peak"),
                    ))
                logger.info(f"[auto-trader] Restored from snapshot: equity=${p.equity}, {len(p.positions)} positions")
        except Exception as e:
            logger.warning(f"[auto-trader] Could not restore from snapshot: {e}")

    def _load_yolo_level(self) -> int:
        """Load persisted YOLO level — per-wallet config takes priority, then global."""
        # Per-wallet config takes priority
        if self._wallet_config and "yolo_level" in self._wallet_config:
            level = int(self._wallet_config["yolo_level"])
            if 1 <= level <= 5:
                logger.info(f"[auto-trader] YOLO level {level} from wallet config")
                return level
        # Fall back to global wp_runtime_config (legacy)
        try:
            from wolfpack.db import get_db
            db = get_db()
            rows = db.table("wp_runtime_config").select("value").eq("key", "yolo_level").execute().data
            if rows:
                level = int(rows[0]["value"])
                if 1 <= level <= 5:
                    logger.info(f"[auto-trader] Restored YOLO level {level} from DB")
                    return level
        except Exception as e:
            logger.warning(f"[auto-trader] Failed to load YOLO level from DB: {e}")
        return 4

    def _save_yolo_level(self) -> None:
        """Persist current YOLO level to wallet config JSONB (if wallet_id) + legacy global."""
        # Update in-memory wallet config
        self._wallet_config["yolo_level"] = self.yolo_level
        if self.wallet_id:
            try:
                from wolfpack.db import get_db
                db = get_db()
                db.table("wp_wallets").update(
                    {"config": self._wallet_config, "updated_at": datetime.now(timezone.utc).isoformat()}
                ).eq("id", self.wallet_id).execute()
            except Exception as e:
                logger.warning(f"[auto-trader] Failed to save YOLO to wallet config: {e}")
                # Fall through to legacy save
        # Legacy global save as fallback
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_runtime_config").upsert(
                {"key": "yolo_level", "value": self.yolo_level, "updated_at": datetime.now(timezone.utc).isoformat()},
                on_conflict="key",
            ).execute()
        except Exception as e:
            logger.warning(f"[auto-trader] Failed to save YOLO level to DB: {e}")

    def _apply_yolo_profile(self) -> None:
        """Apply YOLO profile settings to all throttle layers."""
        profile = YOLO_PROFILES.get(self.yolo_level, YOLO_PROFILES[2])
        self.conviction_threshold = profile["conviction_threshold"]
        self._yolo_profile = profile

    def _apply_wallet_config(self) -> None:
        """Apply per-wallet config overrides on top of YOLO profile defaults."""
        if not self._wallet_config:
            return
        cfg = self._wallet_config
        # These override the YOLO profile values when set in wallet config
        if "conviction_floor" in cfg:
            self.conviction_threshold = int(cfg["conviction_floor"])
        # Store sizing overrides for use in process_recommendations
        self._wallet_sizing = {}
        for key in ("brief_only_mult", "min_perf_mult", "min_position_usd", "trade_spacing_s"):
            if key in cfg:
                self._wallet_sizing[key] = cfg[key]

        # Phase 3: human heuristics — load state if wallet has it enabled
        if cfg.get("heuristics_enabled") and self.wallet_id:
            try:
                from wolfpack.heuristics import HeuristicState
                from wolfpack.db import get_db
                self._heuristic_state = HeuristicState.load(self.wallet_id, get_db())
                self._heuristic_state.daily_pnl_target = float(cfg.get("daily_pnl_target", 300.0))
                self._heuristics_enabled = True
                logger.info(
                    f"[heuristics] v3 enabled for {self.wallet_id[:8]}: "
                    f"target=${self._heuristic_state.daily_pnl_target:.0f}, "
                    f"hunger={self._heuristic_state.hunger:.2f} fear={self._heuristic_state.fear:.2f}"
                )
            except Exception as e:
                logger.warning(f"[heuristics] init failed: {e}")
                self._heuristic_state = None
                self._heuristics_enabled = False

    def _refresh_heuristics(self) -> float:
        """Refresh v3 heuristic state: decay, poll closed trades, update target progress.

        Returns today's realized P&L (0.0 on error) so callers can reuse it.
        """
        if not self._heuristics_enabled or self._heuristic_state is None:
            return 0.0
        state = self._heuristic_state
        try:
            from wolfpack.db import get_db
            db = get_db()
        except Exception:
            return 0.0

        # 1. Decay drives toward baseline each cycle
        state.decay(cycles=1)

        # 2. Poll new closed trades since last check and apply per-trade events
        since = self._heuristics_last_close_check or (datetime.now(timezone.utc) - timedelta(hours=1))
        try:
            r = (
                db.table("wp_trade_history")
                .select("pnl_usd,hold_duration_seconds,closed_at")
                .eq("wallet_id", self.wallet_id)
                .gt("closed_at", since.isoformat())
                .execute()
            )
            for row in r.data or []:
                pnl = float(row.get("pnl_usd") or 0)
                hold_s = row.get("hold_duration_seconds") or 0
                state.on_trade_close(pnl, hold_s / 3600.0)
        except Exception as e:
            logger.warning(f"[heuristics] trade close poll failed: {e}")
        self._heuristics_last_close_check = datetime.now(timezone.utc)

        # 3. Compute today's daily realized P&L and update target progress
        daily_pnl = 0.0
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            r = (
                db.table("wp_trade_history")
                .select("pnl_usd")
                .eq("wallet_id", self.wallet_id)
                .gte("closed_at", today_start.isoformat())
                .execute()
            )
            daily_pnl = sum(float(row.get("pnl_usd") or 0) for row in (r.data or []))
            if state.daily_pnl_target > 0:
                state.on_target_progress(daily_pnl, state.daily_pnl_target)
        except Exception as e:
            logger.warning(f"[heuristics] daily pnl fetch failed: {e}")

        # 4. Persist state + history
        try:
            state.save(
                db,
                event="cycle_refresh",
                daily_pnl=daily_pnl,
                equity=self.engine.portfolio.equity,
            )
        except Exception as e:
            logger.warning(f"[heuristics] save failed: {e}")

        logger.info(
            f"[heuristics] v3 refreshed: daily_pnl=${daily_pnl:+.2f}/${state.daily_pnl_target:.0f} "
            f"H={state.hunger:.2f} S={state.satisfaction:.2f} F={state.fear:.2f} C={state.curiosity:.2f} "
            f"conv_mod={state.conviction_modifier():+d} size_mod={state.size_modifier():.2f}"
        )
        return daily_pnl

    def set_regime(self, macro_regime: str) -> None:
        """Store current macro regime for filtering decisions."""
        self._current_regime = macro_regime

    def set_vwap(self, symbol: str, vwap: float) -> None:
        """Store latest VWAP for a symbol. Called from the intelligence cycle."""
        if vwap > 0:
            self._latest_vwaps[symbol] = vwap

    def _is_pumping(self, symbol: str, latest_prices: dict[str, float]) -> bool:
        """Check if price moved up >2% recently by comparing to 1h-ago snapshot.

        Uses the last stored price from wp_portfolio_snapshots as baseline.
        Conservative: only blocks shorts, never blocks longs.
        """
        try:
            current = latest_prices.get(symbol)
            if not current:
                return False
            from wolfpack.db import get_db
            db = get_db()
            # Get price from ~1 hour ago via candle data or snapshot
            query = db.table("wp_portfolio_snapshots").select("positions").order("created_at", desc=True).limit(12)
            if self.wallet_id:
                query = query.eq("wallet_id", self.wallet_id)
            result = query.execute()
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
        cycle_recorder: Any = None,
    ) -> list[dict]:
        """Process recommendations from the intelligence cycle.

        Returns list of auto-executed trade dicts.

        Phase 1.3: if `cycle_recorder` (a CycleMetricsRecorder) is supplied,
        sizing-block events are reported via record_sizing_block() so they
        land in wp_cycle_metrics.sizing_blocked_reasons.
        """
        if not self.enabled:
            return []

        self.restore_from_snapshot()

        # Phase 3: refresh v3 heuristic drives once per cycle (no-op on v1/v2)
        if self._heuristics_enabled:
            try:
                self._refresh_heuristics()
            except Exception as e:
                logger.warning(f"[heuristics] refresh failed: {e}")

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

            # Dynamic threshold based on performance — TOXIC combos blocked entirely
            dynamic_threshold = self._perf_tracker.get_threshold(
                symbol, direction, self.conviction_threshold, regime=self._current_regime
            )

            # Phase 3: v3 heuristic drives — adjust floor + detect unfamiliar setups
            if self._heuristics_enabled and self._heuristic_state is not None:
                _score, _tier = self._perf_tracker._lookup_grade(symbol, direction, self._current_regime)
                if _tier == "none":
                    self._heuristic_state.on_unfamiliar_setup("none")
                # hunger lowers floor, fear/satisfaction raise it
                base_dt = dynamic_threshold
                dynamic_threshold = max(30, dynamic_threshold + self._heuristic_state.conviction_modifier())
                if base_dt != dynamic_threshold:
                    logger.info(
                        f"[heuristics] {symbol} {direction} floor {base_dt} -> {dynamic_threshold} "
                        f"({self._heuristic_state.conviction_modifier():+d})"
                    )

            if dynamic_threshold >= 999:
                score, tier = self._perf_tracker._lookup_grade(symbol, direction, self._current_regime)
                if score is not None:
                    logger.info(
                        f"[auto-trader] BLOCKED {symbol} {direction} in {self._current_regime}: "
                        f"TOXIC ({tier}, {score.trades}t, {score.win_rate:.0%} WR, ${score.net_pnl:+,.0f})"
                    )
                else:
                    logger.info(f"[auto-trader] BLOCKED {symbol} {direction}: TOXIC grade")
                continue
            if conviction < dynamic_threshold:
                logger.info(f"[auto-trader] {symbol} {direction} conviction {conviction} < dynamic threshold {dynamic_threshold}, skipping")
                continue

            # Veto check
            cb_dict = cb_output.model_dump() if hasattr(cb_output, "model_dump") else cb_output
            vol_dict = vol_output.model_dump() if hasattr(vol_output, "model_dump") else vol_output
            veto_result = veto.evaluate(
                rec,
                cb_output=cb_dict,
                vol_output=vol_dict,
                cycle_id=getattr(cycle_recorder, "cycle_id", None) if cycle_recorder is not None else None,
            )
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

            # VWAP filter: penalize longs below VWAP (severity scales inversely with YOLO)
            if direction == "long":
                vwap = self._latest_vwaps.get(symbol, 0)
                current_price = (latest_prices or {}).get(symbol, 0)
                if vwap > 0 and current_price > 0 and current_price < vwap:
                    if self.yolo_level <= 2:
                        # Conservative: hard block
                        logger.info(f"[auto-trader] {symbol} long blocked: price ${current_price:,.2f} below VWAP ${vwap:,.2f}")
                        continue
                    elif self.yolo_level == 3:
                        # Active: soft penalty -15 conviction
                        conviction = max(conviction - 15, 0)
                        logger.info(f"[auto-trader] {symbol} long penalized -15 (below VWAP), conviction now {conviction}")
                    elif self.yolo_level == 4:
                        # YOLO: soft penalty -5 conviction
                        conviction = max(conviction - 5, 0)
                        logger.info(f"[auto-trader] {symbol} long penalized -5 (below VWAP), conviction now {conviction}")
                    # Level 5: no VWAP filter at all

            # Trading hours restriction — only open new positions during allowed UTC hours
            current_utc_hour = datetime.now(timezone.utc).hour
            if not (settings.trading_hours_start <= current_utc_hour < settings.trading_hours_end):
                logger.info(f"[auto-trader] {symbol} {direction} blocked: UTC hour {current_utc_hour} outside {settings.trading_hours_start}-{settings.trading_hours_end}")
                continue

            # Pump guard — cap short exposure to prevent cascade losses on sudden pumps
            if direction == "short":
                open_shorts = sum(1 for p in self.engine.portfolio.positions if p.direction == "short")
                max_shorts = {1: 2, 2: 3, 3: 4, 4: 5, 5: 7}.get(self.yolo_level, 3)
                if open_shorts >= max_shorts:
                    logger.info(f"[auto-trader] {symbol} short blocked: {open_shorts} shorts open (max {max_shorts} at YOLO {self.yolo_level})")
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
            # Brief-only multiplier scales with YOLO level
            yolo_sizing = {**_YOLO_SIZING.get(self.yolo_level, _YOLO_SIZING[2])}
            # Per-wallet sizing overrides
            if hasattr(self, '_wallet_sizing'):
                yolo_sizing.update(self._wallet_sizing)
            if has_mechanical:
                size_multiplier = 1.0  # Full size -- Brief + mechanical agree
                logger.info(f"[auto-trader] Brief+mechanical aligned for {symbol} {direction}")
            else:
                size_multiplier = yolo_sizing["brief_only_mult"]

            size_pct = min(size_pct * size_multiplier, profile["max_size_pct"])

            # Apply performance-based size multiplier (floored by YOLO level)
            perf_mult = self._perf_tracker.get_size_multiplier(
                symbol, direction, regime=self._current_regime
            )
            perf_mult = max(perf_mult, yolo_sizing["min_perf_mult"])

            # Phase 3: v3 heuristics size modulation — hunger scales up, fear scales down
            if self._heuristics_enabled and self._heuristic_state is not None:
                hmod = self._heuristic_state.size_modifier()
                # Extra shrink on unfamiliar setups (curiosity funds small exploration)
                _score2, _tier2 = self._perf_tracker._lookup_grade(symbol, direction, self._current_regime)
                if _tier2 == "none":
                    explore = 0.2 + 0.3 * self._heuristic_state.exploration_budget()
                    hmod = min(hmod, explore)
                    logger.info(
                        f"[heuristics] {symbol} {direction} explore-sizing mult={hmod:.2f} "
                        f"(budget={self._heuristic_state.exploration_budget():.2f})"
                    )
                perf_mult *= hmod

            size_pct = size_pct * perf_mult

            if size_pct <= 0:
                if cycle_recorder is not None:
                    try:
                        cycle_recorder.record_sizing_block(
                            symbol=symbol,
                            direction=direction,
                            attempted_usd=0.0,
                            floor_usd=float(yolo_sizing["min_position_usd"]),
                            reason="size_pct<=0 after perf_mult",
                            size_multiplier=size_multiplier,
                            perf_mult=perf_mult,
                        )
                    except Exception:
                        pass
                continue

            # Trade spacing cooldown (scales with YOLO level)
            spacing_s = yolo_sizing["trade_spacing_s"]
            if self._last_trade_at:
                elapsed = (datetime.now(timezone.utc) - self._last_trade_at).total_seconds()
                if elapsed < spacing_s:
                    logger.info(f"[auto-trader] Trade spacing: {spacing_s - elapsed:.0f}s remaining")
                    continue

            # Enforce minimum position size (scales with YOLO level)
            min_pos_usd = yolo_sizing["min_position_usd"]
            estimated_usd = self.engine.portfolio.equity * (size_pct / 100)
            if estimated_usd < min_pos_usd:
                logger.info(f"[auto-trader] {symbol} {direction} skipped: ${estimated_usd:.0f} < ${min_pos_usd:.0f} minimum (YOLO {self.yolo_level})")
                if cycle_recorder is not None:
                    try:
                        cycle_recorder.record_sizing_block(
                            symbol=symbol,
                            direction=direction,
                            attempted_usd=float(estimated_usd),
                            floor_usd=float(yolo_sizing["min_position_usd"]),
                            reason="below_min_position_usd",
                            size_multiplier=size_multiplier,
                            perf_mult=perf_mult,
                        )
                    except Exception:
                        pass
                continue
            if estimated_usd > settings.max_position_usd:
                size_pct = (settings.max_position_usd / self.engine.portfolio.equity) * 100
                logger.info(f"[auto-trader] {symbol} {direction} capped at ${settings.max_position_usd:.0f}")

            # Open position
            pos = self.engine.open_position(
                symbol=symbol,
                direction=direction,
                current_price=round_price(entry_price),
                size_pct=min(size_pct, profile["max_size_pct"]),
                recommendation_id=f"auto-{rec.get('id', 'unknown')}",
                max_positions_per_symbol=profile.get("max_positions_per_symbol", 1),
                regime_at_entry=self._current_regime,
                conviction_at_entry=veto_result.final_conviction,
            )

            if pos:
                self._last_trade_at = datetime.now(timezone.utc)
                if rec.get("stop_loss"):
                    pos.stop_loss = rec["stop_loss"]
                else:
                    # Auto stop-loss fallback: Brief often omits stop_loss.
                    # Set a mechanical SL at per-symbol bps distance from
                    # entry so every position has defined risk.
                    pos.stop_loss = _compute_default_stop_loss(
                        symbol=symbol,
                        direction=direction,
                        entry_price=pos.entry_price,
                    )
                    logger.info(
                        f"[auto-trader] {symbol} {direction} auto stop_loss "
                        f"@ ${pos.stop_loss:.4f} (Brief omitted SL)"
                    )
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

            # Protect mechanical strategy positions from premature Brief closes.
            # When a wallet opts into `protect_mechanical_positions`, Brief cannot
            # close a position whose recommendation_id starts with "strat-" unless
            # an emergency condition is met: held > 30 min, loss > 1.5%, or regime
            # shifted from entry. This lets band_fade / mean_reversion / trend_pullback
            # run to their own SL/TP instead of being flattened on first red tick.
            if (
                action == "close"
                and self._wallet_config is not None
                and self._wallet_config.get("protect_mechanical_positions", False)
                and getattr(pos, "recommendation_id", None)
                and str(pos.recommendation_id).startswith("strat-")
            ):
                try:
                    hold_s = (datetime.now(timezone.utc) - pos.opened_at).total_seconds()
                except Exception:
                    hold_s = 0.0
                loss_pct = 0.0
                if getattr(pos, "size_usd", 0) and pos.unrealized_pnl is not None and pos.unrealized_pnl < 0:
                    loss_pct = -(pos.unrealized_pnl / pos.size_usd) * 100
                regime_shifted = (
                    getattr(pos, "regime_at_entry", None)
                    and pos.regime_at_entry not in (None, "unknown")
                    and self._current_regime not in (None, "unknown")
                    and pos.regime_at_entry != self._current_regime
                )
                if hold_s < 1800 and loss_pct < 1.5 and not regime_shifted:
                    logger.info(
                        f"[auto-trader] Brief close BLOCKED on strat position {pa_symbol}: "
                        f"held {hold_s:.0f}s, loss {loss_pct:.2f}%, "
                        f"regime {pos.regime_at_entry}->{self._current_regime} — "
                        f"protect_mechanical_positions"
                    )
                    # Mark action as auto_executed so it doesn't re-queue each cycle
                    if action_id:
                        try:
                            db.table("wp_position_actions").delete().eq(
                                "symbol", pa_symbol
                            ).eq("action", action).eq("status", "auto_executed").execute()
                            db.table("wp_position_actions").update({
                                "status": "auto_executed",
                                "acted_at": datetime.now(timezone.utc).isoformat(),
                            }).eq("id", action_id).execute()
                        except Exception:
                            pass
                    continue

            if action == "close":
                current_price = (latest_prices or {}).get(pa_symbol, pos.current_price)
                self.engine.update_prices({pa_symbol: current_price})
                pnl = self.engine.close_position(
                    pa_symbol,
                    exit_reason="brief_close",
                    regime_at_exit=self._current_regime,
                )
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

            # Update DB status to auto_executed.
            # Unique constraint on (symbol, action, status) means only one
            # auto_executed row per (symbol, action) can exist. Delete any
            # prior auto_executed row before transitioning this one, so we
            # don't spam the logs with duplicate-key warnings every cycle.
            if action_id:
                try:
                    db.table("wp_position_actions").delete().eq(
                        "symbol", pa_symbol
                    ).eq("action", action).eq("status", "auto_executed").execute()
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
        """Store an auto-trade to Supabase.

        NOTE: wp_auto_trades writes removed (legacy table, nothing reads it).
        Trades are persisted via paper_trading._store_closed_trade -> wp_trade_history.
        """
        # Intentionally no-op — kept as hook for future auditing if needed.
        pass

    def _store_snapshot(self) -> None:
        """Store auto-trader portfolio snapshot to Supabase.

        Wave 3: writes to wp_portfolio_snapshots with wallet_id + enrichment.
        Includes exchange_id (NOT NULL column) — previously omitted, which
        caused every wave-5 snapshot write to fail silently and trades to
        be lost on restart.

        Resilient to missing DB columns — retries without problematic fields.
        """
        try:
            from wolfpack.db import get_db
            db = get_db()
            p = self.engine.portfolio
            snapshot = {
                "exchange_id": "hyperliquid",  # NOT NULL column; default target
                "equity": round(p.equity, 2),
                "free_collateral": round(p.free_collateral, 2),
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "realized_pnl": round(p.realized_pnl, 2),
                "positions": [pos.model_dump(mode="json") for pos in p.positions],
                "wallet_id": self.wallet_id,
                "open_position_count": len(p.positions),
                "total_exposure_usd": round(
                    sum(abs(getattr(pos, "size_usd", 0) or 0) for pos in p.positions), 2
                ),
                "regime_state": self._current_regime,
            }
            try:
                db.table("wp_portfolio_snapshots").insert(snapshot).execute()
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
                    db.table("wp_portfolio_snapshots").insert(snapshot).execute()
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
        specific_regime = routing.get("specific_regime", routing.get("macro_regime", "unknown"))
        macro_family = routing.get("macro_regime", "unknown")
        # Sync _current_regime so per-wallet traders get the live regime.
        # api.py only calls set_regime() on the primary trader, so v2/v3 were stuck
        # at "unknown" — breaking regime_at_entry tags and PerformanceTracker grading.
        self._current_regime = specific_regime
        logger.info(
            f"[auto-trader] Regime routing: {specific_regime} "
            f"(family={macro_family}) -- {routing['reason']} [{debounce}]"
        )

        # Regime validation feedback loop — tick existing pending validations
        # every cycle, and record a new one whenever the specific regime
        # actually changes for this symbol.
        try:
            from wolfpack.strategies import regime_validator as _rv
            _cur_price = float(candles[-1].close) if candles else 0.0
            _atr_for_val = 0.0
            if len(candles) >= 15:
                # Reuse the mean_reversion ATR helper on the last 15 bars
                from wolfpack.strategies.mean_reversion import MeanReversionStrategy as _MR
                _atr_for_val = _MR._compute_atr(candles[-15:], 14)
            _rv.tick(symbol, _cur_price, _atr_for_val)
            # Only record on a real regime shift — use a per-symbol cache
            if not hasattr(self, "_regime_validator_seen"):
                self._regime_validator_seen = {}
            if self._regime_validator_seen.get(symbol) != specific_regime:
                _rv.record_classification(
                    symbol=symbol,
                    regime=specific_regime,
                    anchor_price=_cur_price,
                    anchor_atr=_atr_for_val,
                )
                self._regime_validator_seen[symbol] = specific_regime
        except Exception as _e:
            logger.debug(f"[regime-validator] {symbol} tick/record failed: {_e}")

        # VOLATILE: tighten trailing stops, no new entries
        if macro_family == "VOLATILE":
            for pos in self.engine.portfolio.positions:
                if pos.trailing_stop_pct and pos.trailing_stop_pct > 1.5:
                    pos.trailing_stop_pct = max(1.5, pos.trailing_stop_pct * 0.5)
            self._store_snapshot()
            return []

        # TRANSITION: regime is changing but debounce not confirmed.
        # Tighten trailing stops on existing positions and block new entries
        # until the new regime stabilizes. Distinct from VOLATILE — this is a
        # "wait and see" posture, not a panic posture.
        if routing.get("transition"):
            tightened = 0
            for pos in self.engine.portfolio.positions:
                if pos.trailing_stop_pct and pos.trailing_stop_pct > 2.0:
                    pos.trailing_stop_pct = max(2.0, pos.trailing_stop_pct * 0.7)
                    tightened += 1
            if tightened:
                logger.info(
                    f"[auto-trader] {symbol} TRANSITION: tightened {tightened} trailing stops "
                    f"(pending={routing.get('debounce','')})"
                )
            self._store_snapshot()
            return []

        # Check regime transition cooldown (separate legacy cooldown mechanism)
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

            # Per-wallet kill switch: lets a wallet disable individual strategies
            # without touching code. Used when empirical evidence shows a strategy
            # has lost its edge (e.g., mean_reversion after the Apr 11 regime shift).
            if self._wallet_config is not None:
                _disabled = self._wallet_config.get("disabled_strategies") or []
                if strategy_name in _disabled:
                    continue

            # Check timeframe compatibility
            expected_tf = STRATEGY_TIMEFRAMES.get(strategy_name, "1h")
            if expected_tf != timeframe:
                continue

            try:
                strategy = strategy_cls()
                if current_idx < strategy.warmup_bars:
                    continue

                # Pass the specific sub-regime so strategies can auto-adapt:
                # - mean_reversion: RANGING_LOW_VOL → tight thresholds, RANGING_HIGH_VOL → wider
                # - band_fade: only fires in RANGING_* variants
                # - ema_crossover / turtle_donchian: directional gating on TRENDING_UP vs TRENDING_DOWN
                # Strategies that want the parent family can call regime_family(specific_regime).
                signal = strategy.evaluate(
                    candles,
                    current_idx,
                    macro_regime=specific_regime,
                )
                if signal is None:
                    continue

                direction = signal.get("direction", "wait")
                if direction == "wait":
                    continue

                # VWAP filter on mechanical longs (scales with YOLO level)
                # Uses the latest candle close since process_strategy_signals doesn't
                # receive latest_prices (pre-existing NameError bug — was swallowing
                # every mechanical long signal).
                if direction == "long":
                    vwap = self._latest_vwaps.get(symbol, 0)
                    current_price = float(candles[current_idx].close) if candles else 0
                    if vwap > 0 and current_price > 0 and current_price < vwap:
                        if self.yolo_level <= 2:
                            logger.info(f"[auto-trader] {symbol} mech long blocked: below VWAP")
                            continue
                        elif self.yolo_level == 3:
                            signal["conviction"] = max(signal.get("conviction", 60) - 15, 0)
                            logger.info(f"[auto-trader] {symbol} mech long penalized -15 (below VWAP)")
                        elif self.yolo_level == 4:
                            signal["conviction"] = max(signal.get("conviction", 60) - 5, 0)
                            logger.info(f"[auto-trader] {symbol} mech long penalized -5 (below VWAP)")
                        # Level 5: no VWAP filter

                rec_id = f"strat-{strategy_name}-{symbol}-{timestamp}"

                # Handle close signals — close positions with matching strategy tag
                if direction == "close":
                    for pos in list(self.engine.portfolio.positions):
                        if pos.symbol == symbol and pos.recommendation_id.startswith(f"strat-{strategy_name}-"):
                            pnl = self.engine.close_position(
                                symbol,
                                exit_reason="strategy_close",
                                regime_at_exit=self._current_regime,
                            )
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

                # Trade spacing cooldown — uses per-wallet config if present.
                # Default 120s so strategies can cycle faster in low-vol scalp
                # posture. v1 YOLO 5 uses 30s, v2/v3 use 120s (reset earlier
                # from 300s).
                _spacing = int(self._wallet_config.get("trade_spacing_s", 120)) if self._wallet_config else 120
                if self._last_trade_at:
                    elapsed = (datetime.now(timezone.utc) - self._last_trade_at).total_seconds()
                    if elapsed < _spacing:
                        logger.info(
                            f"[auto-trader] Strategy {strategy_name} trade spacing: "
                            f"{_spacing - elapsed:.0f}s remaining (limit {_spacing}s), skipping"
                        )
                        continue

                # Size based on strategy allocation
                size_pct = allocation * 100  # e.g. 0.20 -> 20%
                size_pct = min(size_pct, profile["max_size_pct"])

                # Enforce $3K-$5K position size sweet spot
                estimated_usd = self.engine.portfolio.equity * (size_pct / 100)
                yolo_sizing = {**_YOLO_SIZING.get(self.yolo_level, _YOLO_SIZING[2])}
                # Per-wallet sizing overrides
                if hasattr(self, '_wallet_sizing'):
                    yolo_sizing.update(self._wallet_sizing)
                min_pos_usd = yolo_sizing["min_position_usd"]
                if estimated_usd < min_pos_usd:
                    logger.info(f"[auto-trader] Strategy {strategy_name} {symbol} {direction} skipped: ${estimated_usd:.0f} < ${min_pos_usd:.0f} minimum (YOLO {self.yolo_level})")
                    continue
                if estimated_usd > settings.max_position_usd:
                    size_pct = (settings.max_position_usd / self.engine.portfolio.equity) * 100
                    logger.info(f"[auto-trader] Strategy {strategy_name} {symbol} {direction} capped at ${settings.max_position_usd:.0f}")

                pos = self.engine.open_position(
                    symbol=symbol,
                    direction=direction,
                    current_price=round_price(signal.get("entry_price", candles[current_idx].close)),
                    size_pct=size_pct,
                    recommendation_id=rec_id,
                    max_positions_per_symbol=profile.get("max_positions_per_symbol", 1),
                    regime_at_entry=self._current_regime,
                    conviction_at_entry=signal.get("conviction", 75),
                )

                if pos:
                    self._last_trade_at = datetime.now(timezone.utc)

                    # Set stop_loss/take_profit from strategy signal
                    if signal.get("stop_loss"):
                        pos.stop_loss = signal["stop_loss"]
                    else:
                        # Auto SL fallback — same mechanical SL as Brief path
                        pos.stop_loss = _compute_default_stop_loss(
                            symbol=symbol,
                            direction=direction,
                            entry_price=pos.entry_price,
                        )
                        logger.info(
                            f"[auto-trader] Strategy {strategy_name} {symbol} {direction} "
                            f"auto stop_loss @ ${pos.stop_loss:.4f}"
                        )
                    if signal.get("take_profit"):
                        pos.take_profit = signal["take_profit"]

                    # Place exchange stop orders (live mode only)
                    if hasattr(self.engine, 'place_exchange_stops'):
                        self.engine.place_exchange_stops(symbol)

                    # Trailing stop in addition to hard SL (belt-and-suspenders)
                    if pos.stop_loss is not None:
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
                        pos.stop_loss = round_price(new_stop)
                        changed = True
                        logger.info(f"[auto-trader] HTF trailing: {symbol} long stop -> ${pos.stop_loss}")

            elif pos.direction == "short":
                if current_bar.low < prev_bar.low:
                    buffer = current_bar.close * 0.005
                    new_stop = current_bar.high + buffer
                    if new_stop < pos.stop_loss:
                        pos.stop_loss = round_price(new_stop)
                        changed = True
                        logger.info(f"[auto-trader] HTF trailing: {symbol} short stop -> ${pos.stop_loss}")

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
            "yolo_sizing": _YOLO_SIZING.get(self.yolo_level, _YOLO_SIZING[2]),
            "type": "AutoBot",
        }
