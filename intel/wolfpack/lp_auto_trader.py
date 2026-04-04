"""LP AutoTrader — orchestrates paper LP engine + position monitoring.

Follows the AutoTrader pattern: singleton via api.py, restore from snapshot,
process_tick() called from the main intelligence cycle.
"""

import logging
from typing import Any, Optional

from wolfpack.config import settings

logger = logging.getLogger(__name__)


class LPAutoTrader:
    """Autonomous LP position manager with paper trading engine."""

    def __init__(self) -> None:
        from wolfpack.lp_paper_engine import PaperLPEngine
        from wolfpack.modules.lp_monitor import LPPositionMonitor
        from wolfpack.modules.lp_range_calculator import LPRangeCalculator

        self._enabled = settings.lp_auto_enabled
        self.engine = PaperLPEngine(starting_equity=settings.lp_starting_equity)
        self.monitor = LPPositionMonitor()
        self.range_calc = LPRangeCalculator()
        self._restored = False
        self._watched_pools: list[str] = []

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
        2. For each watched pool: fetch pool state via monitor
        3. Update paper engine with current ticks + prices
        4. Check for alerts (out-of-range, IL warnings)
        5. Store snapshot
        6. Return summary dict
        """
        self.restore_from_snapshot()

        if not self._watched_pools:
            return {"alerts": [], "pools_checked": 0, "positions": 0}

        alerts: list[dict] = []
        pools_checked = 0

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

        for pool_address in self._watched_pools:
            try:
                state = await self.monitor.fetch_pool_state(pool_address)
                if state is None:
                    continue

                pools_checked += 1

                # Compute price ratio from sqrtPrice
                price_ratio = self.monitor.compute_price_ratio(state.sqrt_price)
                if price_ratio <= 0:
                    # Fallback: use USD prices if available
                    if state.token1_price_usd and state.token1_price_usd > 0:
                        price_ratio = state.token0_price_usd / state.token1_price_usd
                    else:
                        continue

                # Auto-open: if no existing position in this pool, compute range and open
                existing = [
                    p for p in self.engine.portfolio.positions
                    if p.pool_address == pool_address and p.status == "active"
                ]
                if not existing:
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

        # Check alerts on all active positions
        active_positions = [
            p for p in self.engine.portfolio.positions if p.status in ("active", "out_of_range")
        ]
        alerts = self.monitor.check_alerts(active_positions)

        # Store snapshot
        self._store_snapshot()

        return {
            "alerts": alerts,
            "pools_checked": pools_checked,
            "positions": len(active_positions),
            "equity": round(self.engine.portfolio.equity, 2),
        }

    def _store_snapshot(self) -> None:
        """Persist portfolio state to wp_lp_snapshots."""
        try:
            self.engine.store_snapshot()
        except Exception as e:
            logger.warning(f"[lp-trader] Failed to store snapshot: {e}")

    def get_status(self) -> dict:
        """Return current status for API endpoint."""
        return {
            "enabled": self._enabled,
            "paper_mode": True,
            "equity": round(self.engine.portfolio.equity, 2),
            "positions": len(self.engine.portfolio.positions),
            "total_fees": round(self.engine.portfolio.total_fees_earned, 2),
            "total_il": round(self.engine.portfolio.total_il, 2),
            "realized_pnl": round(self.engine.portfolio.realized_pnl, 2),
            "watched_pools": len(self._watched_pools),
        }

    def add_pool(self, pool_address: str) -> None:
        """Add a pool to the watch list."""
        if pool_address not in self._watched_pools:
            self._watched_pools.append(pool_address)

    def remove_pool(self, pool_address: str) -> None:
        """Remove a pool from the watch list."""
        self._watched_pools = [p for p in self._watched_pools if p != pool_address]
