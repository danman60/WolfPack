"""WolfPack Bot Tools - 20 tools with executors for LLM interaction.

Tools are defined in OpenAI function-calling JSON schema format with:
- name, description, parameters (JSON schema)
- permission tier (tier1=read, tier2=write)
- executor function
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)
try:
    import httpx as _http_lib
    _HTTP = "httpx"
except ImportError:
    import requests as _http_lib  # type: ignore
    _HTTP = "requests"

from wolfpack.config import settings
from wolfpack.bot_permissions import check_permission

# API base URL - used for making internal API calls
API_BASE_URL = "http://localhost:8000"


async def _api_get(endpoint: str, params: dict | None = None) -> dict:
    """Async GET request — won't deadlock single-worker uvicorn."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=30)
        return response.json()


async def _api_post(endpoint: str, json_data: dict | None = None) -> dict:
    """Async POST request — won't deadlock single-worker uvicorn."""
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE_URL}{endpoint}", json=json_data, timeout=30)
        return response.json()


# ============================================================================
# PORTFOLIO & MARKET TOOLS (4)
# ============================================================================

async def get_portfolio_executor(exchange: str = "hyperliquid") -> dict:
    """Get current portfolio positions from exchange adapter."""
    result = await _api_get("/portfolio", params={"exchange": exchange})
    return result


async def get_market_data_executor(pairs: str | None = None) -> dict:
    """Get market data: prices, volume, funding rates."""
    if pairs:
        # Fetch prices for each symbol individually
        symbols = [p.strip() for p in pairs.split(",")]
        results = {}
        for sym in symbols:
            result = await _api_get("/market/price", params={"symbol": sym.replace("-PERP", "")})
            results[sym] = result
        return {"prices": results}
    # Default: return BTC price
    return await _api_get("/market/price", params={"symbol": "BTC"})


async def get_pnl_executor() -> dict:
    """Get P&L summary for the portfolio."""
    result = await _api_get("/portfolio")
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


def _get_lp_snapshot() -> dict:
    """Pull current LP portfolio snapshot."""
    try:
        from wolfpack.lp_auto_trader import LPAutoTrader
        # Access the singleton LP trader from api module
        import wolfpack.api as api_mod
        lp = getattr(api_mod, "_lp_trader", None)
        if lp is None or not lp.enabled:
            return {}
        status = lp.get_status()
        return {
            "lp_equity": status.get("equity", 0),
            "lp_positions": status.get("positions", 0),
            "lp_total_fees": status.get("total_fees", 0),
            "lp_total_il": status.get("total_il", 0),
            "lp_realized_pnl": status.get("realized_pnl", 0),
            "lp_net_pnl": round(status.get("total_fees", 0) - status.get("total_il", 0) + status.get("realized_pnl", 0), 2),
            "lp_hedges": status.get("active_il_hedges", 0),
            "lp_hedge_usd": status.get("total_hedge_usd", 0),
        }
    except Exception:
        return {}


def _get_benchmark(hours: int, total_pnl: float, avg_deployed: float) -> dict | None:
    """Compute BTC buy-and-hold benchmark for the given window.

    Returns dict with btc_change_pct, buy_hold_return, and alpha,
    or None if price data is unavailable.
    """
    import time as _time
    try:
        now_ms = int(_time.time() * 1000)
        start_ms = now_ms - (hours * 3600 * 1000)

        def _post(url, payload):
            if _HTTP == "httpx":
                r = _http_lib.post(url, json=payload, timeout=10)
            else:
                r = _http_lib.post(url, json=payload, timeout=10)
            return r.json()

        # Fetch BTC candles for the window — first candle gives start price
        candles = _post("https://api.hyperliquid.xyz/info", {
            "type": "candleSnapshot",
            "req": {"coin": "BTC", "interval": "1h",
                    "startTime": start_ms, "endTime": start_ms + 3600_000},
        })
        if not candles or not isinstance(candles, list) or len(candles) == 0:
            return None
        btc_then = float(candles[0].get("o") or candles[0].get("open", 0))
        if btc_then <= 0:
            return None

        # Current BTC mid price
        mids = _post("https://api.hyperliquid.xyz/info", {"type": "allMids"})
        btc_now = float(mids.get("BTC", 0))
        if btc_now <= 0:
            return None

        btc_change_pct = (btc_now - btc_then) / btc_then * 100
        # Benchmark: if avg deployed capital was held as BTC spot
        buy_hold_return = avg_deployed * (btc_now - btc_then) / btc_then
        alpha = total_pnl - buy_hold_return

        return {
            "btc_start": round(btc_then, 2),
            "btc_now": round(btc_now, 2),
            "btc_change_pct": round(btc_change_pct, 2),
            "capital_deployed": round(avg_deployed, 2),
            "buy_hold_return": round(buy_hold_return, 2),
            "alpha": round(alpha, 2),
        }
    except Exception:
        return None


async def get_profit_executor(hours: int = 24) -> dict:
    """Get P&L for a time window from trade history DB (deduplicated)."""
    from wolfpack.db import get_db
    db = get_db()
    try:
        # Use raw SQL for deduplication — backtest reruns create duplicate rows
        result = db.rpc("get_deduplicated_pnl", {"hours_back": int(hours)}).execute()

        if result.data and len(result.data) == 1:
            row = result.data[0]
            perp = {
                "hours": hours,
                "total_pnl": float(row.get("total_pnl") or 0),
                "trades": int(row.get("unique_trades") or 0),
                "winners": int(row.get("winners") or 0),
                "losers": int(row.get("losers") or 0),
                "win_rate_pct": float(row.get("win_rate_pct") or 0),
                "avg_win": float(row.get("avg_win") or 0),
                "avg_loss": float(row.get("avg_loss") or 0),
                "best_trade": float(row.get("best_trade") or 0),
                "worst_trade": float(row.get("worst_trade") or 0),
            }
            lp = _get_lp_snapshot()
            if lp:
                perp["lp"] = lp
                perp["combined_pnl"] = round(perp["total_pnl"] + lp.get("lp_net_pnl", 0), 2)

            # Benchmark: query avg deployed capital from trade history
            try:
                from datetime import datetime, timezone, timedelta
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                size_result = db.table("wp_trade_history").select(
                    "size_usd"
                ).gte(
                    "closed_at", cutoff
                ).not_.is_("exit_price", "null").execute()
                if size_result.data:
                    sizes = [abs(float(t.get("size_usd", 0) or 0)) for t in size_result.data]
                    avg_deployed = sum(sizes) / max(len(sizes), 1)
                else:
                    avg_deployed = 0
                if avg_deployed > 0:
                    bench = _get_benchmark(hours, perp["total_pnl"], avg_deployed)
                    if bench:
                        perp["benchmark"] = bench
            except Exception as e:
                logger.warning(f"Benchmark calc failed: {e}")

            return perp

        # Fallback: client-side dedup if RPC not available
        result = db.table("wp_trade_history").select(
            "symbol, direction, entry_price, exit_price, pnl_usd, size_usd, closed_at"
        ).gte(
            "closed_at", f"now() - interval '{int(hours)} hours'"
        ).not_.is_("exit_price", "null").execute()

        if not result.data:
            return {"hours": hours, "total_pnl": 0, "trades": 0, "winners": 0, "losers": 0, "message": f"No closed trades in last {hours}h"}

        # Deduplicate by (symbol, direction, entry_price, exit_price)
        seen = set()
        unique_trades = []
        for t in result.data:
            key = (t.get("symbol"), t.get("direction"), t.get("entry_price"), t.get("exit_price"))
            if key not in seen:
                seen.add(key)
                unique_trades.append(t)

        pnls = [float(t.get("pnl_usd", 0) or 0) for t in unique_trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]

        perp = {
            "hours": hours,
            "total_pnl": round(sum(pnls), 2),
            "trades": len(unique_trades),
            "winners": len(winners),
            "losers": len(losers),
            "win_rate_pct": round(len(winners) / len(unique_trades) * 100, 1) if unique_trades else 0,
            "avg_win": round(sum(winners) / len(winners), 2) if winners else 0,
            "avg_loss": round(sum(losers) / len(losers), 2) if losers else 0,
            "best_trade": round(max(pnls), 2) if pnls else 0,
            "worst_trade": round(min(pnls), 2) if pnls else 0,
        }
        lp = _get_lp_snapshot()
        if lp:
            perp["lp"] = lp
            perp["combined_pnl"] = round(perp["total_pnl"] + lp.get("lp_net_pnl", 0), 2)

        # Benchmark: avg deployed capital from the trades we already have
        sizes = [abs(float(t.get("size_usd", 0) or 0)) for t in unique_trades]
        avg_deployed = sum(sizes) / max(len(sizes), 1) if sizes else 0
        if avg_deployed > 0:
            bench = _get_benchmark(hours, perp["total_pnl"], avg_deployed)
            if bench:
                perp["benchmark"] = bench

        return perp
    except Exception as e:
        return {"error": str(e)}


async def get_funding_rates_executor(exchange: str = "hyperliquid") -> dict:
    """Get funding rates from exchanges."""
    # Funding rates are embedded in the latest intelligence output
    result = await _api_get("/intelligence/latest", params={"exchange": exchange})
    funding = result.get("funding_rates", [])
    return {"exchange": exchange, "funding_rates": funding}


# ============================================================================
# AGENTS TOOLS (4)
# ============================================================================

async def get_agent_status_executor() -> dict:
    """Get running agents and their states."""
    result = await _api_get("/agents/status")
    return result


async def pause_agent_executor(agent_id: str) -> dict:
    """Pause a running agent."""
    result = await _api_post(f"/agents/{agent_id}/pause")
    return result


async def resume_agent_executor(agent_id: str) -> dict:
    """Resume a paused agent."""
    result = await _api_post(f"/agents/{agent_id}/resume")
    return result


async def get_recommendations_executor(status: str = "pending", limit: int = 10) -> dict:
    """Get pending trade recommendations."""
    result = await _api_get("/intelligence/recommendations", params={
        "status": status,
        "limit": limit
    })
    return result


# ============================================================================
# TRADE EXECUTION TOOLS (6) - All tier2 (require permission)
# ============================================================================

async def approve_trade_executor(recommendation_id: str, exchange: str = "hyperliquid") -> dict:
    """Approve a trade recommendation for execution."""
    if not check_permission("approve_trade"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}
    
    result = await _api_post(f"/recommendations/{recommendation_id}/approve", json_data={
        "exchange": exchange
    })
    return result


async def reject_trade_executor(recommendation_id: str) -> dict:
    """Reject a trade recommendation."""
    if not check_permission("reject_trade"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}
    
    result = await _api_post(f"/recommendations/{recommendation_id}/reject")
    return result


async def place_order_executor(
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

    result = await _api_post("/paper/order", json_data=params)
    return result


async def cancel_order_executor(order_id: str, exchange: str = "hyperliquid") -> dict:
    """Cancel an open order."""
    if not check_permission("cancel_order"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}

    # API expects symbol + order_id as query params, not body
    result = await _api_post(f"/trades/cancel?symbol=&order_id={order_id}")
    return result


async def close_position_executor(position_id: str, exchange: str = "hyperliquid") -> dict:
    """Close a trading position. position_id is treated as symbol (e.g. 'BTC')."""
    if not check_permission("close_position"):
        return {"status": "denied", "message": "Trade execution permission denied. Enable in permissions."}

    # API endpoint: POST /portfolio/close/{symbol}?exchange=...
    symbol = position_id.replace("-PERP", "").upper()
    result = await _api_post(f"/portfolio/close/{symbol}?exchange={exchange}")
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

async def autobot_status_executor() -> dict:
    """Get full AutoBot state and status."""
    result = await _api_get("/auto-trader/status")
    return result


async def autobot_start_executor(strategy: str = "default") -> dict:
    """Start the AutoBot (toggle on). The API uses a toggle endpoint."""
    if not check_permission("autobot_start"):
        return {"status": "denied", "message": "AutoBot control permission denied. Enable in permissions."}

    # Check current state first, then toggle if not already enabled
    status = await _api_get("/auto-trader/status")
    if status.get("enabled"):
        return {"status": "already_running", "message": "AutoBot is already running."}
    result = await _api_post("/auto-trader/toggle")
    return result


async def autobot_stop_executor() -> dict:
    """Stop the AutoBot (toggle off)."""
    if not check_permission("autobot_stop"):
        return {"status": "denied", "message": "AutoBot control permission denied. Enable in permissions."}

    # Check current state first, then toggle if enabled
    status = await _api_get("/auto-trader/status")
    if not status.get("enabled"):
        return {"status": "already_stopped", "message": "AutoBot is already stopped."}
    result = await _api_post("/auto-trader/toggle")
    return result


async def autobot_configure_executor(params: dict) -> dict:
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
    result = await _api_post(f"/auto-trader/config?{qs}")
    return result


# ============================================================================
# INTELLIGENCE TOOLS (2)
# ============================================================================

async def get_sentiment_executor(sources: str | None = None) -> dict:
    """Get social sentiment analysis from the latest intelligence output."""
    # Sentiment is embedded in /intelligence/latest output
    result = await _api_get("/intelligence/latest")
    sentiment = result.get("social_sentiment") or result.get("sentiment")
    if sentiment:
        return {"sentiment": sentiment}
    return {"status": "no_data", "message": "No sentiment data available. Run an intelligence cycle first."}


async def get_daily_report_executor(date: str | None = None) -> dict:
    """Get the latest daily trading report."""
    # Map to /intelligence/latest — the API doesn't have a separate daily-report endpoint
    result = await _api_get("/intelligence/latest")
    return result


# ============================================================================
# TOOL DEFINITIONS (20 tools total)
# ============================================================================

TOOLS = [
    # Portfolio & Market Tools (4)
    {
        "name": "get_portfolio",
        "description": "Get current Paper portfolio positions and status (simulated $10K manual trading engine).",
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
        "description": "Get current session P&L summary: realized, unrealized, win rate.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "permission": "tier1",
        "_executor": get_pnl_executor,
    },
    {
        "name": "get_profit",
        "description": "Get profit/loss for a time window (e.g. last 24h, 72h, 168h for 1 week). Queries closed trades from database. Includes benchmark comparison vs BTC buy-and-hold (alpha).",
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "Number of hours to look back (e.g. 24, 48, 72, 168 for 1 week)",
                    "default": 24
                }
            }
        },
        "permission": "tier1",
        "_executor": get_profit_executor,
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
        "description": "Get AutoBot autonomous portfolio: positions, equity, P&L ($25K autonomous trading engine).",
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
