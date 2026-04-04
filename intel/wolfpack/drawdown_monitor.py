"""Drawdown Monitor — Peak equity tracking and per-position drawdown detection.

Tracks portfolio high-water mark in DB (survives restarts) and monitors
per-position peak unrealized P&L. Generates emergency close signals when
a position gives back >40% of its peak profit (NoFx pattern).
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DrawdownMonitor:
    """Monitors portfolio and position-level drawdown from peaks."""

    def __init__(self) -> None:
        self._peak_cache: dict[str, float] = {}  # exchange_id -> peak_equity
        self._position_peaks: dict[str, float] = {}  # symbol -> peak_unrealized_pnl

    def update_peaks(self, exchange_id: str, current_equity: float) -> dict:
        """Called every tick. Updates peak if new high. Returns drawdown info.

        Args:
            exchange_id: Exchange identifier (e.g. "hyperliquid").
            current_equity: Current portfolio equity.

        Returns:
            Dict with peak_equity, current_equity, drawdown_pct.
        """
        # Load from DB if not cached
        if exchange_id not in self._peak_cache:
            self._load_from_db(exchange_id, current_equity)

        peak = self._peak_cache.get(exchange_id, current_equity)

        # If current > peak: update peak in DB and cache
        if current_equity > peak:
            peak = current_equity
            self._peak_cache[exchange_id] = peak
            self._save_to_db(exchange_id, peak, current_equity, 0.0)
        else:
            # Compute drawdown and update DB
            drawdown_pct = ((peak - current_equity) / peak * 100) if peak > 0 else 0.0
            self._save_to_db(exchange_id, peak, current_equity, drawdown_pct)

        drawdown_pct = ((peak - current_equity) / peak * 100) if peak > 0 else 0.0

        return {
            "peak_equity": round(peak, 2),
            "current_equity": round(current_equity, 2),
            "drawdown_pct": round(drawdown_pct, 4),
        }

    def update_position_peak(self, symbol: str, unrealized_pnl: float) -> None:
        """Track per-position peak unrealized P&L.

        Args:
            symbol: Asset symbol (e.g. "BTC").
            unrealized_pnl: Current unrealized P&L for the position.
        """
        current_peak = self._position_peaks.get(symbol, 0.0)
        if unrealized_pnl > current_peak:
            self._position_peaks[symbol] = unrealized_pnl

    def check_emergency_exits(self, positions: list) -> list:
        """NoFx pattern: if position was profitable (>5%) but drew down 40% from peak -> emergency close.

        Args:
            positions: List of position dicts with symbol, unrealized_pnl, size_usd.

        Returns:
            List of emergency close signal dicts.
        """
        exits = []
        for pos in positions:
            symbol = pos.get("symbol")
            peak_pnl = self._position_peaks.get(symbol, 0.0)
            current_pnl = pos.get("unrealized_pnl", 0.0)

            if peak_pnl <= 0:
                continue

            # Only trigger if position was meaningfully profitable
            size_usd = pos.get("size_usd", 0)
            if size_usd <= 0:
                continue
            peak_pnl_pct = (peak_pnl / size_usd) * 100

            if peak_pnl_pct < 5.0:
                continue

            # Check drawdown from peak
            drawdown_from_peak = ((peak_pnl - current_pnl) / peak_pnl) * 100
            if drawdown_from_peak >= 40.0:
                exits.append({
                    "symbol": symbol,
                    "action": "emergency_close",
                    "reason": (
                        f"Gave back {drawdown_from_peak:.1f}% of peak profit "
                        f"(peak: ${peak_pnl:.2f}, now: ${current_pnl:.2f})"
                    ),
                })

        return exits

    def clear_position_peak(self, symbol: str) -> None:
        """Call when position is closed to clean up tracking state."""
        self._position_peaks.pop(symbol, None)

    def get_position_peak(self, symbol: str) -> float:
        """Get the peak unrealized P&L for a position."""
        return self._position_peaks.get(symbol, 0.0)

    def _load_from_db(self, exchange_id: str, fallback_equity: float) -> None:
        """Load peak equity from wp_equity_highwater table."""
        try:
            from wolfpack.db import get_db
            db = get_db()
            result = (
                db.table("wp_equity_highwater")
                .select("peak_equity")
                .eq("exchange_id", exchange_id)
                .limit(1)
                .execute()
            )
            if result.data:
                self._peak_cache[exchange_id] = float(result.data[0]["peak_equity"])
                logger.info(f"[drawdown] Loaded peak equity for {exchange_id}: ${self._peak_cache[exchange_id]:.2f}")
            else:
                # First time — seed with current equity
                self._peak_cache[exchange_id] = fallback_equity
                self._save_to_db(exchange_id, fallback_equity, fallback_equity, 0.0)
                logger.info(f"[drawdown] Seeded peak equity for {exchange_id}: ${fallback_equity:.2f}")
        except Exception as e:
            logger.warning(f"[drawdown] Could not load peak from DB: {e}")
            self._peak_cache[exchange_id] = fallback_equity

    def _save_to_db(
        self,
        exchange_id: str,
        peak_equity: float,
        current_equity: float,
        drawdown_pct: float,
    ) -> None:
        """Upsert peak equity to wp_equity_highwater table."""
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_equity_highwater").upsert(
                {
                    "exchange_id": exchange_id,
                    "peak_equity": round(peak_equity, 2),
                    "peak_timestamp": datetime.now(timezone.utc).isoformat(),
                    "current_equity": round(current_equity, 2),
                    "current_drawdown_pct": round(drawdown_pct, 4),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="exchange_id",
            ).execute()
        except Exception as e:
            logger.warning(f"[drawdown] Could not save peak to DB: {e}")
