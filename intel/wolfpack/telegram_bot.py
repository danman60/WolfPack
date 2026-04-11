"""Two-way Telegram bot — commands + inline approve/reject buttons + LLM chat.

Uses python-telegram-bot (PTB) v21+ with asyncio polling.
Started from FastAPI lifespan; runs non-blocking alongside uvicorn.
"""

import asyncio
import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from wolfpack.config import settings

logger = logging.getLogger(__name__)


class WolfPackBot:
    """Telegram bot with slash commands and inline approve/reject for recommendations."""

    def __init__(self) -> None:
        self._app: Application | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Build the PTB application and start polling (non-blocking)."""
        if not settings.telegram_bot_token:
            logger.info("[telegram-bot] No bot token configured, skipping bot start")
            return

        self._app = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .build()
        )

        # Register handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("intel", self._cmd_intel))
        self._app.add_handler(CommandHandler("portfolio", self._cmd_portfolio))
        self._app.add_handler(CommandHandler("permissions", self._cmd_permissions))
        self._app.add_handler(CallbackQueryHandler(self._callback_handler))
        
        # LLM chat handler - messages that are not commands
        self._app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_llm_chat
        ))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        self._running = True
        logger.info("[telegram-bot] Bot started polling")

    async def stop(self) -> None:
        """Gracefully stop the bot."""
        if self._app and self._running:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._running = False
            logger.info("[telegram-bot] Bot stopped")

    async def send_recommendation_with_buttons(
        self,
        symbol: str,
        direction: str,
        conviction: int,
        rationale: str,
        entry_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        rec_id: str | None = None,
    ) -> bool:
        """Send a recommendation with inline Approve/Reject buttons."""
        if not self._app or not settings.telegram_chat_id:
            return False

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

        if rec_id:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("\u2705 Approve", callback_data=f"approve:{rec_id}"),
                    InlineKeyboardButton("\u274c Reject", callback_data=f"reject:{rec_id}"),
                ]
            ])
        else:
            keyboard = None

        try:
            await self._app.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=msg,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            logger.error(f"[telegram-bot] Failed to send recommendation: {e}")
            return False

    async def send_position_action_with_buttons(
        self,
        symbol: str,
        action: str,
        reason: str,
        urgency: str = "medium",
        action_id: str | None = None,
    ) -> bool:
        """Send a position action notification with inline Approve/Dismiss buttons."""
        if not self._app or not settings.telegram_chat_id:
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

        keyboard = None
        if action_id:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("\u2705 Approve", callback_data=f"pa_approve:{action_id}"),
                    InlineKeyboardButton("\u274c Dismiss", callback_data=f"pa_dismiss:{action_id}"),
                ]
            ])

        try:
            await self._app.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=msg,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            logger.error(f"[telegram-bot] Failed to send position action: {e}")
            return False

    # ── Command Handlers ──

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "<b>\U0001f43a WolfPack Intel Bot</b>\n\n"
            "Commands:\n"
            "/status — Portfolio equity & CB state\n"
            "/intel — Trigger intelligence run\n"
            "/portfolio — Open positions\n"
            "/help — Show this message",
            parse_mode="HTML",
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._cmd_start(update, context)

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            from wolfpack.api import _get_perp_trader, _get_circuit_breaker

            engine = _get_perp_trader("paper_perp").engine
            portfolio = engine.portfolio
            cb = _get_circuit_breaker()

            pnl = portfolio.realized_pnl + portfolio.unrealized_pnl
            pnl_icon = "\u2705" if pnl >= 0 else "\u274c"
            pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
            cb_icon = "\u2705" if cb.state == "ACTIVE" else "\u26a0\ufe0f"

            msg = (
                f"<b>\U0001f4ca WolfPack Status</b>\n\n"
                f"Equity: <code>${portfolio.equity:,.2f}</code>\n"
                f"{pnl_icon} Total P&L: <code>{pnl_str}</code>\n"
                f"Open Positions: {len(portfolio.positions)}\n"
                f"{cb_icon} Circuit Breaker: {cb.state}"
            )
            await update.message.reply_text(msg, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def _cmd_intel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            from wolfpack.api import _run_full_cycle, _running

            if _running:
                await update.message.reply_text("Intelligence cycle already running...")
                return

            await update.message.reply_text("\U0001f9e0 Starting intelligence cycle for BTC...")
            asyncio.create_task(_run_full_cycle("hyperliquid", "BTC"))
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def _cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            from wolfpack.api import _get_perp_trader

            engine = _get_perp_trader("paper_perp").engine
            portfolio = engine.portfolio

            if not portfolio.positions:
                await update.message.reply_text("No open positions.")
                return

            lines = ["<b>\U0001f4bc Open Positions</b>\n"]
            for p in portfolio.positions:
                arrow = "\u2b06\ufe0f" if p.direction == "long" else "\u2b07\ufe0f"
                pnl_str = f"+${p.unrealized_pnl:,.2f}" if p.unrealized_pnl >= 0 else f"-${abs(p.unrealized_pnl):,.2f}"
                lines.append(
                    f"{arrow} <b>{p.symbol}</b> {p.direction.upper()}\n"
                    f"   Entry: <code>${p.entry_price:,.2f}</code>  Size: <code>${p.size_usd:,.0f}</code>\n"
                    f"   P&L: <code>{pnl_str}</code>"
                )

            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def _cmd_permissions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show and manage permissions."""
        from wolfpack.bot_permissions import get_permissions_status, enable_tier2, disable_tier2
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        status = get_permissions_status()
        tier2_status = "✅ ENABLED" if status["tier2"] else "❌ DISABLED"
        
        msg = (
            f"<b>\U0001f512 WolfPack Permissions</b>\n\n"
            f"Tier 1 (Read): {'✅ ENABLED' if status['tier1'] else '❌ DISABLED'}\n"
            f"Tier 2 (Trade Execution): {tier2_status}\n\n"
            f"Tier 2 allows: approve trades, place orders, control AutoBot"
        )

        keyboard = []
        if not status["tier2"]:
            keyboard.append([InlineKeyboardButton("Enable Tier 2", callback_data="perm_enable")])
        else:
            keyboard.append([InlineKeyboardButton("Disable Tier 2", callback_data="perm_disable")])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

    async def _handle_llm_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle LLM chat messages."""
        if not update.message or not update.message.text:
            return

        user_id = str(update.effective_user.id)
        user_text = update.message.text.strip()

        try:
            # Import after handler registration to avoid circular imports
            from wolfpack.llm_client import get_llm_response
            from wolfpack.bot_memory import get_memory

            # Add user message to memory
            memory = get_memory()
            memory.add_user_message(user_id, user_text)

            # Get messages for LLM
            messages = memory.get_messages_for_llm(user_id)

            # Call LLM
            response, tool_calls = await get_llm_response(messages, user_id=user_id)

            # Add assistant response to memory
            if tool_calls:
                memory.add_assistant_message(user_id, response, tool_calls)
            else:
                memory.add_assistant_message(user_id, response)

            # Send response to user
            await update.message.reply_text(response)

            # Handle tool calls if any
            if tool_calls:
                await self._handle_tool_calls(update, context, user_id, tool_calls)

        except Exception as e:
            logger.error(f"LLM chat error: {e}")
            # Clean error message — no URLs or stack traces leaked to chat
            err_msg = str(e)
            if len(err_msg) > 150:
                err_msg = err_msg[:150] + "..."
            await update.message.reply_text(
                f"\U0001f6a8 {err_msg}",
                disable_web_page_preview=True,
            )

    async def _handle_tool_calls(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, tool_calls: list) -> None:
        """Store tool execution results from LLM loop into memory.

        tool_calls is the execution_log from call_llm_with_tool_loop:
        each item: {"name": str, "success": bool, "result": dict | "error": str}
        Tools are already executed — this just persists results to memory.
        """
        from wolfpack.bot_memory import get_memory

        memory = get_memory()

        for tool_call in tool_calls:
            # execution_log format: {"name": ..., "id": ..., "success": ..., "result": ...}
            tool_name = tool_call.get("name", "unknown")
            tc_id = tool_call.get("id")
            if tool_call.get("success"):
                result_str = str(tool_call.get("result", ""))
            else:
                result_str = f"Error: {tool_call.get('error', 'unknown error')}"

            memory.add_tool_message(user_id, tool_name, result_str, tool_call_id=tc_id)

    # ── Callback Handler (inline buttons) ──

    async def _callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        data = query.data or ""
        if ":" not in data:
            return

        action, rec_id = data.split(":", 1)

        if action == "approve":
            await self._handle_approve(query, rec_id)
        elif action == "reject":
            await self._handle_reject(query, rec_id)
        elif action == "pa_approve":
            await self._handle_pa_approve(query, rec_id)
        elif action == "pa_dismiss":
            await self._handle_pa_dismiss(query, rec_id)

    async def _handle_approve(self, query: Any, rec_id: str) -> None:
        try:
            from wolfpack.api import approve_recommendation

            result = await approve_recommendation(rec_id, exchange="hyperliquid")
            status = result.get("status", "error")

            if status == "executed":
                pos = result.get("position", {})
                await query.edit_message_text(
                    f"\u2705 <b>APPROVED & EXECUTED</b>\n\n"
                    f"{query.message.text}\n\n"
                    f"Position opened: ${pos.get('size_usd', 0):,.0f} @ ${pos.get('entry_price', 0):,.2f}",
                    parse_mode="HTML",
                )
            else:
                msg = result.get("message", status)
                await query.edit_message_text(
                    f"\u26a0\ufe0f <b>Approve failed:</b> {msg}\n\n{query.message.text}",
                    parse_mode="HTML",
                )
        except Exception as e:
            await query.edit_message_text(f"\u274c Error: {e}\n\n{query.message.text}", parse_mode="HTML")

    async def _handle_reject(self, query: Any, rec_id: str) -> None:
        try:
            from wolfpack.api import reject_recommendation

            await reject_recommendation(rec_id)
            await query.edit_message_text(
                f"\u274c <b>REJECTED</b>\n\n{query.message.text}",
                parse_mode="HTML",
            )
        except Exception as e:
            await query.edit_message_text(f"\u274c Error: {e}\n\n{query.message.text}", parse_mode="HTML")

    async def _handle_pa_approve(self, query: Any, action_id: str) -> None:
        try:
            from wolfpack.api import approve_position_action

            result = await approve_position_action(action_id)
            status = result.get("status", "error")

            if status == "executed":
                action = result.get("action", "unknown")
                symbol = result.get("symbol", "?")
                detail = ""
                if action == "close":
                    pnl = result.get("realized_pnl", 0)
                    pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                    detail = f"\nRealized P&L: {pnl_str}"
                elif action == "adjust_stop":
                    detail = f"\nNew stop: ${result.get('new_stop', 0):,.2f}"
                elif action == "adjust_tp":
                    detail = f"\nNew TP: ${result.get('new_tp', 0):,.2f}"
                elif action == "reduce":
                    detail = f"\nReduced by {result.get('reduced_by_pct', 0)}%"

                await query.edit_message_text(
                    f"\u2705 <b>APPROVED — {action.upper()} {symbol}</b>{detail}\n\n{query.message.text}",
                    parse_mode="HTML",
                )
            else:
                msg = result.get("message", status)
                await query.edit_message_text(
                    f"\u26a0\ufe0f <b>Approve failed:</b> {msg}\n\n{query.message.text}",
                    parse_mode="HTML",
                )
        except Exception as e:
            await query.edit_message_text(f"\u274c Error: {e}\n\n{query.message.text}", parse_mode="HTML")

    async def _handle_pa_dismiss(self, query: Any, action_id: str) -> None:
        try:
            from wolfpack.api import dismiss_position_action

            await dismiss_position_action(action_id)
            await query.edit_message_text(
                f"\u274c <b>DISMISSED</b>\n\n{query.message.text}",
                parse_mode="HTML",
            )
        except Exception as e:
            await query.edit_message_text(f"\u274c Error: {e}\n\n{query.message.text}", parse_mode="HTML")
