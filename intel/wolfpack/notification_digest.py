"""Notification digest — periodic P&L report combining perp + LP into one TG message.

Replaces event-by-event noise with a clean 4-hour profit report.
Queries DB directly for P&L numbers across multiple time windows.
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# LP alert types for grouping
LP_TYPES = frozenset({
    "rotation_exit", "rebalance", "fee_harvest", "fee_milestone",
    "out_of_range", "lp_open", "lp_close", "lp_alert",
})

# Perp alert types
PERP_TYPES = frozenset({
    "trade_open", "trade_close", "stop_triggered", "stop_adjusted",
})

# Report interval in minutes (4 hours)
REPORT_INTERVAL_MINUTES = 240


class NotificationDigest:
    """Sends periodic P&L reports via Telegram, driven by DB queries."""

    def __init__(self):
        self._buffer: list[dict] = []
        self._last_flush: datetime = datetime.now(timezone.utc)
        self._mode: str = "hourly"  # hourly = periodic reports, individual, disabled
        self._interval_minutes: int = REPORT_INTERVAL_MINUTES
        self._portfolio_snapshot: dict | None = None

    def set_mode(self, mode: str) -> None:
        """Set digest mode: individual, hourly, daily, disabled."""
        if mode in ("individual", "hourly", "daily", "disabled"):
            self._mode = mode
            logger.info(f"[digest] Notification mode set to: {mode}")

    def set_interval(self, minutes: int) -> None:
        """Set custom digest interval in minutes."""
        self._interval_minutes = max(5, min(minutes, 1440))

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def interval_minutes(self) -> int:
        return self._interval_minutes

    def set_portfolio_snapshot(self, perp: dict | None = None, lp: dict | None = None) -> None:
        """Set current portfolio state for inclusion in the digest."""
        self._portfolio_snapshot = {"perp": perp, "lp": lp}

    def add(self, notification: dict) -> None:
        """Buffer a notification. Individual mode sends immediately, otherwise stored for report context."""
        notification.setdefault("timestamp", datetime.now(timezone.utc))
        self._buffer.append(notification)

    async def maybe_flush(self) -> bool:
        """Check if it's time to send the periodic P&L report."""
        if self._mode == "disabled":
            return False

        if self._mode == "individual":
            for notif in self._buffer:
                try:
                    from wolfpack.notifications import send_telegram
                    details = notif.get("details", "")
                    if details:
                        await send_telegram(details)
                except Exception:
                    pass
            self._buffer.clear()
            self._last_flush = datetime.now(timezone.utc)
            return True

        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_flush).total_seconds() / 60
        if elapsed < self._interval_minutes:
            return False

        await self._send_pnl_report()
        return True

    async def _send_pnl_report(self) -> None:
        """Send a unified P&L report combining perp + LP across time windows."""
        try:
            from wolfpack.db import get_db
            from wolfpack.notifications import send_telegram

            db = get_db()
            now = datetime.now(timezone.utc)

            # ── PERP P&L from wp_trade_history ──
            perp_windows = {}
            for label, hours in [("4H", 4), ("8H", 8), ("24H", 24)]:
                result = db.rpc("", {}).execute()  # dummy — use raw SQL below
                pass

            # Query perp P&L for each window via direct select
            perp_4h = _query_perp_pnl(db, 4)
            perp_8h = _query_perp_pnl(db, 8)
            perp_24h = _query_perp_pnl(db, 24)

            # ── LP P&L from wp_lp_snapshots ──
            lp_now = self._portfolio_snapshot.get("lp") if self._portfolio_snapshot else None
            lp_4h = _query_lp_snapshot(db, 4)
            lp_8h = _query_lp_snapshot(db, 8)
            lp_24h = _query_lp_snapshot(db, 24)

            # Current LP state
            lp_equity = lp_now.get("equity", 0) if lp_now else 0
            lp_fees = lp_now.get("total_fees", 0) if lp_now else 0
            lp_il = lp_now.get("total_il", 0) if lp_now else 0
            lp_positions = len(lp_now.get("positions", [])) if lp_now else 0

            # Compute LP deltas (fees gained minus IL gained in each window)
            lp_delta_4h = (lp_fees - (lp_4h.get("fees", lp_fees))) - (lp_il - (lp_4h.get("il", lp_il)))
            lp_delta_8h = (lp_fees - (lp_8h.get("fees", lp_fees))) - (lp_il - (lp_8h.get("il", lp_il)))
            lp_delta_24h = (lp_fees - (lp_24h.get("fees", lp_fees))) - (lp_il - (lp_24h.get("il", lp_il)))

            # Current perp state from snapshot
            perp_snap = (self._portfolio_snapshot or {}).get("perp")
            perp_equity = perp_snap.get("equity", 0) if perp_snap else 0
            perp_positions = len(perp_snap.get("positions", [])) if perp_snap else 0
            perp_unrealized = perp_snap.get("unrealized_pnl", 0) if perp_snap else 0

            # ── BUILD MESSAGE ──
            lines: list[str] = []
            lines.append("<b>WolfPack P&L Report</b>")
            lines.append("")

            # Combined P&L table
            lines.append("<b>Profit (New This Period)</b>")
            lines.append("<pre>")
            lines.append(f"{'':8s} {'4H':>10s} {'8H':>10s} {'24H':>10s}")
            lines.append(f"{'Perp':8s} {_fmt_compact(perp_4h['pnl']):>10s} {_fmt_compact(perp_8h['pnl']):>10s} {_fmt_compact(perp_24h['pnl']):>10s}")
            lines.append(f"{'LP':8s} {_fmt_compact(lp_delta_4h):>10s} {_fmt_compact(lp_delta_8h):>10s} {_fmt_compact(lp_delta_24h):>10s}")
            total_4h = perp_4h['pnl'] + lp_delta_4h
            total_8h = perp_8h['pnl'] + lp_delta_8h
            total_24h = perp_24h['pnl'] + lp_delta_24h
            lines.append(f"{'─'*40}")
            lines.append(f"{'Total':8s} {_fmt_compact(total_4h):>10s} {_fmt_compact(total_8h):>10s} {_fmt_compact(total_24h):>10s}")
            lines.append("</pre>")

            # Perp detail
            lines.append("")
            lines.append(f"<b>Perp</b>: ${perp_equity:,.0f} equity | {perp_positions} open | {_fmt_pnl(perp_unrealized)} unreal")
            if perp_4h['trades'] > 0:
                lines.append(f"  4H: {perp_4h['trades']} trades ({perp_4h['wins']}W/{perp_4h['losses']}L)")

            # LP detail
            lines.append(f"<b>LP</b>: ${lp_equity:,.0f} equity | {lp_positions} positions | fees ${lp_fees:,.2f} | IL ${lp_il:,.2f}")

            msg = "\n".join(lines)
            await send_telegram(msg)
            logger.info(f"[digest] Sent P&L report (4H perp: {_fmt_compact(perp_4h['pnl'])}, LP: {_fmt_compact(lp_delta_4h)})")

        except Exception as e:
            logger.warning(f"[digest] Failed to send P&L report: {e}")
            # Fallback: try old-style digest with buffered events
            try:
                await self._send_fallback_digest()
            except Exception:
                pass

        self._buffer.clear()
        self._last_flush = datetime.now(timezone.utc)
        self._portfolio_snapshot = None

    async def _send_fallback_digest(self) -> None:
        """Minimal fallback if DB query fails — just send buffered event count."""
        if not self._buffer:
            return
        from wolfpack.notifications import send_telegram
        perp_count = sum(1 for n in self._buffer if n.get("type") in PERP_TYPES)
        lp_count = sum(1 for n in self._buffer if n.get("type") in LP_TYPES)
        closes = [n for n in self._buffer if n.get("type") == "trade_close"]
        perp_pnl = sum(n.get("pnl", 0) for n in closes)
        msg = f"<b>WolfPack</b>: {perp_count} perp events, {lp_count} LP events"
        if closes:
            msg += f"\nPerp P&L: {_fmt_pnl(perp_pnl)} ({len(closes)} closed)"
        await send_telegram(msg)

    async def force_flush(self) -> None:
        """Force send report now regardless of interval."""
        await self._send_pnl_report()


def _query_perp_pnl(db, hours: int) -> dict:
    """Query perp trading P&L for the last N hours."""
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        result = db.table("wp_trade_history").select("pnl_usd").gte("closed_at", cutoff).execute()
        rows = result.data or []
        pnls = [float(r["pnl_usd"]) for r in rows if r.get("pnl_usd") is not None]
        return {
            "pnl": sum(pnls),
            "trades": len(pnls),
            "wins": sum(1 for p in pnls if p > 0),
            "losses": sum(1 for p in pnls if p < 0),
        }
    except Exception as e:
        logger.warning(f"[digest] Perp query failed ({hours}h): {e}")
        return {"pnl": 0, "trades": 0, "wins": 0, "losses": 0}


def _query_lp_snapshot(db, hours: int) -> dict:
    """Get LP snapshot from N hours ago for delta calculation."""
    try:
        from datetime import timedelta
        target = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        result = (
            db.table("wp_lp_snapshots")
            .select("total_fees_usd, total_il_usd, total_value_usd")
            .lte("created_at", target)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            row = result.data[0]
            return {
                "fees": float(row.get("total_fees_usd", 0)),
                "il": float(row.get("total_il_usd", 0)),
                "equity": float(row.get("total_value_usd", 0)),
            }
    except Exception as e:
        logger.warning(f"[digest] LP snapshot query failed ({hours}h): {e}")
    return {"fees": 0, "il": 0, "equity": 0}


def _fmt_pnl(value: float) -> str:
    """Format a P&L value with sign and dollar."""
    if value >= 0:
        return f"+${value:,.2f}"
    return f"-${abs(value):,.2f}"


def _fmt_compact(value: float) -> str:
    """Compact P&L format for table columns."""
    if value >= 0:
        return f"+${value:,.0f}"
    return f"-${abs(value):,.0f}"


# Singleton
_digest: NotificationDigest | None = None

def get_digest() -> NotificationDigest:
    global _digest
    if _digest is None:
        _digest = NotificationDigest()
    return _digest
