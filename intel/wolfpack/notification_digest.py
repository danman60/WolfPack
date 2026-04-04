"""Notification digest — buffers trade notifications and sends periodic summaries."""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class NotificationDigest:
    """Buffers notifications and sends periodic digest via Telegram."""

    def __init__(self):
        self._buffer: list[dict] = []
        self._last_flush: datetime = datetime.now(timezone.utc)
        self._mode: str = "individual"  # individual, hourly, daily, disabled
        self._interval_minutes: int = 60  # for hourly mode

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

    def add(self, notification: dict) -> None:
        """Add a notification to the buffer.

        notification dict should have:
        - type: "trade_open", "trade_close", "stop_triggered", "stop_adjusted"
        - symbol: str
        - direction: str
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
        """Format and send the buffered notifications as a single digest message."""
        if not self._buffer:
            return

        try:
            from wolfpack.notifications import send_telegram

            # Group by type
            opens = [n for n in self._buffer if n.get("type") == "trade_open"]
            closes = [n for n in self._buffer if n.get("type") == "trade_close"]
            stops = [n for n in self._buffer if n.get("type") in ("stop_triggered", "stop_adjusted")]
            other = [n for n in self._buffer if n.get("type") not in ("trade_open", "trade_close", "stop_triggered", "stop_adjusted")]

            # Calculate summary stats
            total_pnl = sum(n.get("pnl", 0) for n in closes)
            winners = sum(1 for n in closes if n.get("pnl", 0) > 0)
            losers = sum(1 for n in closes if n.get("pnl", 0) < 0)

            # Build digest message
            lines = [f"<b>\U0001f4ca AutoBot Digest</b> ({len(self._buffer)} events)"]
            lines.append(f"Period: {self._last_flush.strftime('%H:%M')} \u2014 {datetime.now(timezone.utc).strftime('%H:%M')} UTC")
            lines.append("")

            if opens:
                lines.append(f"<b>\U0001f4c8 Opened: {len(opens)} positions</b>")
                for n in opens:
                    arrow = "\u2b06\ufe0f" if n.get("direction") == "long" else "\u2b07\ufe0f"
                    lines.append(f"  {arrow} {n.get('symbol')} {n.get('direction')} ${n.get('size', 0):,.0f}")
                lines.append("")

            if closes:
                lines.append(f"<b>\U0001f4c9 Closed: {len(closes)} trades</b>")
                for n in closes:
                    pnl = n.get("pnl", 0)
                    pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                    lines.append(f"  {n.get('symbol')} {n.get('direction')}: {pnl_str}")
                lines.append(f"  <b>Net P&L: {'+'if total_pnl>=0 else ''}{total_pnl:,.2f} ({winners}W/{losers}L)</b>")
                lines.append("")

            if stops:
                lines.append(f"<b>\U0001f6e1\ufe0f Stop updates: {len(stops)}</b>")
                for n in stops[:5]:  # cap at 5 to avoid huge messages
                    lines.append(f"  {n.get('symbol')}: {n.get('details', '')[:60]}")
                if len(stops) > 5:
                    lines.append(f"  ...and {len(stops) - 5} more")
                lines.append("")

            if other:
                lines.append(f"<b>\u2139\ufe0f Other: {len(other)}</b>")

            msg = "\n".join(lines)
            await send_telegram(msg)
            logger.info(f"[digest] Sent digest with {len(self._buffer)} events")

        except Exception as e:
            logger.warning(f"[digest] Failed to send digest: {e}")

        self._buffer.clear()
        self._last_flush = datetime.now(timezone.utc)

    async def force_flush(self) -> None:
        """Force send digest now regardless of interval."""
        await self._send_digest()


# Singleton
_digest: NotificationDigest | None = None

def get_digest() -> NotificationDigest:
    global _digest
    if _digest is None:
        _digest = NotificationDigest()
    return _digest
