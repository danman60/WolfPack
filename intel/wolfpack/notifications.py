"""Telegram notifications — sends alerts for trade recommendations and system events.

Usage:
    Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env

Messages:
- High-conviction recommendations (>= 70%)
- Position entries/exits
- Circuit breaker triggers
- Daily intelligence summaries
"""

import logging

import httpx

from wolfpack.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


async def send_telegram(message: str) -> bool:
    """Send a message via Telegram Bot API.

    Returns True if sent successfully, False otherwise.
    """
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.debug("Telegram not configured, skipping notification")
        return False

    url = f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return True
            logger.error(f"Telegram API error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


async def notify_recommendation(
    symbol: str,
    direction: str,
    conviction: int,
    rationale: str,
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> bool:
    """Send a trade recommendation notification."""
    arrow = "\u2b06\ufe0f" if direction == "long" else "\u2b07\ufe0f"
    msg = (
        f"<b>{arrow} {direction.upper()} {symbol}</b>\n"
        f"Conviction: <b>{conviction}%</b>\n"
    )
    if entry_price:
        msg += f"Entry: <code>${entry_price:,.2f}</code>\n"
    if stop_loss:
        msg += f"Stop Loss: <code>${stop_loss:,.2f}</code>\n"
    if take_profit:
        msg += f"Take Profit: <code>${take_profit:,.2f}</code>\n"
    msg += f"\n{rationale}"

    return await send_telegram(msg)


async def notify_position_opened(
    symbol: str,
    direction: str,
    entry_price: float,
    size_usd: float,
) -> bool:
    """Notify when a paper position is opened."""
    arrow = "\u2b06\ufe0f" if direction == "long" else "\u2b07\ufe0f"
    msg = (
        f"<b>{arrow} Position Opened: {direction.upper()} {symbol}</b>\n"
        f"Entry: <code>${entry_price:,.2f}</code>\n"
        f"Size: <code>${size_usd:,.2f}</code>"
    )
    return await send_telegram(msg)


async def notify_position_closed(
    symbol: str,
    direction: str,
    realized_pnl: float,
) -> bool:
    """Notify when a paper position is closed."""
    icon = "\u2705" if realized_pnl >= 0 else "\u274c"
    pnl_str = f"+${realized_pnl:,.2f}" if realized_pnl >= 0 else f"-${abs(realized_pnl):,.2f}"
    msg = (
        f"<b>{icon} Position Closed: {symbol}</b>\n"
        f"Direction: {direction.upper()}\n"
        f"P&L: <code>{pnl_str}</code>"
    )
    return await send_telegram(msg)


async def notify_circuit_breaker(state: str, reason: str) -> bool:
    """Notify on circuit breaker state changes."""
    icon = "\u26a0\ufe0f" if state == "SUSPENDED" else "\ud83d\uded1" if state == "EMERGENCY_STOP" else "\u2705"
    msg = f"<b>{icon} Circuit Breaker: {state}</b>\n{reason}"
    return await send_telegram(msg)


async def notify_daily_summary(
    equity: float,
    unrealized_pnl: float,
    realized_pnl: float,
    open_positions: int,
    pending_recs: int,
) -> bool:
    """Send daily portfolio summary."""
    total_pnl = unrealized_pnl + realized_pnl
    icon = "\u2705" if total_pnl >= 0 else "\u274c"
    pnl_str = f"+${total_pnl:,.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):,.2f}"

    msg = (
        f"<b>\ud83d\udcca Daily WolfPack Summary</b>\n\n"
        f"Equity: <code>${equity:,.2f}</code>\n"
        f"{icon} Total P&L: <code>{pnl_str}</code>\n"
        f"Open Positions: {open_positions}\n"
        f"Pending Recs: {pending_recs}"
    )
    return await send_telegram(msg)
