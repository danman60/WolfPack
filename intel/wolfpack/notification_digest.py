"""Notification digest — periodic P&L report combining perp + LP into one TG message.

Sends a 4-hour report comparing current period vs previous, plus 8H/12H rolling totals.
Queries DB directly for all numbers.
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
        """Send unified P&L report: this 4H vs prev 4H + rolling 8H/12H."""
        try:
            from wolfpack.db import get_db
            from wolfpack.notifications import send_telegram

            db = get_db()

            # ── PERP: this 4H vs previous 4H ──
            perp_this_4h = _query_perp_pnl(db, 0, 4)
            perp_prev_4h = _query_perp_pnl(db, 4, 8)
            perp_8h = _query_perp_pnl(db, 0, 8)
            perp_12h = _query_perp_pnl(db, 0, 12)

            # ── LP: current vs snapshots ──
            lp_current = _query_lp_snapshot(db, 0)
            lp_4h_ago = _query_lp_snapshot(db, 4)
            lp_8h_ago = _query_lp_snapshot(db, 8)
            lp_12h_ago = _query_lp_snapshot(db, 12)

            # Override current with live snapshot if available
            snap_lp = (self._portfolio_snapshot or {}).get("lp")
            if snap_lp:
                lp_current = {
                    "fees": snap_lp.get("total_fees", 0),
                    "il": snap_lp.get("total_il", 0),
                    "equity": snap_lp.get("equity", 0),
                }

            lp_this_4h = _lp_delta(lp_current, lp_4h_ago)
            lp_prev_4h = _lp_delta(lp_4h_ago, lp_8h_ago)
            lp_8h = _lp_delta(lp_current, lp_8h_ago)
            lp_12h = _lp_delta(lp_current, lp_12h_ago)

            # ── Totals ──
            this_4h = perp_this_4h['pnl'] + lp_this_4h
            prev_4h = perp_prev_4h['pnl'] + lp_prev_4h
            delta = this_4h - prev_4h
            total_8h = perp_8h['pnl'] + lp_8h
            total_12h = perp_12h['pnl'] + lp_12h

            # Vibe + trend
            if this_4h > 500:
                vibe = "\U0001f525\U0001f4b0 PRINTING MONEY"
            elif this_4h > 100:
                vibe = "\U0001f4b8 The Pack is Eating"
            elif this_4h > 0:
                vibe = "\U0001f43a Grinding"
            elif this_4h > -100:
                vibe = "\U0001f629 Paper Cuts"
            else:
                vibe = "\U0001f6a8 Taking Heat"

            if delta > 200:
                trend = "\U0001f680 MOMENTUM"
            elif delta > 50:
                trend = "\u2b06\ufe0f up from prev"
            elif delta < -200:
                trend = "\U0001f4c9 cooling off"
            elif delta < -50:
                trend = "\u2b07\ufe0f down from prev"
            else:
                trend = "\u27a1\ufe0f steady"

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

            # LP state
            lp_equity = lp_current.get("equity", 0)
            lp_fees = lp_current.get("fees", 0)
            lp_il = lp_current.get("il", 0)
            if snap_lp:
                lp_positions = len(snap_lp.get("positions", []))
            else:
                lp_positions = _query_lp_position_count(db)

            # ── BUILD MESSAGE ──
            combined_equity = perp_equity + lp_equity
            combined_start = 25000.0  # perp $10K + LP $15K
            total_return_pct = ((combined_equity - combined_start) / combined_start) * 100

            lines: list[str] = []
            lines.append(f"\U0001f43a <b>WOLFPACK P&L</b> \U0001f43a")
            lines.append(f"{vibe}")
            lines.append("")

            # Hero: this 4H
            lines.append(f"\U0001f4b5 <b>Last 4 Hours: {_fmt_pnl(this_4h)}</b>")
            if perp_this_4h['trades'] > 0:
                wr = round(perp_this_4h['wins'] / perp_this_4h['trades'] * 100)
                lines.append(f"   \u26a1 Perps closed {perp_this_4h['trades']} trades ({perp_this_4h['wins']}W/{perp_this_4h['losses']}L, {wr}% win rate) for {_fmt_pnl(perp_this_4h['pnl'])}")
            else:
                lines.append(f"   \u26a1 Perps: no closed trades this period")
            if lp_this_4h != 0:
                lines.append(f"   \U0001f4a7 LP pools earned {_fmt_pnl(lp_this_4h)} in fees (net of IL)")
            else:
                lines.append(f"   \U0001f4a7 LP pools: holding steady")
            lines.append("")

            # Comparison to previous
            lines.append(f"\U0001f4ca <b>vs Previous 4H: {_fmt_pnl(prev_4h)}</b>  {trend}")
            if abs(delta) > 10:
                if delta > 0:
                    lines.append(f"   That's {_fmt_pnl(delta)} better than last period \U0001f4aa")
                else:
                    lines.append(f"   Down {_fmt_pnl(abs(delta))} from last period")
            lines.append("")

            # Rolling context
            lines.append(f"\U0001f552 <b>Rolling Totals</b>")
            lines.append(f"   8H: {_fmt_pnl(total_8h)}  \u2022  12H: {_fmt_pnl(total_12h)}")
            lines.append("")

            # Portfolio state
            lines.append(f"\U0001f4bc <b>Portfolio: ${combined_equity:,.0f}</b> ({total_return_pct:+.1f}% all-time)")
            if perp_positions > 0:
                lines.append(f"   \u26a1 Perps: ${perp_equity:,.0f} \u2022 {perp_positions} open positions \u2022 {_fmt_pnl(perp_unrealized)} unrealized")
            else:
                lines.append(f"   \u26a1 Perps: ${perp_equity:,.0f} \u2022 no open positions")
            lines.append(f"   \U0001f4a7 LP: ${lp_equity:,.0f} \u2022 {lp_positions} pools \u2022 ${lp_fees:,.0f} total fees earned")

            msg = "\n".join(lines)
            await send_telegram(msg)
            logger.info(f"[digest] P&L report sent (4H: {_fmt_compact(this_4h)}, {trend}, delta {_fmt_compact(delta)} vs prev)")

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

def _query_perp_pnl(db, hours_ago_start: int, hours_ago_end: int) -> dict:
    """Query perp P&L for a time window (hours_ago_start to hours_ago_end hours ago).

    Example: _query_perp_pnl(db, 0, 4) = last 4 hours
             _query_perp_pnl(db, 4, 8) = 4-8 hours ago (the previous 4H window)
    """
    try:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=hours_ago_end)).isoformat()
        end = (now - timedelta(hours=hours_ago_start)).isoformat()
        result = (
            db.table("wp_trade_history")
            .select("pnl_usd")
            .gte("closed_at", start)
            .lte("closed_at", end)
            .execute()
        )
        pnls = [float(r["pnl_usd"]) for r in (result.data or []) if r.get("pnl_usd") is not None]
        return {
            "pnl": sum(pnls),
            "trades": len(pnls),
            "wins": sum(1 for p in pnls if p > 0),
            "losses": sum(1 for p in pnls if p < 0),
        }
    except Exception as e:
        logger.warning(f"[digest] Perp query failed ({hours_ago_start}-{hours_ago_end}h): {e}")
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
    if not current or not past:
        return 0.0
    fee_gain = current.get("fees", 0) - past.get("fees", 0)
    il_gain = current.get("il", 0) - past.get("il", 0)
    return fee_gain - il_gain


def _query_perp_equity(db) -> float:
    try:
        result = (
            db.table("wp_portfolio_snapshots")
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
