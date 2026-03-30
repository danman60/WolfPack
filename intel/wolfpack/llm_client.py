"""LLM Client for WolfPack Bot - DeepSeek via OpenRouter with tool calling."""

import os
import json
from typing import Any
import httpx

from wolfpack.config import settings

# OpenRouter API endpoint for DeepSeek
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEEPSEEK_DIRECT_URL = "https://api.deepseek.com/v1/chat/completions"

# Model ID for OpenRouter
MODEL_ID = "deepseek/deepseek-chat"

# Max iterations for tool calling loop
MAX_TOOL_ITERATIONS = 5


def get_openrouter_key() -> str | None:
    """Get OpenRouter API key from environment or config."""
    return os.environ.get("OPENROUTER_API_KEY") or settings.openrouter_api_key


def get_deepseek_key() -> str | None:
    """Get DeepSeek direct API key from environment or config."""
    return os.environ.get("DEEPSEEK_API_KEY") or settings.deepseek_api_key


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


async def call_llm(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
) -> dict:
    """
    Call DeepSeek via OpenRouter with optional tool definitions.
    
    Args:
        messages: List of message dicts with role and content
        tools: List of tool definitions in OpenAI function-calling format
        tool_choice: "auto", "none", or "required"
    
    Returns:
        dict with 'content' and/or 'tool_calls' keys
    """
    # Build request payload
    payload = {
        "model": MODEL_ID,
        "messages": messages,
    }
    
    if tools:
        payload["tools"] = build_tool_schema(tools)
        payload["tool_choice"] = tool_choice
    
    # Get API key
    openrouter_key = get_openrouter_key()
    deepseek_key = get_deepseek_key()
    
    headers = {
        "Authorization": f"Bearer {openrouter_key or deepseek_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://wolfpack.bot",
        "X-Title": "WolfPack Trading Bot",
    }
    
    # Try OpenRouter first
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()
            return _parse_response(result)
        except Exception as e:
            # Fallback to DeepSeek direct
            if deepseek_key and openrouter_key != deepseek_key:
                try:
                    headers["Authorization"] = f"Bearer {deepseek_key}"
                    # DeepSeek API uses its own model name, not OpenRouter's
                    ds_payload = payload.copy()
                    ds_payload["model"] = "deepseek-chat"
                    response = await client.post(
                        DEEPSEEK_DIRECT_URL,
                        headers=headers,
                        json=ds_payload,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    result = response.json()
                    return _parse_response(result)
                except Exception as fallback_err:
                    raise RuntimeError(
                        f"LLM call failed: OpenRouter error: {e}, DeepSeek fallback error: {fallback_err}"
                    )
            raise


def _parse_response(result: dict) -> dict:
    """Parse LLM response into unified format."""
    choice = result.get("choices", [{}])[0]
    message = choice.get("message", {})
    
    response = {
        "content": message.get("content", ""),
        "tool_calls": [],
        "finish_reason": choice.get("finish_reason", "stop"),
    }
    
    # Parse tool calls if present
    tool_calls = message.get("tool_calls", [])
    if tool_calls:
        for tc in tool_calls:
            response["tool_calls"].append({
                "id": tc.get("id", ""),
                "name": tc.get("function", {}).get("name", ""),
                "arguments": json.loads(tc.get("function", {}).get("arguments", "{}")),
            })
    
    return response


async def get_llm_response(
    messages: list[dict],
    user_id: str | None = None,
) -> tuple[str, list[dict]]:
    """
    Get LLM response with tool execution.
    
    Args:
        messages: Conversation messages including system prompt
        user_id: Optional user ID for permissions
    
    Returns:
        Tuple of (response content, list of tool calls for handling)
    """
    from wolfpack.bot_tools import TOOLS
    from wolfpack.bot_permissions import get_permission_tools
    
    # Filter tools based on permissions
    available_tools = get_permission_tools(TOOLS, user_id)
    
    # Call LLM with tool loop
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
    """
    Call LLM with tool execution loop.
    
    Args:
        messages: Initial conversation messages
        tools: Available tools for the LLM
        max_iterations: Maximum tool call iterations
    
    Returns:
        Tuple of (final response content, list of tool execution results)
    """
    current_messages = messages.copy()
    execution_log = []
    
    for iteration in range(max_iterations):
        # Call LLM
        response = await call_llm(
            messages=current_messages,
            tools=tools,
            tool_choice="auto" if tools else "none",
        )
        
        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])
        
        if not tool_calls:
            # No more tool calls needed
            return content, execution_log
        
        # Build the assistant message with ALL tool calls first
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

            # Find and execute
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
                    execution_log.append({"name": tool_name, "success": True, "result": result})
                    tool_response = json.dumps(result if isinstance(result, (dict, list)) else str(result))
                except Exception as e:
                    execution_log.append({"name": tool_name, "success": False, "error": str(e)})
                    tool_response = json.dumps({"error": str(e)})
            else:
                error_msg = f"Tool '{tool_name}' has no executor"
                execution_log.append({"name": tool_name, "success": False, "error": error_msg})
                tool_response = json.dumps({"error": error_msg})

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": tool_response,
            })

        # One assistant message with all tool_calls, then one tool message per call
        current_messages.append({
            "role": "assistant",
            "content": content or None,
            "tool_calls": assistant_tool_calls,
        })
        current_messages.extend(tool_results)
    
    # Max iterations reached
    return "Maximum tool iterations reached. Please try again.", execution_log
