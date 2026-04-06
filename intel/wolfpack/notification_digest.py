"""Notification digest — buffers trade notifications and sends periodic summaries."""

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


class NotificationDigest:
    """Buffers notifications and sends periodic digest via Telegram."""

    def __init__(self):
        self._buffer: list[dict] = []
        self._last_flush: datetime = datetime.now(timezone.utc)
        self._mode: str = "hourly"  # individual, hourly, daily, disabled
        self._interval_minutes: int = 60  # for hourly mode
        self._portfolio_snapshot: dict | None = None

    def set_mode(self, mode: str) -> None:
        """Set digest mode: individual, hourly, daily, disabled."""
        if mode in ("individual", "hourly", "daily", "disabled"):
            self._mode = mode
            logger.info(f"[digest] Notification mode set to: {mode}")

    def set_interval(self, minutes: int) -> None:
        """Set custom digest interval in minutes (for hourly mode)."""
        self._interval_minutes = max(5, min(minutes, 1440))

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def interval_minutes(self) -> int:
        return self._interval_minutes

    def set_portfolio_snapshot(self, perp: dict | None = None, lp: dict | None = None) -> None:
        """Set current portfolio state for inclusion in the digest.

        perp: {positions: [...], equity: float, unrealized_pnl: float}
        lp: {positions: [...], total_fees: float, total_il: float, equity: float}
        """
        self._portfolio_snapshot = {"perp": perp, "lp": lp}

    def add(self, notification: dict) -> None:
        """Add a notification to the buffer.

        notification dict should have:
        - type: "trade_open", "trade_close", "stop_triggered", "stop_adjusted",
                "rotation_exit", "rebalance", "fee_harvest", "fee_milestone",
                "out_of_range", "lp_open", "lp_close", "lp_alert"
        - symbol: str
        - direction: str (for perp)
        - details: str (formatted message)
        - timestamp: datetime
        """
        notification.setdefault("timestamp", datetime.now(timezone.utc))
        self._buffer.append(notification)

    async def maybe_flush(self) -> bool:
        """Check if it's time to flush and send digest. Returns True if flushed."""
        if self._mode == "disabled" or not self._buffer:
            return False

        if self._mode == "individual":
            # Individual mode: flush each notification immediately
            for notif in self._buffer:
                try:
                    from wolfpack.notifications import send_telegram
                    await send_telegram(notif["details"])
                except Exception:
                    pass
            self._buffer.clear()
            self._last_flush = datetime.now(timezone.utc)
            return True

        # Digest modes: check interval
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_flush).total_seconds() / 60

        if self._mode == "hourly" and elapsed < self._interval_minutes:
            return False
        if self._mode == "daily" and elapsed < 1440:
            return False

        # Time to flush
        await self._send_digest()
        return True

    async def _send_digest(self) -> None:
        """Format and send unified hourly report combining perp + LP activity."""
        if not self._buffer:
            return

        try:
            from wolfpack.notifications import send_telegram

            # Split buffer into perp vs LP vs other
            perp_events = [n for n in self._buffer if n.get("type") in PERP_TYPES]
            lp_events = [n for n in self._buffer if n.get("type") in LP_TYPES]
            other_events = [n for n in self._buffer if n.get("type") not in PERP_TYPES and n.get("type") not in LP_TYPES]

            period_start = self._last_flush.strftime("%H:%M")
            period_end = datetime.now(timezone.utc).strftime("%H:%M")
            total_events = len(self._buffer)

            lines: list[str] = []
            lines.append(f"<b>WolfPack Hourly Report</b>")
            lines.append(f"{period_start} — {period_end} UTC  |  {total_events} events")

            perp_net_pnl = 0.0
            lp_net_pnl = 0.0

            # ── PERP SECTION ──
            if perp_events or (self._portfolio_snapshot and self._portfolio_snapshot.get("perp")):
                lines.append("")
                lines.append("<b>— Perp Trading —</b>")

                opens = [n for n in perp_events if n.get("type") == "trade_open"]
                closes = [n for n in perp_events if n.get("type") == "trade_close"]
                stops = [n for n in perp_events if n.get("type") in ("stop_triggered", "stop_adjusted")]

                if opens:
                    for n in opens:
                        arrow = "\u2b06" if n.get("direction") == "long" else "\u2b07"
                        lines.append(f"  {arrow} Opened {n.get('symbol')} {n.get('direction','')} ${n.get('size', 0):,.0f}")

                if closes:
                    perp_net_pnl = sum(n.get("pnl", 0) for n in closes)
                    winners = sum(1 for n in closes if n.get("pnl", 0) > 0)
                    losers = sum(1 for n in closes if n.get("pnl", 0) < 0)
                    for n in closes:
                        pnl = n.get("pnl", 0)
                        pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                        lines.append(f"  Closed {n.get('symbol')} {n.get('direction','')}: {pnl_str}")
                    lines.append(f"  Net: {_fmt_pnl(perp_net_pnl)} ({winners}W/{losers}L)")

                if stops:
                    cap = min(len(stops), 3)
                    for n in stops[:cap]:
                        lines.append(f"  {n.get('details', '')[:80]}")
                    if len(stops) > cap:
                        lines.append(f"  +{len(stops) - cap} more adjustments")

                # Active positions summary from snapshot
                snap = (self._portfolio_snapshot or {}).get("perp")
                if snap:
                    pos_count = len(snap.get("positions", []))
                    unrealized = snap.get("unrealized_pnl", 0)
                    if pos_count > 0:
                        lines.append(f"  Active: {pos_count} pos, unrealized {_fmt_pnl(unrealized)}")

                if not opens and not closes and not stops and not snap:
                    lines.append("  No perp activity")

            # ── LP SECTION ──
            if lp_events or (self._portfolio_snapshot and self._portfolio_snapshot.get("lp")):
                lines.append("")
                lines.append("<b>— LP Positions —</b>")

                rotations = [n for n in lp_events if n.get("type") == "rotation_exit"]
                rebalances = [n for n in lp_events if n.get("type") == "rebalance"]
                harvests = [n for n in lp_events if n.get("type") == "fee_harvest"]
                milestones = [n for n in lp_events if n.get("type") == "fee_milestone"]
                oor = [n for n in lp_events if n.get("type") == "out_of_range"]
                lp_other = [n for n in lp_events if n.get("type") not in ("rotation_exit", "rebalance", "fee_harvest", "fee_milestone", "out_of_range")]

                # Portfolio summary from snapshot
                lp_snap = (self._portfolio_snapshot or {}).get("lp")
                if lp_snap:
                    pos_count = len(lp_snap.get("positions", []))
                    total_fees = lp_snap.get("total_fees", 0)
                    total_il = lp_snap.get("total_il", 0)
                    lp_net_pnl = total_fees - abs(total_il)
                    lines.append(f"  {pos_count} positions | fees ${total_fees:,.2f} | IL ${total_il:,.2f}")

                if harvests:
                    lines.append(f"  Harvested: {len(harvests)} times")
                    for h in harvests[:2]:
                        lines.append(f"    {h.get('pair','')}: {h.get('message','')[:60]}")

                if rotations:
                    for r in rotations:
                        lines.append(f"  Rotated out {r.get('pair','')}: {r.get('message','')[:60]}")

                if rebalances:
                    for rb in rebalances:
                        lines.append(f"  Rebalanced {rb.get('pair','')}: {rb.get('message','')[:60]}")

                if oor:
                    lines.append(f"  \u26a0 {len(oor)} out-of-range warning(s)")

                if milestones:
                    for m in milestones:
                        lines.append(f"  {m.get('message','')[:80]}")

                if lp_other:
                    for lo in lp_other[:2]:
                        lines.append(f"  {lo.get('message', lo.get('details', ''))[:80]}")

                if not lp_events and not lp_snap:
                    lines.append("  No LP activity")

            # ── OTHER ──
            if other_events:
                lines.append("")
                lines.append(f"<b>Other:</b> {len(other_events)} event(s)")
                for o in other_events[:3]:
                    lines.append(f"  {o.get('details', str(o.get('type', '')))[:80]}")

            # ── COMBINED FOOTER ──
            lines.append("")
            total_pnl = perp_net_pnl + lp_net_pnl
            parts = []
            if perp_net_pnl != 0:
                parts.append(f"Perp {_fmt_pnl(perp_net_pnl)}")
            if lp_net_pnl != 0:
                parts.append(f"LP {_fmt_pnl(lp_net_pnl)}")
            if parts:
                lines.append(f"<b>Portfolio: {_fmt_pnl(total_pnl)}</b> ({' + '.join(parts)})")

            msg = "\n".join(lines)
            await send_telegram(msg)
            logger.info(f"[digest] Sent unified digest with {len(self._buffer)} events")

        except Exception as e:
            logger.warning(f"[digest] Failed to send digest: {e}")

        self._buffer.clear()
        self._last_flush = datetime.now(timezone.utc)
        self._portfolio_snapshot = None

    async def force_flush(self) -> None:
        """Force send digest now regardless of interval."""
        await self._send_digest()


def _fmt_pnl(value: float) -> str:
    """Format a P&L value with sign and dollar."""
    if value >= 0:
        return f"+${value:,.2f}"
    return f"-${abs(value):,.2f}"


# Singleton
_digest: NotificationDigest | None = None

def get_digest() -> NotificationDigest:
    global _digest
    if _digest is None:
        _digest = NotificationDigest()
    return _digest
