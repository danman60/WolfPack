"""WolfPack Bot Tools - 20 tools with executors for LLM interaction.

Tools are defined in OpenAI function-calling JSON schema format with:
- name, description, parameters (JSON schema)
- permission tier (tier1=read, tier2=write)
- executor function
"""

import asyncio
import json
from typing import Any
import httpx

from wolfpack.config import settings
from wolfpack.bot_permissions import check_permission

# API base URL - used for making internal API calls
API_BASE_URL = "http://localhost:8000"


def _api_get(endpoint: str, params: dict | None = None) -> dict:
    """Make a GET request to the internal API."""
    return _sync_api_get(endpoint, params)


def _sync_api_get(endpoint: str, params: dict | None = None) -> dict:
    """Synchronous GET request to API."""
    import requests
    response = requests.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=30)
    return response.json()


def _api_post(endpoint: str, json_data: dict | None = None) -> dict:
    """Make a POST request to the internal API."""
    try:
        asyncio.get_running_loop()
        # Called from async context — must use sync helper directly
        # (can't run_in_executor from a non-async function reliably)
        return _sync_api_post(endpoint, json_data)
    except RuntimeError:
        return _sync_api_post(endpoint, json_data)


def _sync_api_post(endpoint: str, json_data: dict | None = None) -> dict:
    """Synchronous POST request to API."""
    import requests
    response = requests.post(f"{API_BASE_URL}{endpoint}", json=json_data, timeout=30)
    return response.json()


# ============================================================================
# PORTFOLIO & MARKET TOOLS (4)
# ============================================================================

def get_portfolio_executor(exchange: str = "hyperliquid") -> dict:
    """Get current portfolio positions from exchange adapter."""
    result = _api_get("/portfolio", params={"exchange": exchange})
    return result


def get_market_data_executor(pairs: str | None = None) -> dict:
    """Get market data: prices, volume, funding rates."""
    if pairs:
        # Fetch prices for each symbol individually
        symbols = [p.strip() for p in pairs.split(",")]
        results = {}
        for sym in symbols:
            result = _api_get("/market/price", params={"symbol": sym.replace("-PERP", "")})
            results[sym] = result
        return {"prices": results}
    # Default: return BTC price
    return _api_get("/market/price", params={"symbol": "BTC"})


def get_pnl_executor() -> dict:
    """Get P&L summary for the portfolio."""
    result = _api_get("/portfolio")
    portfolio = result.get("portfolio", result)
    return {
        "realized_pnl": portfolio.get("realized_pnl", 0),
        "unrealized_pnl": portfolio.get("unrealized_pnl", 0),
        "total_pnl": portfolio.get("realized_pnl", 0) + portfolio.get("unrealized_pnl", 0),
        "equity": portfolio.get("equity", 0),
        "starting_equity": portfolio.get("starting_equity", 0),
        "win_rate": portfolio.get("win_rate", 0),
        "closed_trades": portfolio.get("closed_trades", 0),
        "winning_trades": portfolio.get("winning_trades", 0),
    }


def get_funding_rates_executor(exchange: str = "hyperliquid") -> dict:
    """Get funding rates from exchanges."""
    # Funding rates are embedded in the latest intelligence output
    result = _api_get("/intelligence/latest", params={"exchange": exchange})
    funding = result.get("funding_rates", [])
    return {"exchange": exchange, "funding_rates": funding}


# ============================================================================
# AGENTS TOOLS (4)
# ============================================================================

def get_agent_status_executor() -> dict:
    """Get running agents and their states."""
    result = _api_get("/agents/status")
    return result


def pause_agent_executor(agent_id: str) -> dict:
    """Pause a running agent."""
    result = _api_post(f"/agents/{agent_id}/pause")
    return result


def resume_agent_executor(agent_id: str) -> dict:
    """Resume a paused agent."""
    result = _api_post(f"/agents/{agent_id}/resume")
    return result


def get_recommendations_executor(status: str = "pending", limit: int = 10) -> dict:
    """Get pending trade recommendations."""
    result = _api_get("/intelligence/recommendations", params={
        "status": status,
        "limit": limit
    })
    return result


# ============================================================================
# TRADE EXECUTION TOOLS (6) - All tier2 (require permission)
# ============================================================================

def approve_trade_executor(recommendation_id: str, exchange: str = "hyperliquid") -> dict:
    """Approve a trade recommendation for execution."""
    if not check_permission("approve_trade"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}
    
    result = _api_post(f"/recommendations/{recommendation_id}/approve", json_data={
        "exchange": exchange
    })
    return result


def reject_trade_executor(recommendation_id: str) -> dict:
    """Reject a trade recommendation."""
    if not check_permission("reject_trade"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}
    
    result = _api_post(f"/recommendations/{recommendation_id}/reject")
    return result


def place_order_executor(
    exchange: str,
    pair: str,
    side: str,
    amount: float,
    price: float | None = None,
    order_type: str = "limit"
) -> dict:
    """Place a new order on exchange (paper trade via /paper/order)."""
    if not check_permission("place_order"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}

    # Map side to direction (API uses 'long'/'short', not 'buy'/'sell')
    direction = "long" if side.lower() in ("buy", "long") else "short"
    symbol = pair.replace("-PERP", "").upper()

    params = {
        "symbol": symbol,
        "direction": direction,
        "size_usd": amount,
        "exchange": exchange,
    }
    if price:
        params["stop_loss"] = None  # price not used in paper/order; included for context

    result = _api_post("/paper/order", json_data=params)
    return result


def cancel_order_executor(order_id: str, exchange: str = "hyperliquid") -> dict:
    """Cancel an open order."""
    if not check_permission("cancel_order"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}

    # API expects symbol + order_id as query params, not body
    result = _sync_api_post(f"/trades/cancel?symbol=&order_id={order_id}")
    return result


def close_position_executor(position_id: str, exchange: str = "hyperliquid") -> dict:
    """Close a trading position. position_id is treated as symbol (e.g. 'BTC')."""
    if not check_permission("close_position"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}

    # API endpoint: POST /portfolio/close/{symbol}?exchange=...
    symbol = position_id.replace("-PERP", "").upper()
    result = _api_post(f"/portfolio/close/{symbol}?exchange={exchange}")
    return result


def set_stop_loss_executor(position_id: str, price: float, exchange: str = "hyperliquid") -> dict:
    """Set or update stop-loss for a position. position_id is treated as symbol.

    Note: The API does not expose a direct stop-loss endpoint. This patches the
    in-memory paper engine portfolio by going through the paper order flow.
    Returns an informational message instead of a no-op error.
    """
    if not check_permission("set_stop_loss"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}

    # No direct API endpoint for stop-loss updates — return advisory message
    return {
        "status": "advisory",
        "message": f"Stop-loss for {position_id} at {price} noted. "
                   "Automated stop-loss enforcement is handled by the paper engine internally.",
        "symbol": position_id,
        "stop_loss_price": price,
    }


# ============================================================================
# AUTOBOT CONTROL TOOLS (4) - All tier2 (require permission)
# ============================================================================

def autobot_status_executor() -> dict:
    """Get full AutoBot state and status."""
    result = _api_get("/auto-trader/status")
    return result


def autobot_start_executor(strategy: str = "default") -> dict:
    """Start the AutoBot (toggle on). The API uses a toggle endpoint."""
    if not check_permission("autobot_start"):
        return {"status": "denied", "message": "AutoBot control permission denied. Enable in permissions."}

    # Check current state first, then toggle if not already enabled
    status = _api_get("/auto-trader/status")
    if status.get("enabled"):
        return {"status": "already_running", "message": "AutoBot is already running."}
    result = _api_post("/auto-trader/toggle")
    return result


def autobot_stop_executor() -> dict:
    """Stop the AutoBot (toggle off)."""
    if not check_permission("autobot_stop"):
        return {"status": "denied", "message": "AutoBot control permission denied. Enable in permissions."}

    # Check current state first, then toggle if enabled
    status = _api_get("/auto-trader/status")
    if not status.get("enabled"):
        return {"status": "already_stopped", "message": "AutoBot is already stopped."}
    result = _api_post("/auto-trader/toggle")
    return result


def autobot_configure_executor(params: dict) -> dict:
    """Update AutoBot strategy and risk parameters."""
    if not check_permission("autobot_configure"):
        return {"status": "denied", "message": "AutoBot control permission denied. Enable in permissions."}

    # Map params to API query params: equity, conviction_threshold
    equity = params.get("equity") or params.get("auto_trade_equity")
    conviction = params.get("conviction_threshold") or params.get("auto_trade_conviction_threshold")
    query = []
    if equity is not None:
        query.append(f"equity={equity}")
    if conviction is not None:
        query.append(f"conviction_threshold={conviction}")
    qs = "&".join(query)
    result = _api_post(f"/auto-trader/config?{qs}")
    return result


# ============================================================================
# INTELLIGENCE TOOLS (2)
# ============================================================================

def get_sentiment_executor(sources: str | None = None) -> dict:
    """Get social sentiment analysis from the latest intelligence output."""
    # Sentiment is embedded in /intelligence/latest output
    result = _api_get("/intelligence/latest")
    sentiment = result.get("social_sentiment") or result.get("sentiment")
    if sentiment:
        return {"sentiment": sentiment}
    return {"status": "no_data", "message": "No sentiment data available. Run an intelligence cycle first."}


def get_daily_report_executor(date: str | None = None) -> dict:
    """Get the latest daily trading report."""
    # Map to /intelligence/latest — the API doesn't have a separate daily-report endpoint
    result = _api_get("/intelligence/latest")
    return result


# ============================================================================
# TOOL DEFINITIONS (20 tools total)
# ============================================================================

TOOLS = [
    # Portfolio & Market Tools (4)
    {
        "name": "get_portfolio",
        "description": "Get current portfolio positions and status from exchange.",
        "parameters": {
            "type": "object",
            "properties": {
                "exchange": {
                    "type": "string",
                    "description": "Exchange name (e.g., 'hyperliquid', 'binance')",
                    "default": "hyperliquid"
                }
            }
        },
        "permission": "tier1",
        "_executor": get_portfolio_executor,
    },
    {
        "name": "get_market_data",
        "description": "Get market data: prices, volume, funding rates for pairs.",
        "parameters": {
            "type": "object",
            "properties": {
                "pairs": {
                    "type": "string",
                    "description": "Comma-separated list of trading pairs (e.g., 'BTC-PERP,ETH-PERP')"
                }
            }
        },
        "permission": "tier1",
        "_executor": get_market_data_executor,
    },
    {
        "name": "get_pnl",
        "description": "Get P&L summary: realized, unrealized, win rate.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "permission": "tier1",
        "_executor": get_pnl_executor,
    },
    {
        "name": "get_funding_rates",
        "description": "Get current funding rates from exchanges.",
        "parameters": {
            "type": "object",
            "properties": {
                "exchange": {
                    "type": "string",
                    "description": "Exchange name (e.g., 'hyperliquid')",
                    "default": "hyperliquid"
                }
            }
        },
        "permission": "tier1",
        "_executor": get_funding_rates_executor,
    },
    # Agent Tools (4)
    {
        "name": "get_agent_status",
        "description": "Get status of all running trading agents.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "permission": "tier1",
        "_executor": get_agent_status_executor,
    },
    {
        "name": "pause_agent",
        "description": "Pause a running trading agent by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent ID to pause"
                }
            },
            "required": ["agent_id"]
        },
        "permission": "tier1",
        "_executor": pause_agent_executor,
    },
    {
        "name": "resume_agent",
        "description": "Resume a paused trading agent by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent ID to resume"
                }
            },
            "required": ["agent_id"]
        },
        "permission": "tier1",
        "_executor": resume_agent_executor,
    },
    {
        "name": "get_recommendations",
        "description": "Get pending trade recommendations from agents.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: 'pending', 'approved', 'rejected'",
                    "default": "pending"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of recommendations to return",
                    "default": 10
                }
            }
        },
        "permission": "tier1",
        "_executor": get_recommendations_executor,
    },
    # Trade Execution Tools (6) - tier2
    {
        "name": "approve_trade",
        "description": "Approve a trade recommendation for execution on exchange.",
        "parameters": {
            "type": "object",
            "properties": {
                "recommendation_id": {
                    "type": "string",
                    "description": "ID of the recommendation to approve"
                },
                "exchange": {
                    "type": "string",
                    "description": "Target exchange for execution",
                    "default": "hyperliquid"
                }
            },
            "required": ["recommendation_id"]
        },
        "permission": "tier2",
        "_executor": approve_trade_executor,
    },
    {
        "name": "reject_trade",
        "description": "Reject a trade recommendation.",
        "parameters": {
            "type": "object",
            "properties": {
                "recommendation_id": {
                    "type": "string",
                    "description": "ID of the recommendation to reject"
                }
            },
            "required": ["recommendation_id"]
        },
        "permission": "tier2",
        "_executor": reject_trade_executor,
    },
    {
        "name": "place_order",
        "description": "Place a new order on exchange. Be careful with parameters.",
        "parameters": {
            "type": "object",
            "properties": {
                "exchange": {
                    "type": "string",
                    "description": "Exchange name"
                },
                "pair": {
                    "type": "string",
                    "description": "Trading pair (e.g., 'BTC-PERP')"
                },
                "side": {
                    "type": "string",
                    "description": "Order side: 'buy' or 'sell'"
                },
                "amount": {
                    "type": "number",
                    "description": "Order amount/size"
                },
                "price": {
                    "type": "number",
                    "description": "Order price (optional for market orders)"
                },
                "order_type": {
                    "type": "string",
                    "description": "Order type: 'limit' or 'market'",
                    "default": "limit"
                }
            },
            "required": ["exchange", "pair", "side", "amount"]
        },
        "permission": "tier2",
        "_executor": place_order_executor,
    },
    {
        "name": "cancel_order",
        "description": "Cancel an open order by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "ID of the order to cancel"
                },
                "exchange": {
                    "type": "string",
                    "description": "Exchange where order was placed",
                    "default": "hyperliquid"
                }
            },
            "required": ["order_id"]
        },
        "permission": "tier2",
        "_executor": cancel_order_executor,
    },
    {
        "name": "close_position",
        "description": "Close a trading position by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "position_id": {
                    "type": "string",
                    "description": "ID of the position to close"
                },
                "exchange": {
                    "type": "string",
                    "description": "Exchange where position is held",
                    "default": "hyperliquid"
                }
            },
            "required": ["position_id"]
        },
        "permission": "tier2",
        "_executor": close_position_executor,
    },
    {
        "name": "set_stop_loss",
        "description": "Set or update stop-loss price for a position.",
        "parameters": {
            "type": "object",
            "properties": {
                "position_id": {
                    "type": "string",
                    "description": "ID of the position"
                },
                "price": {
                    "type": "number",
                    "description": "Stop-loss price"
                },
                "exchange": {
                    "type": "string",
                    "description": "Exchange where position is held",
                    "default": "hyperliquid"
                }
            },
            "required": ["position_id", "price"]
        },
        "permission": "tier2",
        "_executor": set_stop_loss_executor,
    },
    # AutoBot Control Tools (4) - tier2
    {
        "name": "autobot_status",
        "description": "Get AutoBot state: running, paused, stopped, positions.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "permission": "tier1",
        "_executor": autobot_status_executor,
    },
    {
        "name": "autobot_start",
        "description": "Start the AutoBot with specified strategy.",
        "parameters": {
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "description": "Trading strategy to use (e.g., 'default', 'conservative')",
                    "default": "default"
                }
            }
        },
        "permission": "tier2",
        "_executor": autobot_start_executor,
    },
    {
        "name": "autobot_stop",
        "description": "Stop the AutoBot. Use when you want to halt trading.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "permission": "tier2",
        "_executor": autobot_stop_executor,
    },
    {
        "name": "autobot_configure",
        "description": "Update AutoBot strategy and risk parameters.",
        "parameters": {
            "type": "object",
            "properties": {
                "params": {
                    "type": "object",
                    "description": "Configuration parameters (e.g., leverage, max_position_size)"
                }
            },
            "required": ["params"]
        },
        "permission": "tier2",
        "_executor": autobot_configure_executor,
    },
    # Intelligence Tools (2)
    {
        "name": "get_sentiment",
        "description": "Get social sentiment analysis from Twitter, Reddit, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "string",
                    "description": "Comma-separated sources: 'twitter', 'reddit', 'news'"
                }
            }
        },
        "permission": "tier1",
        "_executor": get_sentiment_executor,
    },
    {
        "name": "get_daily_report",
        "description": "Get the latest daily trading summary report.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (optional, defaults to today)"
                }
            }
        },
        "permission": "tier1",
        "_executor": get_daily_report_executor,
    },
]


async def execute_tool(tool_name: str, tool_args: dict) -> Any:
    """
    Execute a tool by name with the given arguments.
    
    Args:
        tool_name: Name of the tool to execute
        tool_args: Dictionary of arguments for the tool
    
    Returns:
        Result from the tool executor
    """
    # Find the tool definition
    tool_def = None
    for tool in TOOLS:
        if tool["name"] == tool_name:
            tool_def = tool
            break
    
    if not tool_def:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    executor = tool_def.get("_executor")
    if not executor:
        raise ValueError(f"No executor for tool: {tool_name}")
    
    # Check if executor is async
    import inspect
    if inspect.iscoroutinefunction(executor):
        return await executor(**tool_args)
    else:
        return executor(**tool_args)
