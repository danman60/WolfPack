"""Memory management for WolfPack LLM Bot.

Stores conversation history per user session.
"""

from datetime import datetime
from typing import Any
import json
import os


class BotMemory:
    """Manages conversation memory for the LLM bot."""

    def __init__(self, memory_file: str | None = None) -> None:
        """Initialize memory with optional persistence file."""
        import os
        self.memory_file = memory_file or os.path.expanduser("~/.wolfpack-bot/bot_memory.json")
        self.conversations: dict[str, list[dict]] = {}
        self._load()

    def _load(self) -> None:
        """Load conversations from file if it exists."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    self.conversations = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.conversations = {}

    def _save(self) -> None:
        """Save conversations to file."""
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, "w") as f:
                json.dump(self.conversations, f, indent=2)
        except IOError:
            pass  # Silently fail if can't write

    def get_conversation(self, user_id: str) -> list[dict]:
        """Get conversation for a user."""
        return self.conversations.get(user_id, [])

    def add_message(self, user_id: str, role: str, content: str, tool_calls: list | None = None) -> None:
        """Add a message to user's conversation."""
        if user_id not in self.conversations:
            self.conversations[user_id] = []

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if tool_calls:
            message["tool_calls"] = tool_calls

        self.conversations[user_id].append(message)

        # Limit conversation length
        if len(self.conversations[user_id]) > 50:
            self.conversations[user_id] = self.conversations[user_id][-50:]

        self._save()

    def add_user_message(self, user_id: str, text: str) -> None:
        """Add user message."""
        self.add_message(user_id, "user", text)

    def add_assistant_message(self, user_id: str, content: str, tool_calls: list[dict] | None = None) -> None:
        """Add assistant message with optional tool calls."""
        self.add_message(user_id, "assistant", content, tool_calls)

    def add_tool_message(self, user_id: str, tool_name: str, result: str, tool_call_id: str | None = None) -> None:
        """Add tool response with tool_call_id for API compatibility."""
        if user_id not in self.conversations:
            self.conversations[user_id] = []

        message = {
            "role": "tool",
            "content": result,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if tool_call_id:
            message["tool_call_id"] = tool_call_id

        self.conversations[user_id].append(message)

        if len(self.conversations[user_id]) > 50:
            self.conversations[user_id] = self.conversations[user_id][-50:]

        self._save()

    def clear_conversation(self, user_id: str) -> None:
        """Clear a user's conversation."""
        if user_id in self.conversations:
            del self.conversations[user_id]
            self._save()

    def get_system_prompt(self) -> str:
        """Get the system prompt."""
        from wolfpack.bot_prompt import format_system_prompt
        return format_system_prompt()

    def get_messages_for_llm(self, user_id: str) -> list[dict]:
        """Get all messages for LLM call including system prompt.

        Strips non-API fields (timestamp) and skips malformed tool_call
        entries that would cause DeepSeek 400 errors (missing 'id' field).
        """
        messages = [{"role": "system", "content": self.get_system_prompt()}]

        for msg in self.get_conversation(user_id):
            clean = {"role": msg["role"], "content": msg.get("content", "")}

            # Assistant messages with tool_calls need OpenAI-format ids
            if msg.get("tool_calls") and msg["role"] == "assistant":
                valid_calls = []
                for tc in msg["tool_calls"]:
                    # Only include if it has the required 'id' field
                    if isinstance(tc, dict) and tc.get("id"):
                        valid_calls.append({
                            "id": tc["id"],
                            "type": "function",
                            "function": tc.get("function", {
                                "name": tc.get("name", "unknown"),
                                "arguments": json.dumps(tc.get("arguments", {})),
                            }),
                        })
                if valid_calls:
                    clean["tool_calls"] = valid_calls
                    clean["content"] = clean["content"] or None

            # Tool response messages need tool_call_id
            if msg["role"] == "tool":
                tc_id = msg.get("tool_call_id")
                if not tc_id:
                    # Skip orphaned tool messages — no valid id to reference
                    continue
                clean["tool_call_id"] = tc_id

            messages.append(clean)

        return messages


# Global memory instance
_memory: BotMemory | None = None


def get_memory() -> BotMemory:
    """Get or create global memory instance."""
    global _memory
    if _memory is None:
        _memory = BotMemory()
    return _memory


def clear_memory() -> None:
    """Clear global memory instance."""
    global _memory
    _memory = None


def get_messages(chat_id: str) -> list[dict]:
    """Get messages for a chat."""
    return get_memory().get_conversation(str(chat_id))
