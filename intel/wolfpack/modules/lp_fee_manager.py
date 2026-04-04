"""LP Fee Manager — auto-harvest fee decisions for paper LP positions."""

import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

FEE_HARVEST_THRESHOLD_USD = 10.0      # minimum fees to justify harvest
FEE_HARVEST_INTERVAL_HOURS = 24       # max time between harvests
FEE_MILESTONE_INCREMENT = 100.0       # notify every $100 milestone


@dataclass
class FeeHarvestDecision:
    should_harvest: bool
    reason: str                        # "threshold", "scheduled", "pre_rebalance"
    fees_usd: float
    compound: bool                     # True = add back to position, False = sweep


class LPFeeManager:
    def __init__(self, threshold_usd: float = FEE_HARVEST_THRESHOLD_USD, interval_hours: int = FEE_HARVEST_INTERVAL_HOURS):
        self.threshold_usd = threshold_usd
        self.interval_hours = interval_hours
        self._last_milestone: float = 0.0   # last notified milestone amount

    def evaluate(self, position, regime_macro: str = "RANGING") -> FeeHarvestDecision:
        """Decide whether to harvest fees from a position.

        Args:
            position: PaperLPPosition (has fees_earned_usd, status, opened_at, or last_fee_harvest)
            regime_macro: "TRENDING", "RANGING", "VOLATILE"

        Harvest if:
        1. fees >= threshold (gas-justified)
        2. Time since last harvest > interval_hours

        Compound decision:
        - RANGING + in range -> compound (add to position)
        - TRENDING or out of range -> sweep (take profit)
        """
        fees = position.fees_earned_usd

        # Check threshold
        if fees >= self.threshold_usd:
            compound = regime_macro == "RANGING" and position.status == "active"
            return FeeHarvestDecision(
                should_harvest=True,
                reason="threshold",
                fees_usd=fees,
                compound=compound,
            )

        # Check time interval
        last_harvest = getattr(position, 'last_fee_harvest_at', None) or position.opened_at
        if isinstance(last_harvest, str):
            try:
                last_harvest = datetime.fromisoformat(last_harvest)
            except Exception:
                last_harvest = position.opened_at

        now = datetime.now(timezone.utc)
        if hasattr(last_harvest, 'tzinfo') and last_harvest.tzinfo is None:
            last_harvest = last_harvest.replace(tzinfo=timezone.utc)

        hours_since = (now - last_harvest).total_seconds() / 3600
        if hours_since >= self.interval_hours and fees > 0:
            compound = regime_macro == "RANGING" and position.status == "active"
            return FeeHarvestDecision(
                should_harvest=True,
                reason="scheduled",
                fees_usd=fees,
                compound=compound,
            )

        return FeeHarvestDecision(should_harvest=False, reason="", fees_usd=fees, compound=False)

    def execute_paper_harvest(self, position) -> dict:
        """Paper mode: record fee harvest. Reset position's pending fees."""
        harvested = position.fees_earned_usd
        position.fees_earned_usd = 0.0
        if hasattr(position, 'last_fee_harvest_at'):
            position.last_fee_harvest_at = datetime.now(timezone.utc)

        # Log to DB
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_lp_events").insert({
                "event_type": "fee_harvest",
                "details": {
                    "position_id": position.position_id,
                    "pool": position.pool_address,
                    "pair": f"{position.token0_symbol}/{position.token1_symbol}",
                    "fees_harvested_usd": round(harvested, 2),
                },
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to store fee harvest event: {e}")

        logger.info(f"[lp-fees] Harvested ${harvested:.2f} from {position.token0_symbol}/{position.token1_symbol}")
        return {"harvested_usd": round(harvested, 2), "position_id": position.position_id}

    def check_milestone(self, total_fees: float) -> str | None:
        """Check if total fees crossed a milestone. Returns message or None."""
        milestone = int(total_fees / FEE_MILESTONE_INCREMENT) * FEE_MILESTONE_INCREMENT
        if milestone > self._last_milestone and milestone > 0:
            self._last_milestone = milestone
            return f"LP FEE MILESTONE: Total fees earned ${milestone:.0f}"
        return None
