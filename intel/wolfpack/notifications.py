"""Telegram notifications — sends alerts for trade recommendations and system events.

Usage:
    Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env

Messages:
- High-conviction recommendations (>= 70%)
- Position entries/exits
- Circuit breaker triggers
- Daily intelligence summaries
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from wolfpack.config import settings

if TYPE_CHECKING:
    from wolfpack.telegram_bot import WolfPackBot

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"

# Bot fleet config — read from constellation dashboard
BOT_FLEET_CONFIG = Path.home() / "projects" / "constellation-dashboard" / "data" / "bot-fleet.json"

# Map function names to bot-fleet notification keys
_NOTIF_KEYS = {
    "notify_recommendation": "tradeRecommendations",
    "notify_position_opened": "positionOpened",
    "notify_position_closed": "positionClosed",
    "notify_circuit_breaker": "circuitBreaker",
    "notify_position_action": "positionActions",
    "notify_daily_summary": "dailySummary",
}


def _is_notif_enabled(func_name: str) -> bool:
    """Check if a notification is enabled in bot-fleet config. Fail-open."""
    try:
        data = json.loads(BOT_FLEET_CONFIG.read_text())
        if data.get("globalSettings", {}).get("globalMute", False):
            return False
        bot = next((b for b in data.get("bots", []) if b["id"] == "wolfpack"), None)
        if not bot or not bot.get("enabled", True):
            return False
        key = _NOTIF_KEYS.get(func_name, func_name)
        notif = bot.get("notifications", {}).get(key, {})
        if not notif:
            return True
        return notif.get("enabled", True) and notif.get("mode", "individual") != "disabled"
    except Exception:
        return True


def _get_conviction_threshold() -> int:
    """Get conviction threshold from bot-fleet config. Default 70."""
    try:
        data = json.loads(BOT_FLEET_CONFIG.read_text())
        bot = next((b for b in data.get("bots", []) if b["id"] == "wolfpack"), None)
        if not bot:
            return 70
        notif = bot.get("notifications", {}).get("tradeRecommendations", {})
        return notif.get("convictionThreshold", 70)
    except Exception:
        return 70

# Bot singleton — set by api.py on startup when bot is active
_bot_instance: "WolfPackBot | None" = None


def set_bot(bot: "WolfPackBot") -> None:
    """Register the active bot instance for inline keyboard support."""
    global _bot_instance
    _bot_instance = bot


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
    rec_id: str | None = None,
) -> bool:
    """Send a trade recommendation notification.

    Uses inline Approve/Reject buttons when bot is active and rec_id is provided.
    Falls back to plain text notification otherwise.
    """
    if not _is_notif_enabled("notify_recommendation"):
        return False
    # Check configurable conviction threshold
    threshold = _get_conviction_threshold()
    if conviction < threshold:
        logger.debug(f"Skipping rec: conviction {conviction}% < threshold {threshold}%")
        return False
    # Try inline buttons via bot first
    if _bot_instance and _bot_instance.is_running and rec_id:
        return await _bot_instance.send_recommendation_with_buttons(
            symbol=symbol,
            direction=direction,
            conviction=conviction,
            rationale=rationale,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rec_id=rec_id,
        )

    # Fallback to plain text
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
    if not _is_notif_enabled("notify_position_opened"):
        return False
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
    if not _is_notif_enabled("notify_position_closed"):
        return False
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
    if not _is_notif_enabled("notify_circuit_breaker"):
        return False
    icon = "\u26a0\ufe0f" if state == "SUSPENDED" else "\ud83d\uded1" if state == "EMERGENCY_STOP" else "\u2705"
    msg = f"<b>{icon} Circuit Breaker: {state}</b>\n{reason}"
    return await send_telegram(msg)


async def notify_position_action(
    symbol: str,
    action: str,
    reason: str,
    urgency: str = "medium",
    action_id: str | None = None,
) -> bool:
    """Send a position action notification with inline Approve/Dismiss buttons."""
    if not _is_notif_enabled("notify_position_action"):
        return False
    action_icons = {
        "close": "\u274c",
        "reduce": "\u2702\ufe0f",
        "adjust_stop": "\U0001f6e1\ufe0f",
        "adjust_tp": "\U0001f3af",
    }
    urgency_icons = {"low": "\U0001f7e2", "medium": "\U0001f7e1", "high": "\U0001f534"}

    icon = action_icons.get(action, "\u2699\ufe0f")
    urg_icon = urgency_icons.get(urgency, "\U0001f7e1")

    msg = (
        f"<b>{icon} Position Action: {action.upper()} {symbol}</b>\n"
        f"{urg_icon} Urgency: {urgency.upper()}\n\n"
        f"{reason}"
    )

    # Try inline buttons via bot first
    if _bot_instance and _bot_instance.is_running and action_id:
        return await _bot_instance.send_position_action_with_buttons(
            symbol=symbol,
            action=action,
            reason=reason,
            urgency=urgency,
            action_id=action_id,
        )

    return await send_telegram(msg)


async def notify_daily_summary(
    equity: float,
    unrealized_pnl: float,
    realized_pnl: float,
    open_positions: int,
    pending_recs: int,
) -> bool:
    """Send daily portfolio summary."""
    if not _is_notif_enabled("notify_daily_summary"):
        return False
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
