"""Paper LP Engine — simulates Uniswap V3 LP positions without on-chain transactions.

Mirrors PaperTradingEngine pattern: portfolio tracking, position lifecycle, DB persistence.
Fee accrual simulated from pool volume/TVL data. IL computed from price ratio changes.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PaperLPPosition:
    """A simulated Uniswap V3 LP position."""
    position_id: str              # unique ID (e.g., "paper-lp-{pool}-{timestamp}")
    pool_address: str
    token0_symbol: str
    token1_symbol: str
    fee_tier: int                 # 500, 3000, 10000
    tick_lower: int
    tick_upper: int
    liquidity_usd: float          # simulated USD value of liquidity provided
    entry_price_ratio: float      # token0/token1 price at entry
    current_price_ratio: float
    fees_earned_usd: float = 0.0
    il_pct: float = 0.0           # current impermanent loss %
    il_usd: float = 0.0
    status: str = "active"        # active, closed, out_of_range
    out_of_range_ticks: int = 0
    current_tick: int = 0
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PaperLPPortfolio:
    """Portfolio state for paper LP positions."""
    starting_equity: float = 25000.0
    equity: float = 25000.0
    free_collateral: float = 25000.0
    total_fees_earned: float = 0.0
    total_il: float = 0.0
    realized_pnl: float = 0.0     # fees - IL on closed positions
    positions: list[PaperLPPosition] = field(default_factory=list)
    closed_positions: int = 0


class PaperLPEngine:
    """Manages simulated LP positions. Mirrors PaperTradingEngine."""

    def __init__(self, starting_equity: float = 25000.0, persist: bool = True):
        self.persist = persist
        self.portfolio = PaperLPPortfolio(
            starting_equity=starting_equity,
            equity=starting_equity,
            free_collateral=starting_equity,
        )

    def open_position(
        self,
        pool_address: str,
        token0_symbol: str,
        token1_symbol: str,
        fee_tier: int,
        tick_lower: int,
        tick_upper: int,
        size_pct: float,
        current_tick: int,
        current_price_ratio: float,
    ) -> Optional[PaperLPPosition]:
        """Open a new paper LP position."""
        # Check if already have position in this pool
        existing = [p for p in self.portfolio.positions if p.pool_address == pool_address and p.status == "active"]
        if existing:
            logger.warning(f"Already have LP position in pool {pool_address}")
            return None

        size_usd = self.portfolio.equity * (min(size_pct, 30) / 100.0)
        if size_usd > self.portfolio.free_collateral:
            logger.warning(f"Insufficient collateral for LP: need ${size_usd:.2f}, have ${self.portfolio.free_collateral:.2f}")
            return None

        # Check if current tick is within range
        if not (tick_lower <= current_tick <= tick_upper):
            logger.warning(f"Current tick {current_tick} outside range [{tick_lower}, {tick_upper}]")
            return None

        timestamp = datetime.now(timezone.utc)
        position = PaperLPPosition(
            position_id=f"paper-lp-{pool_address[:8]}-{int(timestamp.timestamp())}",
            pool_address=pool_address,
            token0_symbol=token0_symbol,
            token1_symbol=token1_symbol,
            fee_tier=fee_tier,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
            liquidity_usd=size_usd,
            entry_price_ratio=current_price_ratio,
            current_price_ratio=current_price_ratio,
            current_tick=current_tick,
            opened_at=timestamp,
        )

        self.portfolio.positions.append(position)
        self.portfolio.free_collateral -= size_usd
        logger.info(f"Opened paper LP {token0_symbol}/{token1_symbol} {fee_tier/10000:.2f}% @ ticks [{tick_lower}, {tick_upper}], size ${size_usd:.0f}")
        return position

    def update_position(
        self,
        pool_address: str,
        current_tick: int,
        current_price_ratio: float,
        pool_volume_24h: float,
        pool_tvl: float,
    ) -> None:
        """Update position state: tick, fees, IL. Called every tick."""
        for pos in self.portfolio.positions:
            if pos.pool_address != pool_address or pos.status != "active":
                continue

            pos.current_tick = current_tick
            pos.current_price_ratio = current_price_ratio

            # Check if in range
            in_range = pos.tick_lower <= current_tick <= pos.tick_upper
            if in_range:
                if pos.status == "out_of_range":
                    pos.status = "active"
                pos.out_of_range_ticks = 0

                # Simulate fee accrual (only when in range)
                # Fee per tick = (position_liquidity / total_tvl) * daily_fees / (24*12)
                # 5-min tick = 1/288th of daily
                if pool_tvl > 0:
                    daily_fees = pool_volume_24h * (pos.fee_tier / 1_000_000)
                    position_share = pos.liquidity_usd / pool_tvl
                    fee_per_tick = daily_fees * position_share / 288  # 288 five-min ticks per day
                    pos.fees_earned_usd += fee_per_tick
            else:
                pos.out_of_range_ticks += 1
                if pos.out_of_range_ticks >= 3:
                    pos.status = "out_of_range"

            # Compute IL
            pos.il_pct = self._compute_il(pos.entry_price_ratio, current_price_ratio)
            pos.il_usd = pos.liquidity_usd * abs(pos.il_pct) / 100

        # Recalculate portfolio
        self._recalculate()

    @staticmethod
    def _compute_il(entry_ratio: float, current_ratio: float) -> float:
        """Impermanent loss formula: 2*sqrt(r)/(1+r) - 1 where r = current/entry."""
        if entry_ratio <= 0:
            return 0.0
        r = current_ratio / entry_ratio
        if r <= 0:
            return 0.0
        il = 2 * math.sqrt(r) / (1 + r) - 1
        return round(il * 100, 4)  # as percentage (negative = loss)

    def close_position(self, pool_address: str) -> float:
        """Close LP position. Returns net P&L (fees - IL)."""
        pos = None
        idx = -1
        for i, p in enumerate(self.portfolio.positions):
            if p.pool_address == pool_address and p.status in ("active", "out_of_range"):
                pos = p
                idx = i
                break

        if pos is None:
            return 0.0

        net_pnl = pos.fees_earned_usd - pos.il_usd
        self.portfolio.realized_pnl += net_pnl
        self.portfolio.total_fees_earned += pos.fees_earned_usd
        self.portfolio.total_il += pos.il_usd
        self.portfolio.free_collateral += pos.liquidity_usd + net_pnl
        self.portfolio.closed_positions += 1

        pos.status = "closed"
        self.portfolio.positions.pop(idx)

        if self.persist:
            self._store_closed_position(pos, net_pnl)

        logger.info(f"Closed paper LP {pos.token0_symbol}/{pos.token1_symbol}: fees ${pos.fees_earned_usd:.2f}, IL ${pos.il_usd:.2f}, net ${net_pnl:.2f}")
        return net_pnl

    def _recalculate(self) -> None:
        """Recalculate portfolio equity from positions."""
        total_value = sum(p.liquidity_usd + p.fees_earned_usd - p.il_usd for p in self.portfolio.positions if p.status != "closed")
        self.portfolio.equity = self.portfolio.free_collateral + total_value

    def _store_closed_position(self, pos: PaperLPPosition, net_pnl: float) -> None:
        """Store closed LP position to wp_lp_events."""
        if not self.persist:
            return
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_lp_events").insert({
                "event_type": "closed",
                "details": {
                    "position_id": pos.position_id,
                    "pool": pos.pool_address,
                    "pair": f"{pos.token0_symbol}/{pos.token1_symbol}",
                    "fees_earned": round(pos.fees_earned_usd, 2),
                    "il_usd": round(pos.il_usd, 2),
                    "net_pnl": round(net_pnl, 2),
                    "hold_minutes": (datetime.now(timezone.utc) - pos.opened_at).total_seconds() / 60,
                },
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to store LP close event: {e}")

    def take_snapshot(self) -> dict:
        """Generate a portfolio snapshot dict for Supabase storage."""
        positions_data = [
            {
                "position_id": p.position_id,
                "pool": p.pool_address,
                "pair": f"{p.token0_symbol}/{p.token1_symbol}",
                "liquidity_usd": round(p.liquidity_usd, 2),
                "fees": round(p.fees_earned_usd, 2),
                "il_pct": p.il_pct,
                "il_usd": round(p.il_usd, 2),
                "status": p.status,
                "ticks": [p.tick_lower, p.tick_upper],
                "current_tick": p.current_tick,
                "entry_price_ratio": round(p.entry_price_ratio, 6),
                "current_price_ratio": round(p.current_price_ratio, 6),
            }
            for p in self.portfolio.positions
        ]

        return {
            "total_value_usd": round(self.portfolio.equity, 2),
            "total_fees_usd": round(self.portfolio.total_fees_earned, 2),
            "total_il_usd": round(self.portfolio.total_il, 2),
            "positions": positions_data,
        }

    def store_snapshot(self) -> dict:
        """Persist portfolio state to wp_lp_snapshots."""
        if not self.persist:
            return {}
        try:
            from wolfpack.db import get_db
            db = get_db()
            snapshot = self.take_snapshot()
            result = db.table("wp_lp_snapshots").insert(snapshot).execute()
            return result.data[0] if result.data else snapshot
        except Exception as e:
            logger.warning(f"Failed to store LP snapshot: {e}")
            return {}

    def restore_from_snapshot(self) -> None:
        """Restore LP portfolio from latest Supabase snapshot."""
        if not self.persist:
            return
        try:
            from wolfpack.db import get_db
            db = get_db()
            result = (
                db.table("wp_lp_snapshots")
                .select("*")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                snap = result.data[0]
                p = self.portfolio
                snap_equity = snap.get("total_value_usd", self.portfolio.starting_equity)
                p.equity = snap_equity
                p.total_fees_earned = snap.get("total_fees_usd", 0.0)
                p.total_il = snap.get("total_il_usd", 0.0)
                p.free_collateral = snap_equity  # reset for now, will be recalculated
                
                # Restore positions from snapshot
                for pos_data in snap.get("positions", []):
                    pos = PaperLPPosition(
                        position_id=pos_data.get("position_id", ""),
                        pool_address=pos_data.get("pool", ""),
                        token0_symbol=pos_data.get("pair", "").split("/")[0],
                        token1_symbol=pos_data.get("pair", "").split("/")[1] if "/" in pos_data.get("pair", "") else "",
                        fee_tier=3000,  # default, not stored
                        tick_lower=pos_data.get("ticks", [0, 0])[0],
                        tick_upper=pos_data.get("ticks", [0, 0])[1],
                        liquidity_usd=pos_data.get("liquidity_usd", 0.0),
                        entry_price_ratio=pos_data.get("entry_price_ratio", 1.0),
                        current_price_ratio=pos_data.get("current_price_ratio", 1.0),
                        fees_earned_usd=pos_data.get("fees", 0.0),
                        il_pct=pos_data.get("il_pct", 0.0),
                        il_usd=pos_data.get("il_usd", 0.0),
                        status=pos_data.get("status", "active"),
                        current_tick=pos_data.get("current_tick", 0),
                    )
                    p.positions.append(pos)
                
                # Recalculate portfolio state
                self._recalculate()
                logger.info(f"Restored LP portfolio from snapshot: ${p.equity:.2f} equity, {len(p.positions)} positions")
        except Exception as e:
            logger.warning(f"Failed to restore LP portfolio: {e}")
