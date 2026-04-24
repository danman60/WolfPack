"""LLM Client for WolfPack Bot - Multi-provider fallback chain with tool calling."""

import os
import json
import logging
from typing import Any
import httpx

from wolfpack.config import settings

logger = logging.getLogger(__name__)

# Load API keys from ~/.env.keys
_env_keys: dict[str, str] = {}
try:
    with open(os.path.expanduser("~/.env.keys")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                _env_keys[key.strip()] = value.strip()
except FileNotFoundError:
    pass

# Backward compatibility constants
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL_ID = "deepseek-chat"
MAX_TOOL_ITERATIONS = 5

# Provider configuration with fallback order — Kimi K2.5 via NVIDIA NIM primary
# (free developer tier), DeepSeek fallback (paid), Minimax (free, rate-limited),
# then OpenRouter/Anthropic.
PROVIDERS = [
    {
        "name": "kimi",
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "moonshotai/kimi-k2.5",
        "key_env": "NIM_API_KEY",
        "format": "openai",
    },
    {
        "name": "deepseek",
        "url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
        "format": "openai",
    },
    {
        "name": "minimax",
        "url": "https://ollama.com/v1/chat/completions",
        "model": "minimax-m2.7:cloud",
        "key_env": "OLLAMA_API_KEY",
        "format": "openai",
    },
    {
        "name": "openrouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "deepseek/deepseek-chat",
        "key_env": "OPENROUTER_API_KEY",
        "format": "openai",
    },
    {
        "name": "anthropic",
        "url": "https://api.anthropic.com/v1/messages",
        "model": "claude-sonnet-4-20250514",
        "key_env": "ANTHROPIC_API_KEY",
        "format": "anthropic",
    },
]

MAX_RETRIES_PER_PROVIDER = 2


def get_deepseek_key() -> str | None:
    """Get DeepSeek API key from environment or config."""
    return os.environ.get("DEEPSEEK_API_KEY") or settings.deepseek_api_key


def _get_api_key(key_env: str) -> str | None:
    """Get API key from env vars, config, or .env.keys file."""
    return os.environ.get(key_env) or getattr(settings, key_env.lower(), None) or _env_keys.get(key_env)


def build_tool_schema(tools: list[dict]) -> list[dict]:
    """Build OpenAI-compatible tool schema from WolfPack tools."""
    schema = []
    for tool in tools:
        schema.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
        })
    return schema


def _convert_to_anthropic_format(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Convert OpenAI-format messages to Anthropic format.
    Returns (system_prompt, messages_without_system).
    """
    system_prompt = None
    converted = []
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        else:
            converted.append({"role": msg["role"], "content": msg["content"]})
    return system_prompt, converted


def _parse_response(result: dict) -> dict:
    """Parse LLM response into unified format (OpenAI-compatible)."""
    choice = result.get("choices", [{}])[0]
    message = choice.get("message", {})
    
    response = {
        "content": message.get("content", ""),
        "tool_calls": [],
        "finish_reason": choice.get("finish_reason", "stop"),
    }
    
    tool_calls = message.get("tool_calls", [])
    if tool_calls:
        for tc in tool_calls:
            response["tool_calls"].append({
                "id": tc.get("id", ""),
                "name": tc.get("function", {}).get("name", ""),
                "arguments": json.loads(tc.get("function", {}).get("arguments", "{}")),
            })
    
    return response


def _parse_anthropic_response(result: dict) -> dict:
    """Parse Anthropic API response into unified format."""
    content_blocks = result.get("content", [])
    text = ""
    for block in content_blocks:
        if block.get("type") == "text":
            text += block.get("text", "")
    return {
        "content": text,
        "tool_calls": [],  # Anthropic tool calls not needed for our use case
        "finish_reason": result.get("stop_reason", "end_turn"),
    }


async def call_llm(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
) -> dict:
    """Call LLM with provider fallback chain: DeepSeek -> OpenRouter -> Claude."""
    last_error = None

    for provider in PROVIDERS:
        api_key = _get_api_key(provider["key_env"])
        if not api_key:
            logger.debug(f"[llm] Skipping {provider['name']}: no API key")
            continue

        for attempt in range(MAX_RETRIES_PER_PROVIDER):
            try:
                if provider["format"] == "anthropic":
                    result = await _call_anthropic(provider, api_key, messages, tools)
                else:
                    result = await _call_openai_compatible(provider, api_key, messages, tools, tool_choice)

                logger.info(f"[llm] Using {provider['name']} (attempt {attempt + 1})")
                return result

            except Exception as e:
                last_error = e
                error_str = str(e)
                # Retry on timeout or 5xx errors
                is_retryable = "timeout" in error_str.lower() or "5" == str(getattr(e, "status_code", ""))[:1]
                if not is_retryable and "500" not in error_str and "502" not in error_str and "503" not in error_str and "timeout" not in error_str.lower():
                    logger.warning(f"[llm] {provider['name']} non-retryable error: {error_str[:200]}")
                    break  # Don't retry non-retryable errors, move to next provider
                logger.warning(f"[llm] {provider['name']} attempt {attempt + 1} failed: {error_str[:200]}")

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


async def _call_openai_compatible(provider: dict, api_key: str, messages: list[dict], tools: list[dict] | None, tool_choice: str) -> dict:
    """Call an OpenAI-compatible API (DeepSeek, OpenRouter)."""
    payload = {
        "model": provider["model"],
        "messages": messages,
    }
    if tools:
        payload["tools"] = build_tool_schema(tools)
        payload["tool_choice"] = tool_choice

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            provider["url"],
            headers=headers,
            json=payload,
            timeout=60.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"{provider['name']} API returned {response.status_code}: {response.text[:300]}")
        result = response.json()
        return _parse_response(result)


async def _call_anthropic(provider: dict, api_key: str, messages: list[dict], tools: list[dict] | None) -> dict:
    """Call Anthropic API (different format from OpenAI)."""
    system_prompt, converted_messages = _convert_to_anthropic_format(messages)

    payload = {
        "model": provider["model"],
        "max_tokens": 4096,
        "messages": converted_messages,
    }
    if system_prompt:
        payload["system"] = system_prompt

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            provider["url"],
            headers=headers,
            json=payload,
            timeout=90.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Anthropic API returned {response.status_code}: {response.text[:300]}")
        result = response.json()
        return _parse_anthropic_response(result)


async def get_llm_response(
    messages: list[dict],
    user_id: str | None = None,
) -> tuple[str, list[dict]]:
    from wolfpack.bot_tools import TOOLS
    from wolfpack.bot_permissions import get_permission_tools
    available_tools = get_permission_tools(TOOLS, user_id)
    return await call_llm_with_tool_loop(
        messages=messages,
        tools=available_tools,
        max_iterations=MAX_TOOL_ITERATIONS,
    )


async def call_llm_with_tool_loop(
    messages: list[dict],
    tools: list[dict] | None = None,
    max_iterations: int = MAX_TOOL_ITERATIONS,
) -> tuple[str, list[dict]]:
    current_messages = messages.copy()
    execution_log = []
    
    for iteration in range(max_iterations):
        response = await call_llm(
            messages=current_messages,
            tools=tools,
            tool_choice="required" if (tools and iteration == 0) else ("auto" if tools else "none"),
        )
        
        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])
        
        if not tool_calls:
            return content, execution_log
        
        import inspect
        assistant_tool_calls = []
        tool_results = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("arguments", {})
            tc_id = tool_call.get("id", f"call_{tool_name}_{iteration}")

            assistant_tool_calls.append({
                "id": tc_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_args),
                }
            })

            executor = None
            for tool in (tools or []):
                if tool.get("name") == tool_name:
                    executor = tool.get("_executor")
                    break

            if executor:
                try:
                    if inspect.iscoroutinefunction(executor):
                        result = await executor(**tool_args)
                    else:
                        result = executor(**tool_args)
                    execution_log.append({"name": tool_name, "id": tc_id, "success": True, "result": result})
                    tool_response = json.dumps(result if isinstance(result, (dict, list)) else str(result))
                except Exception as e:
                    execution_log.append({"name": tool_name, "id": tc_id, "success": False, "error": str(e)})
                    tool_response = json.dumps({"error": str(e)})
            else:
                error_msg = f"Tool '{tool_name}' has no executor"
                execution_log.append({"name": tool_name, "id": tc_id, "success": False, "error": error_msg})
                tool_response = json.dumps({"error": error_msg})

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": tool_response,
            })

        current_messages.append({
            "role": "assistant",
            "content": content or None,
            "tool_calls": assistant_tool_calls,
        })
        current_messages.extend(tool_results)
    
    return "Maximum tool iterations reached. Please try again.", execution_log
