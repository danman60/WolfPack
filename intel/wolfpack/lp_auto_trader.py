"""LP AutoTrader — orchestrates paper LP engine + position monitoring.

Follows the AutoTrader pattern: singleton via api.py, restore from snapshot,
process_tick() called from the main intelligence cycle.

Pool rotation: scanner discovers high-yield pools every 6 cycles (3 hours),
positions are rotated out when APR declines or better alternatives appear.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from wolfpack.config import settings

logger = logging.getLogger(__name__)

MAX_POSITIONS = settings.lp_max_positions


class LPAutoTrader:
    """Autonomous LP position manager with paper trading engine."""

    def __init__(self) -> None:
        from wolfpack.lp_paper_engine import PaperLPEngine
        from wolfpack.modules.lp_monitor import LPPositionMonitor
        from wolfpack.modules.lp_range_calculator import LPRangeCalculator
        from wolfpack.modules.lp_fee_manager import LPFeeManager
        from wolfpack.modules.lp_rebalance import LPRebalanceEngine
        from wolfpack.modules.lp_pool_scanner import LPPoolScanner

        self._enabled = settings.lp_auto_enabled
        self.engine = PaperLPEngine(starting_equity=settings.lp_starting_equity)
        self.monitor = LPPositionMonitor()
        self.range_calc = LPRangeCalculator()
        self.fee_manager = LPFeeManager()
        self.rebalance_engine = LPRebalanceEngine()
        self.pool_scanner = LPPoolScanner()
        self._restored = False
        # IL hedge tracking: {lp_position_id: {"hedge_size": float, "hedge_entry": float, "last_adjusted": datetime}}
        self._il_hedges: dict[str, dict] = {}
        # Load watched pools from config as seeds (scanner adds dynamically)
        self._config_pools: list[str] = [
            p.strip() for p in (settings.lp_watched_pools or "").split(",") if p.strip()
        ]
        self._watched_pools: list[str] = list(self._config_pools)
        if self._watched_pools:
            logger.info(f"[lp-trader] Loaded {len(self._watched_pools)} seed pools from config")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def restore_from_snapshot(self) -> None:
        """Load latest snapshot from wp_lp_snapshots, rebuild engine state."""
        if self._restored:
            return
        self._restored = True

        try:
            self.engine.restore_from_snapshot()
            logger.info("[lp-trader] Restored from snapshot")
        except Exception as e:
            logger.warning(f"[lp-trader] Could not restore from snapshot: {e}")

    async def process_tick(self, regime_output: Any = None, vol_output: Any = None) -> dict:
        """Main entry point called from _run_full_cycle().

        1. Restore from snapshot (if first call)
        2. Periodic pool scan (every 6 cycles = 3 hours)
        3. Rotation check — exit underperforming positions
        4. For each watched pool: fetch pool state via monitor
        5. Open positions in top-scoring pools (up to MAX_POSITIONS)
        6. Rebalance, fee harvest, alerts
        7. Store snapshot
        """
        self.restore_from_snapshot()

        alerts: list[dict] = []
        pools_checked = 0

        # STEP 0: Periodic pool scan (every 6 cycles)
        if self.pool_scanner.should_scan():
            candidates = await self.pool_scanner.scan()
            if candidates:
                self._update_watch_list(candidates)

        if not self._watched_pools:
            return {"alerts": [], "pools_checked": 0, "positions": 0}

        # Extract regime + vol context for range calculator
        macro = "unknown"
        ema_trend = 0.0
        confidence = 0.5
        vol_regime = "normal"
        realized_vol = 30.0

        if regime_output:
            regime_str = regime_output.regime.value if hasattr(regime_output.regime, "value") else str(regime_output.regime)
            agreement = regime_output.sub_signals.multi_tf_agreement if regime_output.sub_signals else 1.0
            ema_trend = regime_output.sub_signals.ema_trend_score if regime_output.sub_signals else 0.0
            confidence = regime_output.confidence
            if regime_str == "panic":
                macro = "VOLATILE"
            elif regime_str in ("trending_up", "trending_down") and agreement >= 0.75:
                macro = "TRENDING"
            else:
                macro = "RANGING"

        if vol_output:
            vol_regime = vol_output.get("vol_regime", "normal") if isinstance(vol_output, dict) else getattr(vol_output, "vol_regime", "normal")
            realized_vol = vol_output.get("realized_vol_1d", 30) if isinstance(vol_output, dict) else getattr(vol_output, "realized_vol_1d", 30)

        # STEP 1: Rotation check — exit underperforming positions
        for pos in list(self.engine.portfolio.positions):
            if pos.status != "active":
                continue
            should_exit, reason = self._should_exit_pool(pos)
            if should_exit:
                net_pnl = self.engine.close_position(pos.pool_address)
                # Close any IL hedge tied to this position
                if pos.position_id in self._il_hedges:
                    hedge = self._il_hedges.pop(pos.position_id)
                    logger.info(f"[lp-hedge] Closed IL hedge on rotation: ${hedge['hedge_size']:.2f}")
                logger.info(f"[lp-auto] ROTATED OUT: {pos.token0_symbol}/{pos.token1_symbol} — {reason} (net PnL: ${net_pnl:.2f})")
                self._store_rotation_event(pos, reason, net_pnl)
                alerts.append({
                    "type": "rotation_exit",
                    "pair": f"{pos.token0_symbol}/{pos.token1_symbol}",
                    "message": f"Rotated out: {reason}, net ${net_pnl:.2f}",
                })

        # STEP 2: Batch fetch all pool states (RPC + GeckoTerminal)
        pool_states = await self.monitor.fetch_pool_states(self._watched_pools)

        # STEP 3: Update existing positions + open in top-scoring pools
        active_pools = {p.pool_address.lower() for p in self.engine.portfolio.positions if p.status == "active"}
        active_count = len(active_pools)
        candidates = self.pool_scanner.get_candidates()

        # Build priority list: scanner candidates first (by score), then remaining watched pools
        candidate_addresses = [c.address for c in candidates]
        priority_pools = candidate_addresses + [p for p in self._watched_pools if p not in candidate_addresses]

        for pool_address in priority_pools:
            try:
                state = pool_states.get(pool_address)
                if state is None:
                    continue

                pools_checked += 1

                # Compute price ratio from sqrtPriceX96
                price_ratio = self.monitor.compute_price_ratio(state.sqrt_price_x96)
                if price_ratio <= 0:
                    # Fallback: use USD prices if available
                    if state.token1_price_usd and state.token1_price_usd > 0:
                        price_ratio = state.token0_price_usd / state.token1_price_usd
                    else:
                        continue

                # Auto-open: if no existing position and under MAX_POSITIONS
                if pool_address.lower() not in active_pools and active_count < MAX_POSITIONS:
                    recommendation = self.range_calc.compute_range(
                        current_tick=state.current_tick,
                        fee_tier=state.fee_tier,
                        regime_macro=macro,
                        vol_regime=vol_regime,
                        realized_vol_1d=realized_vol,
                        ema_trend_score=ema_trend,
                        confidence=confidence,
                    )
                    if recommendation:
                        safe_ratio = price_ratio if price_ratio > 0 else 1.0
                        pos = self.engine.open_position(
                            pool_address=pool_address,
                            token0_symbol=state.token0_symbol,
                            token1_symbol=state.token1_symbol,
                            fee_tier=state.fee_tier,
                            tick_lower=recommendation.tick_lower,
                            tick_upper=recommendation.tick_upper,
                            size_pct=recommendation.size_pct,
                            current_tick=state.current_tick,
                            current_price_ratio=safe_ratio,
                        )
                        if pos:
                            active_pools.add(pool_address.lower())
                            active_count += 1
                            logger.info(f"[lp-auto] Opened paper LP {state.token0_symbol}/{state.token1_symbol} {recommendation.reason}")

                # Update paper engine positions for this pool
                self.engine.update_position(
                    pool_address=pool_address,
                    current_tick=state.current_tick,
                    current_price_ratio=price_ratio,
                    pool_volume_24h=state.volume_usd_24h,
                    pool_tvl=state.tvl_usd,
                )

            except Exception as e:
                logger.warning(f"[lp-trader] Error processing pool {pool_address[:10]}: {e}")

        # Rebalance evaluation — check active positions against recommended ranges
        for pos in list(self.engine.portfolio.positions):
            if pos.status not in ("active", "out_of_range"):
                continue
            try:
                recommendation = self.range_calc.compute_range(
                    current_tick=pos.current_tick,
                    fee_tier=pos.fee_tier,
                    regime_macro=macro,
                    vol_regime=vol_regime,
                    realized_vol_1d=realized_vol,
                    ema_trend_score=ema_trend,
                    confidence=confidence,
                )
                action = self.rebalance_engine.evaluate(pos, recommendation)
                if action and recommendation:
                    # Close old position
                    net_pnl = self.engine.close_position(pos.pool_address)
                    # Open new at recommended range
                    safe_ratio = pos.current_price_ratio if pos.current_price_ratio > 0 else 1.0
                    new_pos = self.engine.open_position(
                        pool_address=pos.pool_address,
                        token0_symbol=pos.token0_symbol,
                        token1_symbol=pos.token1_symbol,
                        fee_tier=pos.fee_tier,
                        tick_lower=recommendation.tick_lower,
                        tick_upper=recommendation.tick_upper,
                        size_pct=recommendation.size_pct,
                        current_tick=pos.current_tick,
                        current_price_ratio=safe_ratio,
                    )
                    self.rebalance_engine.record_rebalance(pos.position_id)
                    # Log rebalance event to wp_lp_events
                    self._store_rebalance_event(action, net_pnl)
                    logger.info(f"[lp-auto] Rebalanced {action['pair']}: {action['reason']}, net PnL ${net_pnl:.2f}")
                    alerts.append({
                        "type": "rebalance",
                        "pair": action["pair"],
                        "message": f"Rebalanced: {action['reason']}, old={action['old_range']}, new={action['new_range']}, net ${net_pnl:.2f}",
                    })
            except Exception as e:
                logger.warning(f"[lp-trader] Rebalance eval error for {pos.position_id}: {e}")

        # Check alerts on all active positions
        active_positions = [
            p for p in self.engine.portfolio.positions if p.status in ("active", "out_of_range")
        ]
        alerts.extend(self.monitor.check_alerts(active_positions))

        # IL hedging — open/adjust/close perp hedges for positions with IL > 3%
        hedge_alerts = self._check_il_hedges(active_positions)
        alerts.extend(hedge_alerts)

        # Fee harvesting — evaluate and auto-harvest for active positions
        for pos in self.engine.portfolio.positions:
            if pos.status == "active":
                harvest = self.fee_manager.evaluate(pos, regime_macro=macro)
                if harvest.should_harvest:
                    result = self.fee_manager.execute_paper_harvest(pos)
                    action = "compound" if harvest.compound else "sweep"
                    alerts.append({
                        "type": "fee_harvest",
                        "pair": f"{pos.token0_symbol}/{pos.token1_symbol}",
                        "message": f"Harvested ${result['harvested_usd']:.2f} fees ({harvest.reason}, {action})",
                    })

        # Check fee milestone
        milestone_msg = self.fee_manager.check_milestone(self.engine.portfolio.total_fees_earned)
        if milestone_msg:
            alerts.append({"type": "fee_milestone", "message": milestone_msg})

        # Store snapshot
        self._store_snapshot()

        return {
            "alerts": alerts,
            "pools_checked": pools_checked,
            "positions": len(active_positions),
            "equity": round(self.engine.portfolio.equity, 2),
            "scanner_candidates": len(self.pool_scanner.get_candidates()),
        }

    def _check_il_hedges(self, active_positions: list) -> list[dict]:
        """Check IL on active LP positions and manage perp hedges (paper mode).

        - Opens a short hedge when IL exceeds 3% of position value
        - Adjusts hedge size if IL changed by more than 20% since last adjustment
        - Closes hedge when the LP position is no longer active
        """
        alerts: list[dict] = []
        IL_THRESHOLD_PCT = 3.0
        REBALANCE_THRESHOLD = 0.20  # Adjust hedge if IL changed by >20%

        active_ids = {p.position_id for p in active_positions}

        # Close hedges for positions that are no longer active
        closed_ids = [pid for pid in self._il_hedges if pid not in active_ids]
        for pid in closed_ids:
            hedge = self._il_hedges.pop(pid)
            logger.info(f"[lp-hedge] Closed IL hedge for {pid}: size=${hedge['hedge_size']:.2f}")
            alerts.append({
                "type": "il_hedge",
                "message": f"IL hedge CLOSED (position exited): hedge was ${hedge['hedge_size']:.2f}",
            })

        for pos in active_positions:
            il_pct = abs(getattr(pos, "il_pct", 0.0))
            il_usd = abs(getattr(pos, "il_usd", 0.0))
            pair = f"{pos.token0_symbol}/{pos.token1_symbol}"

            if il_pct < IL_THRESHOLD_PCT:
                # If IL dropped below threshold and we have a hedge, close it
                if pos.position_id in self._il_hedges:
                    hedge = self._il_hedges.pop(pos.position_id)
                    logger.info(f"[lp-hedge] Closed IL hedge for {pair}: IL dropped to {il_pct:.1f}%")
                    alerts.append({
                        "type": "il_hedge",
                        "message": f"IL hedge CLOSED for {pair}: IL recovered to {il_pct:.1f}%",
                    })
                continue

            # IL exceeds threshold — open or adjust hedge
            existing_hedge = self._il_hedges.get(pos.position_id)

            if existing_hedge is None:
                # Open new hedge — size equals the IL in USD
                self._il_hedges[pos.position_id] = {
                    "hedge_size": il_usd,
                    "hedge_entry": getattr(pos, "current_price_ratio", 0.0),
                    "last_adjusted": datetime.now(timezone.utc),
                    "pair": pair,
                }
                logger.info(f"[lp-hedge] Opened IL hedge for {pair}: ${il_usd:.2f} short (IL={il_pct:.1f}%)")
                alerts.append({
                    "type": "il_hedge",
                    "message": f"IL hedge OPENED for {pair}: ${il_usd:.2f} short to offset {il_pct:.1f}% IL",
                })
            else:
                # Check if hedge needs rebalancing
                old_size = existing_hedge["hedge_size"]
                if old_size > 0 and abs(il_usd - old_size) / old_size > REBALANCE_THRESHOLD:
                    existing_hedge["hedge_size"] = il_usd
                    existing_hedge["last_adjusted"] = datetime.now(timezone.utc)
                    logger.info(f"[lp-hedge] Adjusted IL hedge for {pair}: ${old_size:.2f} -> ${il_usd:.2f}")
                    alerts.append({
                        "type": "il_hedge",
                        "message": f"IL hedge ADJUSTED for {pair}: ${old_size:.2f} -> ${il_usd:.2f} (IL={il_pct:.1f}%)",
                    })

        return alerts

    def _update_watch_list(self, candidates) -> None:
        """Update watched pools based on scanner results."""
        # Config pools always stay watched (user overrides)
        scanner_pools = [c.address for c in candidates[:MAX_POSITIONS]]

        # Merge: config pools + top candidates (deduped, order preserved)
        all_pools = list(dict.fromkeys(self._config_pools + scanner_pools))
        self._watched_pools = all_pools
        logger.info(f"[lp-auto] Watch list updated: {len(self._config_pools)} config + {len(scanner_pools)} scanner = {len(all_pools)} total")

    def _should_exit_pool(self, position) -> tuple[bool, str]:
        """Decide if we should exit a position and rotate capital elsewhere."""
        candidates = self.pool_scanner.get_candidates()
        if not candidates:
            return False, ""

        # Get this pool's current projected APR from scanner
        current_candidate = next(
            (c for c in candidates if c.address.lower() == position.pool_address.lower()),
            None,
        )

        # If pool dropped out of top candidates entirely
        if not current_candidate:
            # Only exit if we've held for at least 2 hours (avoid churn)
            hold_hours = (datetime.now(timezone.utc) - position.opened_at).total_seconds() / 3600
            if hold_hours >= 2:
                return True, "pool dropped from top candidates"
            return False, ""

        # If APR is declining
        apr_trend = self.pool_scanner.get_apr_trend(position.pool_address)
        if apr_trend == "declining":
            # Check if there's a significantly better alternative
            best = candidates[0]
            if best.address.lower() != position.pool_address.lower() and best.fee_apr > current_candidate.fee_apr * 1.5:
                return True, f"APR declining, better alternative: {best.name} ({best.fee_apr:.1f}% vs {current_candidate.fee_apr:.1f}%)"

        # If IL is eating all the fees
        if position.il_usd > position.fees_earned_usd * 2 and position.fees_earned_usd > 0:
            return True, f"IL (${position.il_usd:.2f}) exceeding 2x fees (${position.fees_earned_usd:.2f})"

        return False, ""

    def _store_rotation_event(self, position, reason: str, net_pnl: float) -> None:
        """Store rotation exit event to wp_lp_events."""
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_lp_events").insert({
                "event_type": "rotation_exit",
                "details": {
                    "position_id": position.position_id,
                    "pool": position.pool_address,
                    "pair": f"{position.token0_symbol}/{position.token1_symbol}",
                    "reason": reason,
                    "fees_earned": round(position.fees_earned_usd, 2),
                    "il_usd": round(position.il_usd, 2),
                    "net_pnl": round(net_pnl, 2),
                    "hold_hours": round((datetime.now(timezone.utc) - position.opened_at).total_seconds() / 3600, 1),
                },
            }).execute()
        except Exception as e:
            logger.warning(f"[lp-trader] Failed to store rotation event: {e}")

    def _store_rebalance_event(self, action: dict, net_pnl: float) -> None:
        """Store rebalance event to wp_lp_events."""
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_lp_events").insert({
                "event_type": "rebalance",
                "details": {
                    "position_id": action["position_id"],
                    "pool": action["pool_address"],
                    "pair": action["pair"],
                    "reason": action["reason"],
                    "old_range": action["old_range"],
                    "new_range": action["new_range"],
                    "il_pct": action["il_pct"],
                    "out_of_range_ticks": action["out_of_range_ticks"],
                    "net_pnl": round(net_pnl, 2),
                },
            }).execute()
        except Exception as e:
            logger.warning(f"[lp-trader] Failed to store rebalance event: {e}")

    def _store_snapshot(self) -> None:
        """Persist portfolio state to wp_lp_snapshots."""
        try:
            self.engine.store_snapshot()
        except Exception as e:
            logger.warning(f"[lp-trader] Failed to store snapshot: {e}")

    def get_status(self) -> dict:
        """Return current status for API endpoint."""
        candidates = self.pool_scanner.get_candidates()
        return {
            "enabled": self._enabled,
            "paper_mode": True,
            "equity": round(self.engine.portfolio.equity, 2),
            "positions": len(self.engine.portfolio.positions),
            "max_positions": MAX_POSITIONS,
            "total_fees": round(self.engine.portfolio.total_fees_earned, 2),
            "total_il": round(self.engine.portfolio.total_il, 2),
            "realized_pnl": round(self.engine.portfolio.realized_pnl, 2),
            "watched_pools": len(self._watched_pools),
            "active_il_hedges": len(self._il_hedges),
            "total_hedge_usd": round(sum(h["hedge_size"] for h in self._il_hedges.values()), 2),
            "scanner_candidates": len(candidates),
            "top_pools": [
                {"name": c.name, "apr": c.fee_apr, "score": c.score}
                for c in candidates[:5]
            ],
        }

    def add_pool(self, pool_address: str) -> None:
        """Add a pool to the watch list."""
        if pool_address not in self._watched_pools:
            self._watched_pools.append(pool_address)

    def remove_pool(self, pool_address: str) -> None:
        """Remove a pool from the watch list."""
        self._watched_pools = [p for p in self._watched_pools if p != pool_address]
