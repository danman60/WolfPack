"""Notification digest — periodic P&L report combining perp + LP into one TG message.

Sends a unified 4-hour report with P&L across 4H / 8H / 12H windows.
Queries DB directly — no buffering needed for the report itself.
"""

import logging
from datetime import datetime, timezone, timedelta
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

# Report interval (4 hours)
REPORT_INTERVAL_MINUTES = 240


class NotificationDigest:
    """Sends periodic P&L reports via Telegram, driven by DB queries."""

    def __init__(self):
        self._buffer: list[dict] = []
        self._last_flush: datetime = datetime.now(timezone.utc)
        self._mode: str = "hourly"
        self._interval_minutes: int = REPORT_INTERVAL_MINUTES
        self._portfolio_snapshot: dict | None = None

    def set_mode(self, mode: str) -> None:
        if mode in ("individual", "hourly", "daily", "disabled"):
            self._mode = mode
            logger.info(f"[digest] Notification mode set to: {mode}")

    def set_interval(self, minutes: int) -> None:
        self._interval_minutes = max(5, min(minutes, 1440))

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def interval_minutes(self) -> int:
        return self._interval_minutes

    def set_portfolio_snapshot(self, perp: dict | None = None, lp: dict | None = None) -> None:
        self._portfolio_snapshot = {"perp": perp, "lp": lp}

    def add(self, notification: dict) -> None:
        notification.setdefault("timestamp", datetime.now(timezone.utc))
        self._buffer.append(notification)

    async def maybe_flush(self) -> bool:
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
        """Send unified P&L report: perp + LP across 4H / 8H / 12H."""
        try:
            from wolfpack.db import get_db
            from wolfpack.notifications import send_telegram

            db = get_db()

            # ── PERP P&L ──
            perp_4h = _query_perp_pnl(db, 4)
            perp_8h = _query_perp_pnl(db, 8)
            perp_12h = _query_perp_pnl(db, 12)

            # ── LP snapshots for delta calc ──
            lp_current = _query_lp_snapshot(db, 0)   # latest snapshot = "now"
            lp_4h_ago = _query_lp_snapshot(db, 4)
            lp_8h_ago = _query_lp_snapshot(db, 8)
            lp_12h_ago = _query_lp_snapshot(db, 12)

            # Override with live snapshot if available
            snap_lp = (self._portfolio_snapshot or {}).get("lp")
            if snap_lp:
                lp_current = {
                    "fees": snap_lp.get("total_fees", 0),
                    "il": snap_lp.get("total_il", 0),
                    "equity": snap_lp.get("equity", 0),
                }

            lp_fees = lp_current.get("fees", 0)
            lp_il = lp_current.get("il", 0)
            lp_equity = lp_current.get("equity", 0)

            lp_delta_4h = _lp_delta(lp_current, lp_4h_ago)
            lp_delta_8h = _lp_delta(lp_current, lp_8h_ago)
            lp_delta_12h = _lp_delta(lp_current, lp_12h_ago)

            # ── Perp state ──
            snap_perp = (self._portfolio_snapshot or {}).get("perp")
            if snap_perp:
                perp_equity = snap_perp.get("equity", 0)
                perp_positions = len(snap_perp.get("positions", []))
                perp_unrealized = snap_perp.get("unrealized_pnl", 0)
            else:
                perp_equity = _query_perp_equity(db)
                perp_positions = 0
                perp_unrealized = 0

            # LP position count from snapshot or DB
            if snap_lp:
                lp_positions = len(snap_lp.get("positions", []))
            else:
                lp_positions = _query_lp_position_count(db)

            # ── BUILD MESSAGE ──
            total_4h = perp_4h['pnl'] + lp_delta_4h
            total_8h = perp_8h['pnl'] + lp_delta_8h
            total_12h = perp_12h['pnl'] + lp_delta_12h

            lines: list[str] = []
            lines.append("<b>WolfPack P&L Report</b>")
            lines.append("")
            lines.append("<pre>")
            lines.append(f"{'':8s} {'4H':>10s} {'8H':>10s} {'12H':>10s}")
            lines.append(f"{'Perp':8s} {_fmt_compact(perp_4h['pnl']):>10s} {_fmt_compact(perp_8h['pnl']):>10s} {_fmt_compact(perp_12h['pnl']):>10s}")
            lines.append(f"{'LP':8s} {_fmt_compact(lp_delta_4h):>10s} {_fmt_compact(lp_delta_8h):>10s} {_fmt_compact(lp_delta_12h):>10s}")
            lines.append(f"{'─' * 40}")
            lines.append(f"{'Total':8s} {_fmt_compact(total_4h):>10s} {_fmt_compact(total_8h):>10s} {_fmt_compact(total_12h):>10s}")
            lines.append("</pre>")

            # Perp detail line
            lines.append("")
            perp_line = f"<b>Perp</b>: ${perp_equity:,.0f}"
            if perp_positions > 0:
                perp_line += f" | {perp_positions} open | {_fmt_pnl(perp_unrealized)} unreal"
            lines.append(perp_line)
            if perp_4h['trades'] > 0:
                lines.append(f"  4H: {perp_4h['trades']} trades ({perp_4h['wins']}W/{perp_4h['losses']}L)")

            # LP detail line
            lines.append(f"<b>LP</b>: ${lp_equity:,.0f} | {lp_positions} pos | fees ${lp_fees:,.2f} | IL ${lp_il:,.2f}")

            msg = "\n".join(lines)
            await send_telegram(msg)
            logger.info(f"[digest] Sent P&L report (4H: {_fmt_compact(total_4h)})")

        except Exception as e:
            logger.warning(f"[digest] P&L report failed: {e}")
            try:
                await self._send_fallback_digest()
            except Exception:
                pass

        self._buffer.clear()
        self._last_flush = datetime.now(timezone.utc)
        self._portfolio_snapshot = None

    async def _send_fallback_digest(self) -> None:
        if not self._buffer:
            return
        from wolfpack.notifications import send_telegram
        closes = [n for n in self._buffer if n.get("type") == "trade_close"]
        perp_pnl = sum(n.get("pnl", 0) for n in closes)
        msg = f"<b>WolfPack</b>: {len(self._buffer)} events"
        if closes:
            msg += f" | Perp {_fmt_pnl(perp_pnl)} ({len(closes)} closed)"
        await send_telegram(msg)

    async def force_flush(self) -> None:
        await self._send_pnl_report()


# ── DB query helpers ──

def _query_perp_pnl(db, hours: int) -> dict:
    """Query perp P&L for the last N hours from wp_trade_history."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        result = db.table("wp_trade_history").select("pnl_usd").gte("closed_at", cutoff).execute()
        pnls = [float(r["pnl_usd"]) for r in (result.data or []) if r.get("pnl_usd") is not None]
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
    """Get LP snapshot from N hours ago (0 = latest)."""
    try:
        if hours == 0:
            result = (
                db.table("wp_lp_snapshots")
                .select("total_fees_usd, total_il_usd, total_value_usd")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        else:
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
                "fees": float(row.get("total_fees_usd", 0) or 0),
                "il": float(row.get("total_il_usd", 0) or 0),
                "equity": float(row.get("total_value_usd", 0) or 0),
            }
    except Exception as e:
        logger.warning(f"[digest] LP snapshot query failed ({hours}h): {e}")
    return {}


def _lp_delta(current: dict, past: dict) -> float:
    """Compute LP net profit delta between two snapshots."""
    if not past:
        return 0.0
    fee_gain = current.get("fees", 0) - past.get("fees", 0)
    il_gain = current.get("il", 0) - past.get("il", 0)
    return fee_gain - il_gain


def _query_perp_equity(db) -> float:
    """Get latest perp equity from snapshot table."""
    try:
        result = (
            db.table("wp_auto_portfolio_snapshots")
            .select("equity")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return float(result.data[0].get("equity", 0))
    except Exception:
        pass
    return 0


def _query_lp_position_count(db) -> int:
    """Get active LP position count."""
    try:
        result = (
            db.table("wp_lp_snapshots")
            .select("positions")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            positions = result.data[0].get("positions", [])
            return len(positions) if isinstance(positions, list) else 0
    except Exception:
        pass
    return 0


def _fmt_pnl(value: float) -> str:
    if value >= 0:
        return f"+${value:,.2f}"
    return f"-${abs(value):,.2f}"


def _fmt_compact(value: float) -> str:
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
