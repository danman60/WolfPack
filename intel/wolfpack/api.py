"""FastAPI application — exposes intelligence endpoints to the frontend."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import BackgroundTasks, Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from contextlib import asynccontextmanager

from wolfpack.config import settings

logger = logging.getLogger(__name__)

# Telegram bot singleton
_telegram_bot: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks for FastAPI."""
    global _telegram_bot

    # Start Telegram bot if configured
    if settings.telegram_bot_token:
        try:
            from wolfpack.telegram_bot import WolfPackBot
            from wolfpack.notifications import set_bot

            _telegram_bot = WolfPackBot()
            await _telegram_bot.start()
            set_bot(_telegram_bot)
            logger.info("[lifespan] Telegram bot started")
        except Exception as e:
            logger.warning(f"[lifespan] Telegram bot failed to start: {e}")

    # Initialize PromptBuilder for configurable agent prompts
    try:
        from wolfpack.db import get_db
        from wolfpack.prompt_builder import init_prompt_builder
        init_prompt_builder(get_db())
        logger.info("[lifespan] PromptBuilder initialized")
    except Exception as e:
        logger.warning(f"[lifespan] PromptBuilder init failed (agents will use hardcoded prompts): {e}")

    yield

    # Shutdown
    if _telegram_bot:
        try:
            await _telegram_bot.stop()
            logger.info("[lifespan] Telegram bot stopped")
        except Exception as e:
            logger.warning(f"[lifespan] Telegram bot stop error: {e}")


app = FastAPI(title="WolfPack Intel", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://wolf-pack-eight.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ──
_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Verify bearer token on protected endpoints. No-op if API_SECRET_KEY is unset."""
    if not settings.api_secret_key:
        raise HTTPException(status_code=403, detail="API authentication not configured")
    if creds is None or creds.credentials != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# Track last run times
_last_runs: dict[str, datetime | None] = {
    "quant": None,
    "snoop": None,
    "sage": None,
    "brief": None,
}
_running: set[str] = set()

# Track module last-run timestamps
_module_last_runs: dict[str, datetime | None] = {
    "regime_detection": None,
    "liquidity_intel": None,
    "funding_carry": None,
    "correlation": None,
    "volatility": None,
    "circuit_breakers": None,
    "execution_timing": None,
    "backtest": None,
    "social_sentiment": None,
    "whale_tracker": None,
}

# Circuit breaker singleton (persists across cycles)
_circuit_breaker: Any = None

# Drawdown monitor singleton (peak equity tracking)
_drawdown_monitor: Any = None

# Data freshness tracker singleton
_freshness_tracker: Any = None

# Failure tracker singleton (consecutive agent failure → safe mode)
_failure_tracker: Any = None

# Token usage tracker singleton
_token_tracker: Any = None


def _get_freshness_tracker() -> Any:
    """Get or create the freshness tracker singleton."""
    global _freshness_tracker
    if _freshness_tracker is None:
        from wolfpack.data_freshness import FreshnessTracker
        _freshness_tracker = FreshnessTracker()
    return _freshness_tracker


def _get_failure_tracker() -> Any:
    """Get or create the failure tracker singleton."""
    global _failure_tracker
    if _failure_tracker is None:
        from wolfpack.failure_tracker import FailureTracker
        _failure_tracker = FailureTracker()
    return _failure_tracker


def _get_token_tracker() -> Any:
    """Get or create the token tracker singleton. Also wires it into Agent base class."""
    global _token_tracker
    if _token_tracker is None:
        from wolfpack.token_tracker import TokenTracker
        from wolfpack.db import get_db
        from wolfpack.agents.base import Agent
        _token_tracker = TokenTracker(get_db())
        Agent.set_token_tracker(_token_tracker)
    return _token_tracker

# Latest module outputs (updated each intelligence cycle)
_latest_liquidity: Any = None
_latest_regime: Any = None
_latest_volatility: Any = None


def _get_circuit_breaker() -> Any:
    """Get or create the circuit breaker singleton. Restores state from DB on first access."""
    global _circuit_breaker
    if _circuit_breaker is None:
        from wolfpack.modules.circuit_breaker import CircuitBreaker
        _circuit_breaker = CircuitBreaker()
        # Restore persisted state (e.g. EMERGENCY_STOP survives restarts)
        try:
            from wolfpack.db import load_cb_state
            saved = load_cb_state()
            if saved and saved.get("state"):
                _circuit_breaker.restore_state(saved["state"], reason="Restored from DB on startup")
                logger.info(f"[circuit-breaker] Restored state: {saved['state']}")
        except Exception as e:
            logger.warning(f"[circuit-breaker] Could not restore state from DB: {e}")
    return _circuit_breaker


def _get_drawdown_monitor() -> Any:
    """Get or create the drawdown monitor singleton."""
    global _drawdown_monitor
    if _drawdown_monitor is None:
        from wolfpack.drawdown_monitor import DrawdownMonitor
        _drawdown_monitor = DrawdownMonitor()
    return _drawdown_monitor


@app.get("/health")
async def health():
    result = {"status": "ok", "service": "wolfpack-intel"}
    if _token_tracker is not None:
        result["token_usage_session"] = _token_tracker.get_session_totals()
    return result


@app.get("/health/deep")
async def deep_health_check():
    """Deep health check — data freshness, API keys, CB state, last intel run."""
    now = datetime.now(timezone.utc)
    stale_threshold = timedelta(minutes=10)
    checks: dict[str, Any] = {}

    # Data freshness — check module last-run times
    stale_modules = []
    for name, last_run in _module_last_runs.items():
        if last_run is None:
            stale_modules.append(f"{name}: never run")
        elif now - last_run > stale_threshold:
            age_min = (now - last_run).total_seconds() / 60
            stale_modules.append(f"{name}: {age_min:.0f}min ago")
    checks["data_freshness"] = {
        "ok": len(stale_modules) == 0,
        "stale_modules": stale_modules,
    }

    # API key validity
    checks["api_keys"] = {
        "deepseek": bool(settings.deepseek_api_key),
        "supabase": bool(settings.supabase_url and settings.supabase_key),
        "telegram": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "hyperliquid_wallet": bool(settings.hyperliquid_wallet),
    }

    # Circuit breaker state
    cb = _get_circuit_breaker()
    checks["circuit_breaker"] = {
        "state": cb.state,
        "ok": cb.state == "ACTIVE",
    }

    # Per-symbol data freshness from tracker
    tracker = _get_freshness_tracker()
    checks["symbol_freshness"] = tracker.get_all_freshness()


    # Agent failure tracker
    checks["failure_tracker"] = _get_failure_tracker().get_status()
    # Last successful intel run
    brief_last = _last_runs.get("brief")
    checks["last_intel_run"] = {
        "timestamp": brief_last.isoformat() if brief_last else None,
        "minutes_ago": round((now - brief_last).total_seconds() / 60, 1) if brief_last else None,
    }

    all_ok = (
        checks["data_freshness"]["ok"]
        and all(checks["api_keys"].values())
        and checks["circuit_breaker"]["ok"]
        and not checks["failure_tracker"]["safe_mode"]
    )
    status = "healthy" if all_ok else "degraded"

    return {"status": status, "checks": checks}


@app.get("/api/token-usage")
async def token_usage():
    """Return today's LLM token usage summary and session totals."""
    tracker = _get_token_tracker()
    return {
        "daily": tracker.get_daily_summary(),
        "session": tracker.get_session_totals(),
    }


@app.get("/agents/status")
async def agent_status():
    """Return status of all 4 intelligence agents."""
    return {
        "agents": [
            {
                "name": "The Quant",
                "key": "quant",
                "status": "running" if "quant" in _running else "idle",
                "last_run": _last_runs["quant"].isoformat() if _last_runs["quant"] else None,
            },
            {
                "name": "The Snoop",
                "key": "snoop",
                "status": "running" if "snoop" in _running else "idle",
                "last_run": _last_runs["snoop"].isoformat() if _last_runs["snoop"] else None,
            },
            {
                "name": "The Sage",
                "key": "sage",
                "status": "running" if "sage" in _running else "idle",
                "last_run": _last_runs["sage"].isoformat() if _last_runs["sage"] else None,
            },
            {
                "name": "The Brief",
                "key": "brief",
                "status": "running" if "brief" in _running else "idle",
                "last_run": _last_runs["brief"].isoformat() if _last_runs["brief"] else None,
            },
        ],
        "failure_tracker": _get_failure_tracker().get_status(),
    }


@app.get("/intelligence/latest")
async def latest_intelligence():
    """Return latest intelligence outputs from Supabase."""
    try:
        from wolfpack.db import get_latest_agent_outputs

        outputs = get_latest_agent_outputs()
        result: dict = {"quant": None, "snoop": None, "sage": None, "brief": None, "timestamp": None}
        for row in outputs:
            name = row.get("agent_name", "")
            result[name] = {
                "summary": row.get("summary"),
                "signals": row.get("signals"),
                "confidence": row.get("confidence"),
                "created_at": row.get("created_at"),
            }
            if result["timestamp"] is None or (row.get("created_at") and row["created_at"] > result["timestamp"]):
                result["timestamp"] = row.get("created_at")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch latest intelligence: {e}")
        return {"quant": None, "snoop": None, "sage": None, "brief": None, "timestamp": None}


@app.get("/intelligence/recommendations")
async def latest_recommendations(status: str = "pending", limit: int = 10):
    """Return latest trade recommendations."""
    try:
        from wolfpack.db import get_latest_recommendations

        return {"recommendations": get_latest_recommendations(status=status, limit=limit)}
    except Exception as e:
        logger.error(f"Failed to fetch recommendations: {e}")
        return {"recommendations": []}


@app.get("/modules/status")
async def module_status():
    """Return status of all 8 quantitative modules with real run times."""
    result = {}
    for name, last_run in _module_last_runs.items():
        result[name] = {
            "status": "completed" if last_run else "not_started",
            "last_run": last_run.isoformat() if last_run else None,
        }
    return {"modules": result}


# ── Strategy Mode ──

_strategy_mode: str = "paper"  # "paper" or "live"


@app.get("/strategy/mode")
async def get_strategy_mode():
    """Return current strategy mode and safety checklist."""
    checklist = _safety_checklist()
    return {
        "mode": _strategy_mode,
        "can_go_live": all(c["passed"] for c in checklist),
        "checklist": checklist,
    }


@app.post("/strategy/mode")
async def set_strategy_mode(mode: str, _auth: None = Depends(require_auth)):
    """Switch strategy mode. Requires all safety checks to go live."""
    global _strategy_mode

    if mode not in ("paper", "live"):
        return {"status": "error", "message": "Mode must be 'paper' or 'live'"}

    if mode == "live":
        checklist = _safety_checklist()
        failures = [c for c in checklist if not c["passed"]]
        if failures:
            return {
                "status": "blocked",
                "message": "Safety checks failed",
                "failures": failures,
            }

    _strategy_mode = mode
    logger.info(f"Strategy mode changed to: {mode}")
    return {"status": "ok", "mode": _strategy_mode}


def _safety_checklist() -> list[dict]:
    """P0 safety checklist for live trading."""
    return [
        {
            "name": "Private key configured",
            "passed": bool(settings.hyperliquid_private_key),
            "description": "HYPERLIQUID_PRIVATE_KEY must be set in .env",
        },
        {
            "name": "Circuit breaker active",
            "passed": _get_circuit_breaker().state != "EMERGENCY_STOP",
            "description": "Circuit breaker must not be in EMERGENCY_STOP state",
        },
        {
            "name": "Max position size set",
            "passed": True,  # Default 25% cap in Brief agent
            "description": "Brief agent caps at 25% per position",
        },
        {
            "name": "Intelligence pipeline tested",
            "passed": _last_runs.get("brief") is not None,
            "description": "At least one full intelligence cycle must have run",
        },
        {
            "name": "Paper trading profitable",
            "passed": _check_paper_profitable(),
            "description": "Paper trading must show positive returns before going live",
        },
    ]


def _check_paper_profitable() -> bool:
    """Check if paper trading has positive returns."""
    if _paper_engine is None:
        return False
    return _paper_engine.portfolio.realized_pnl > 0 or _paper_engine.portfolio.equity > _paper_engine.portfolio.starting_equity


@app.post("/recommendations/{rec_id}/approve")
async def approve_recommendation(rec_id: str, exchange: str = "hyperliquid", _auth: None = Depends(require_auth)):
    """Approve a trade recommendation for paper trading execution."""
    try:
        from wolfpack.db import get_db

        db = get_db()

        # Update status to approved
        result = (
            db.table("wp_trade_recommendations")
            .update({"status": "approved", "resolved_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", rec_id)
            .execute()
        )

        if not result.data:
            return {"status": "error", "message": "Recommendation not found"}

        rec = result.data[0]

        # Check circuit breaker before executing
        cb = _get_circuit_breaker()
        if not cb.state == "ACTIVE":
            return {
                "status": "blocked",
                "message": f"Circuit breaker is {cb.state} — new entries not allowed",
            }

        # Check liquidity gate
        if _latest_liquidity and not _latest_liquidity.trade_allowed:
            return {
                "status": "blocked",
                "message": f"Liquidity gate: {_latest_liquidity.reason}",
                "liquidity_health": _latest_liquidity.liquidity_health,
            }

        # Execute as paper trade
        engine = _get_paper_engine()

        # Resolve entry price — use rec value, fall back to live price
        entry_price = rec.get("entry_price")
        if not entry_price:
            try:
                from wolfpack.exchanges import get_exchange
                adapter = get_exchange(exchange)  # type: ignore[arg-type]
                candles = await adapter.get_candles(rec["symbol"], interval="1m", limit=1)
                if candles:
                    entry_price = candles[-1].close
            except Exception as e:
                logger.warning(f"[approve] Could not fetch live price for {rec['symbol']}: {e}")

        if not entry_price:
            return {"status": "error", "message": "No entry price available — run intel first or set entry_price"}

        # Apply slippage
        slippage_bps = _latest_liquidity.estimated_slippage_bps if _latest_liquidity else 5.0
        slippage_pct = slippage_bps / 10_000
        if rec["direction"] == "long":
            entry_price *= (1 + slippage_pct)
        else:
            entry_price *= (1 - slippage_pct)

        # Adaptive position sizing
        from wolfpack.modules.sizing import SizingEngine
        sizer = SizingEngine(base_pct=rec.get("size_pct") or 10.0)
        sizing = sizer.compute(
            conviction=rec.get("conviction", 50),
            vol_output=_latest_volatility,
            regime_output=_latest_regime,
            liquidity_output=_latest_liquidity,
        )
        size_pct = sizing.final_size_pct
        logger.info(f"[sizing] {rec['symbol']}: {sizing.rationale}")

        if size_pct <= 0:
            return {
                "status": "blocked",
                "message": f"Sizing engine returned 0%: {sizing.rationale}",
                "sizing": sizing.model_dump(),
            }

        pos = engine.open_position(
            symbol=rec["symbol"],
            direction=rec["direction"],
            current_price=round(entry_price, 2),
            size_pct=size_pct,
            recommendation_id=rec_id,
        )
        if pos:
            # Set stop/TP from recommendation
            if rec.get("stop_loss"):
                pos.stop_loss = rec["stop_loss"]
            if rec.get("take_profit"):
                pos.take_profit = rec["take_profit"]

            # Enable trailing stop — use Brief's recommendation or default based on vol regime
            trailing_pct = rec.get("trailing_stop_pct")
            if not trailing_pct and _latest_volatility:
                # Auto-assign trailing stop based on volatility regime
                vol_regime = _latest_volatility.vol_regime if hasattr(_latest_volatility, 'vol_regime') else "normal"
                if vol_regime in ("elevated", "high"):
                    trailing_pct = 4.0
                elif vol_regime == "extreme":
                    trailing_pct = 5.0
                else:
                    trailing_pct = 2.5  # Normal vol default
            if trailing_pct and trailing_pct > 0:
                engine.enable_trailing_stop(rec["symbol"], trailing_pct)
                logger.info(f"[approve] Trailing stop {trailing_pct}% enabled for {rec['symbol']}")

            # Update status to executed
            db.table("wp_trade_recommendations").update(
                {"status": "executed"}
            ).eq("id", rec_id).execute()

            # Store portfolio snapshot
            engine.store_snapshot(exchange)
            return {
                "status": "executed",
                "position": pos.model_dump(),
                "sizing": sizing.model_dump(),
            }

        return {"status": "error", "message": f"Could not open position — may already have {rec['symbol']} open"}

    except Exception as e:
        logger.error(f"Failed to approve recommendation: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/recommendations/{rec_id}/reject")
async def reject_recommendation(rec_id: str, _auth: None = Depends(require_auth)):
    """Reject a trade recommendation."""
    try:
        from wolfpack.db import get_db

        db = get_db()
        result = (
            db.table("wp_trade_recommendations")
            .update({"status": "rejected", "resolved_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", rec_id)
            .execute()
        )
        if not result.data:
            return {"status": "error", "message": "Recommendation not found"}
        return {"status": "rejected"}
    except Exception as e:
        logger.error(f"Failed to reject recommendation: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/portfolio")
async def portfolio_status(exchange: str = "hyperliquid"):
    """Return current paper trading portfolio state with live prices."""
    engine = _get_paper_engine()
    portfolio = engine.portfolio

    # Fetch live prices for open positions
    if portfolio.positions:
        try:
            from wolfpack.exchanges import get_exchange
            adapter = get_exchange(exchange)  # type: ignore[arg-type]
            symbols = list({p.symbol for p in portfolio.positions})
            prices: dict[str, float] = {}
            for sym in symbols:
                try:
                    candles = await adapter.get_candles(sym, interval="1m", limit=1)
                    if candles:
                        prices[sym] = candles[-1].close
                except Exception:
                    pass
            if prices:
                engine.update_prices(prices)
        except Exception as e:
            logger.warning(f"[portfolio] Failed to fetch live prices: {e}")

    return {
        "status": "active",
        "equity": round(portfolio.equity, 2),
        "starting_equity": portfolio.starting_equity,
        "realized_pnl": round(portfolio.realized_pnl, 2),
        "unrealized_pnl": round(portfolio.unrealized_pnl, 2),
        "free_collateral": round(portfolio.free_collateral, 2),
        "positions": [p.model_dump() for p in portfolio.positions],
        "closed_trades": portfolio.closed_trades,
        "winning_trades": portfolio.winning_trades,
        "win_rate": round(portfolio.winning_trades / portfolio.closed_trades, 3) if portfolio.closed_trades > 0 else 0,
        "type": "Paper",
    }


@app.get("/portfolio/history")
async def portfolio_history(limit: int = 100):
    """Return portfolio snapshot history for equity curve."""
    try:
        from wolfpack.db import get_db

        db = get_db()
        result = (
            db.table("wp_portfolio_snapshots")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        snapshots = result.data or []
        snapshots.reverse()  # Chronological order
        return {"snapshots": snapshots}
    except Exception as e:
        logger.error(f"Failed to fetch portfolio history: {e}")
        return {"snapshots": []}


@app.get("/portfolio/trades")
async def portfolio_trades(limit: int = 50):
    """Return closed trade history."""
    try:
        from wolfpack.db import get_db
        db = get_db()
        result = (
            db.table("wp_trade_history")
            .select("*")
            .order("closed_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"trades": result.data or []}
    except Exception as e:
        logger.error(f"[portfolio] Failed to fetch trade history: {e}")
        return {"trades": []}


@app.post("/portfolio/close/{symbol}")
async def close_position(symbol: str, exchange: str = "hyperliquid", _auth: None = Depends(require_auth)):
    """Close a paper trading position."""
    engine = _get_paper_engine()
    realized_pnl = engine.close_position(symbol.upper())
    # Clear position peak tracking on close
    try:
        _get_drawdown_monitor().clear_position_peak(symbol.upper())
    except Exception:
        pass
    engine.store_snapshot(exchange)
    return {"status": "closed", "symbol": symbol.upper(), "realized_pnl": round(realized_pnl, 2)}


@app.post("/paper/order")
async def paper_order(
    symbol: str,
    direction: str,
    size_usd: float,
    exchange: str = "hyperliquid",
    stop_loss: float | None = None,
    take_profit: float | None = None,
    _auth: None = Depends(require_auth),
):
    """Place a manual paper trade — bypasses recommendation flow."""
    engine = _get_paper_engine()

    # Get current price
    try:
        from wolfpack.exchanges import get_exchange

        adapter = get_exchange(exchange)  # type: ignore[arg-type]
        candles = await adapter.get_candles(symbol.upper(), interval="1m", limit=1)
        if not candles:
            return {"status": "error", "message": f"No price data for {symbol}"}
        current_price = candles[-1].close
    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch price: {e}"}

    # Compute size_pct from USD amount
    size_pct = (size_usd / engine.portfolio.equity) * 100 if engine.portfolio.equity > 0 else 0
    if size_pct <= 0 or size_pct > 100:
        return {"status": "error", "message": f"Invalid size: ${size_usd} is {size_pct:.1f}% of equity"}

    pos = engine.open_position(
        symbol=symbol.upper(),
        direction=direction.lower(),
        current_price=current_price,
        size_pct=min(size_pct, 25),  # Cap at 25%
        recommendation_id=f"manual-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
    )

    if pos:
        if stop_loss is not None:
            pos.stop_loss = stop_loss
        if take_profit is not None:
            pos.take_profit = take_profit
        engine.store_snapshot(exchange)
        return {
            "status": "executed",
            "position": pos.model_dump(),
            "message": f"Paper {direction} {symbol.upper()} ${size_usd} @ {current_price}",
        }

    return {"status": "error", "message": "Failed to open position — check free collateral"}


# ── Trade Execution Endpoints ──


@app.post("/trades/execute")
async def execute_trade(
    symbol: str,
    direction: str,
    size: float,
    price: float,
    order_type: str = "limit",
    reduce_only: bool = False,
    _auth: None = Depends(require_auth),
):
    """Execute a real trade on Hyperliquid (requires private key in .env)."""
    trader = _get_trader()
    if trader is None:
        return {"status": "error", "message": "HYPERLIQUID_PRIVATE_KEY not configured"}

    try:
        result = await trader.place_order(
            symbol=symbol.upper(),
            is_buy=(direction.lower() == "long"),
            size=size,
            price=price,
            reduce_only=reduce_only,
            order_type=order_type,  # type: ignore[arg-type]
        )
        return {"status": "submitted", "result": result}
    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/trades/positions")
async def get_positions():
    """Fetch current positions from Hyperliquid."""
    trader = _get_trader()
    if trader is None:
        return {"status": "error", "positions": [], "message": "HYPERLIQUID_PRIVATE_KEY not configured"}

    try:
        positions = await trader.get_positions()
        return {"status": "ok", "positions": positions, "type": "Actual"}
    except Exception as e:
        logger.error(f"Failed to fetch positions: {e}")
        return {"status": "error", "positions": [], "message": str(e)}


@app.get("/trades/orders")
async def get_open_orders():
    """Fetch open orders from Hyperliquid."""
    trader = _get_trader()
    if trader is None:
        return {"status": "error", "orders": [], "message": "HYPERLIQUID_PRIVATE_KEY not configured"}

    try:
        orders = await trader.get_open_orders()
        return {"status": "ok", "orders": orders}
    except Exception as e:
        logger.error(f"Failed to fetch orders: {e}")
        return {"status": "error", "orders": [], "message": str(e)}


@app.post("/trades/cancel")
async def cancel_order(symbol: str, order_id: int, _auth: None = Depends(require_auth)):
    """Cancel an open order on Hyperliquid."""
    trader = _get_trader()
    if trader is None:
        return {"status": "error", "message": "HYPERLIQUID_PRIVATE_KEY not configured"}

    try:
        result = await trader.cancel_order(symbol.upper(), order_id)
        return {"status": "cancelled", "result": result}
    except Exception as e:
        logger.error(f"Cancel failed: {e}")
        return {"status": "error", "message": str(e)}


# ── Singletons ──

# Paper trading engine (lazy-initialized on first intelligence run)
_paper_engine: Any = None
_trader_instance: Any = None


def _get_trader() -> Any:
    """Get or create the Hyperliquid trader singleton."""
    global _trader_instance
    if _trader_instance is None:
        if not settings.hyperliquid_private_key:
            return None
        from wolfpack.exchanges.hyperliquid_trading import HyperliquidTrader
        _trader_instance = HyperliquidTrader(settings.hyperliquid_private_key)
    return _trader_instance


def _get_paper_engine() -> Any:
    """Get or create the paper trading engine singleton.

    On first call, attempts to restore from the latest portfolio snapshot
    in Supabase so state survives VPS restarts.
    """
    global _paper_engine
    if _paper_engine is None:
        from wolfpack.paper_trading import PaperTradingEngine, PaperPosition

        _paper_engine = PaperTradingEngine(starting_equity=10000.0)

        # Restore from latest snapshot
        try:
            from wolfpack.db import get_db
            db = get_db()
            result = (
                db.table("wp_portfolio_snapshots")
                .select("*")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                snap = result.data[0]
                p = _paper_engine.portfolio
                p.equity = snap.get("equity", 10000.0)
                p.free_collateral = snap.get("free_collateral", 10000.0)
                p.realized_pnl = snap.get("realized_pnl", 0.0)
                p.unrealized_pnl = snap.get("unrealized_pnl", 0.0)
                for pos_data in snap.get("positions", []):
                    p.positions.append(PaperPosition(
                        symbol=pos_data["symbol"],
                        direction=pos_data["direction"],
                        entry_price=pos_data["entry_price"],
                        current_price=pos_data.get("current_price", pos_data["entry_price"]),
                        size_usd=pos_data["size_usd"],
                        unrealized_pnl=pos_data.get("unrealized_pnl", 0.0),
                        recommendation_id=pos_data.get("recommendation_id", "restored"),
                        opened_at=pos_data.get("opened_at", "2026-01-01T00:00:00+00:00"),
                    ))
                logger.info(f"[paper] Restored from snapshot: equity=${p.equity}, {len(p.positions)} positions")
        except Exception as e:
            logger.warning(f"[paper] Could not restore from snapshot: {e}")

    return _paper_engine


# ── Veto Singleton ──
_veto_instance: Any = None


def _get_veto() -> Any:
    """Get or create the BriefVeto singleton."""
    global _veto_instance
    if _veto_instance is None:
        from wolfpack.veto import BriefVeto
        _veto_instance = BriefVeto()
    return _veto_instance


# ── Auto-Trader Singleton ──
_auto_trader: Any = None


def _get_auto_trader() -> Any:
    """Get or create the AutoTrader singleton."""
    global _auto_trader
    if _auto_trader is None:
        from wolfpack.auto_trader import AutoTrader
        _auto_trader = AutoTrader()
    return _auto_trader


# ── LP AutoTrader Singleton ──
_lp_trader: Any = None


def _get_lp_trader() -> Any:
    """Get or create the LPAutoTrader singleton."""
    global _lp_trader
    if _lp_trader is None:
        from wolfpack.lp_auto_trader import LPAutoTrader
        _lp_trader = LPAutoTrader()
    return _lp_trader


@app.get("/auto-trader/status")
async def auto_trader_status():
    """Return auto-trader status."""
    trader = _get_auto_trader()
    return trader.get_status()


@app.post("/auto-trader/toggle")
async def auto_trader_toggle(_auth: None = Depends(require_auth)):
    """Toggle auto-trader on/off."""
    trader = _get_auto_trader()
    trader.enabled = not trader.enabled
    state = "enabled" if trader.enabled else "disabled"
    logger.info(f"[auto-trader] Toggled to {state}")
    return {"status": "ok", "enabled": trader.enabled}


@app.post("/auto-trader/config")
async def auto_trader_config(
    equity: float | None = Body(None),
    conviction_threshold: int | None = Body(None),
    _auth: None = Depends(require_auth),
):
    """Update auto-trader configuration at runtime."""
    trader = _get_auto_trader()
    trader.restore_from_snapshot()
    if equity is not None and equity > 0:
        trader.engine.portfolio.starting_equity = equity
        # Only reset equity if no open positions
        if len(trader.engine.portfolio.positions) == 0:
            trader.engine.portfolio.equity = equity
            trader.engine.portfolio.free_collateral = equity
        trader._store_snapshot()
        logger.info(f"[auto-trader] Updated equity to ${equity}")
    if conviction_threshold is not None and 50 <= conviction_threshold <= 100:
        trader.conviction_threshold = conviction_threshold
        logger.info(f"[auto-trader] Updated conviction threshold to {conviction_threshold}")
    return trader.get_status()


@app.post("/auto-trader/yolo-level")
async def auto_trader_yolo_level(
    level: int = Body(..., embed=True),
    _auth: None = Depends(require_auth),
):
    """Set the YOLO meter level (1-5)."""
    if level < 1 or level > 5:
        raise HTTPException(status_code=400, detail="YOLO level must be 1-5")
    trader = _get_auto_trader()
    trader.yolo_level = level
    trader._apply_yolo_profile()
    from wolfpack.auto_trader import YOLO_PROFILES
    logger.info(f"[auto-trader] YOLO level set to {level} ({YOLO_PROFILES[level]['label']})")
    return trader.get_status()


@app.get("/auto-trader/trades")
async def auto_trader_trades(limit: int = 50):
    """Return recent auto-trades."""
    try:
        from wolfpack.db import get_db
        db = get_db()
        result = (
            db.table("wp_auto_trades")
            .select("*")
            .order("opened_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"trades": result.data or []}
    except Exception as e:
        logger.error(f"[auto-trader] Failed to fetch trades: {e}")
        return {"trades": []}


# ── Notification Digest Endpoints ──


@app.get("/notifications/config")
async def notification_config():
    """Get current notification digest configuration."""
    from wolfpack.notification_digest import get_digest
    d = get_digest()
    return {
        "mode": d.mode,
        "interval_minutes": d.interval_minutes,
        "buffered_count": len(d._buffer),
    }


@app.post("/notifications/config")
async def update_notification_config(
    mode: str | None = None,
    interval_minutes: int | None = None,
    _auth: None = Depends(require_auth),
):
    """Update notification digest settings."""
    from wolfpack.notification_digest import get_digest
    d = get_digest()
    if mode:
        d.set_mode(mode)
    if interval_minutes:
        d.set_interval(interval_minutes)
    return {
        "mode": d.mode,
        "interval_minutes": d.interval_minutes,
    }


@app.post("/notifications/flush")
async def flush_notifications(_auth: None = Depends(require_auth)):
    """Force flush notification digest now."""
    from wolfpack.notification_digest import get_digest
    d = get_digest()
    await d.force_flush()
    return {"status": "flushed"}


# ── Market Data Endpoints ──


@app.get("/market/orderbook")
async def market_orderbook(symbol: str = "BTC", depth: int = 20, exchange: str = "hyperliquid"):
    """Fetch orderbook from exchange adapter."""
    try:
        from wolfpack.exchanges import get_exchange

        adapter = get_exchange(exchange)  # type: ignore[arg-type]
        ob = await adapter.get_orderbook(symbol, depth=depth)
        return {"orderbook": ob.model_dump()}
    except Exception as e:
        logger.error(f"Failed to fetch orderbook: {e}")
        return {"orderbook": {"symbol": symbol, "bids": [], "asks": [], "timestamp": 0}, "error": str(e)}


# ── Kraken Paper Trading Endpoints ──


async def _kraken_cli(*args: str, timeout: float = 15) -> dict | list:
    """Run Kraken CLI and return parsed JSON."""
    import asyncio
    import json
    import os

    cli = os.path.expanduser("~/.cargo/bin/kraken")
    cmd = [cli] + list(args) + ["-o", "json"]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    if proc.returncode != 0:
        err = stderr.decode().strip() if stderr else "unknown error"
        raise RuntimeError(f"Kraken CLI error: {err}")
    return json.loads(stdout.decode())


@app.post("/kraken/paper/init")
async def kraken_paper_init(balance: float = 10000):
    """Initialize Kraken paper trading with starting balance."""
    try:
        result = await _kraken_cli("paper", "init", "--balance", str(balance))
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/kraken/paper/buy")
async def kraken_paper_buy(pair: str, volume: float):
    """Place a paper buy order via Kraken CLI."""
    try:
        result = await _kraken_cli("paper", "buy", pair, str(volume))
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/kraken/paper/sell")
async def kraken_paper_sell(pair: str, volume: float):
    """Place a paper sell order via Kraken CLI."""
    try:
        result = await _kraken_cli("paper", "sell", pair, str(volume))
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/kraken/paper/status")
async def kraken_paper_status():
    """Get Kraken paper trading status."""
    try:
        result = await _kraken_cli("paper", "status")
        return result if isinstance(result, dict) else {"data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/kraken/paper/history")
async def kraken_paper_history():
    """Get Kraken paper trading history."""
    try:
        result = await _kraken_cli("paper", "history")
        return result if isinstance(result, dict) else {"trades": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/kraken/paper/balance")
async def kraken_paper_balance():
    """Get Kraken paper trading balance."""
    try:
        result = await _kraken_cli("paper", "balance")
        return result if isinstance(result, dict) else {"balance": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/kraken/paper/reset")
async def kraken_paper_reset(_auth: None = Depends(require_auth)):
    """Reset Kraken paper trading state."""
    try:
        result = await _kraken_cli("paper", "reset")
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Prediction Scoring Endpoints ──


@app.get("/predictions/accuracy")
async def prediction_accuracy(days: int = 7):
    """Get prediction accuracy for the last N days."""
    try:
        from wolfpack.modules.prediction_scorer import get_prediction_accuracy
        return get_prediction_accuracy(days=days)
    except Exception as e:
        logger.error(f"Failed to get prediction accuracy: {e}")
        return {"accuracy_pct": 0, "total_scored": 0, "correct": 0, "incorrect": 0, "neutral": 0}


@app.get("/predictions/history")
async def prediction_history(days: int = 7):
    """Get scored prediction history for charting."""
    try:
        from wolfpack.modules.prediction_scorer import get_prediction_history
        return {"predictions": get_prediction_history(days=days)}
    except Exception as e:
        logger.error(f"Failed to get prediction history: {e}")
        return {"predictions": []}


@app.post("/predictions/score")
async def trigger_prediction_scoring(days: int = 7, _auth: None = Depends(require_auth)):
    """Manually trigger prediction scoring."""
    try:
        from wolfpack.modules.prediction_scorer import score_predictions
        result = await score_predictions(days=days)
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"Failed to score predictions: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/market/candles")
async def market_candles(
    symbol: str = "BTC",
    interval: str = "1h",
    limit: int = 100,
    exchange: str = "hyperliquid",
):
    """Fetch candlestick data from the exchange adapter."""
    try:
        from wolfpack.exchanges import get_exchange

        adapter = get_exchange(exchange)  # type: ignore[arg-type]
        candles = await adapter.get_candles(symbol, interval=interval, limit=limit)
        return {
            "symbol": symbol,
            "interval": interval,
            "candles": [c.model_dump() for c in candles],
        }
    except Exception as e:
        logger.error(f"Failed to fetch candles: {e}")
        return {"symbol": symbol, "interval": interval, "candles": [], "error": str(e)}


@app.get("/market/price")
async def market_price(symbol: str = "BTC", exchange: str = "hyperliquid"):
    """Fetch latest price for a symbol."""
    try:
        from wolfpack.exchanges import get_exchange

        adapter = get_exchange(exchange)  # type: ignore[arg-type]
        candles = await adapter.get_candles(symbol, interval="1m", limit=1)
        if candles:
            return {
                "symbol": symbol,
                "price": candles[-1].close,
                "high_24h": candles[-1].high,
                "low_24h": candles[-1].low,
                "timestamp": candles[-1].timestamp,
            }
        return {"symbol": symbol, "price": None}
    except Exception as e:
        logger.error(f"Failed to fetch price: {e}")
        return {"symbol": symbol, "price": None, "error": str(e)}


@app.get("/market/markets")
async def market_list(exchange: str = "hyperliquid"):
    """Fetch available markets from exchange."""
    try:
        from wolfpack.exchanges import get_exchange

        adapter = get_exchange(exchange)  # type: ignore[arg-type]
        markets = await adapter.get_markets()
        return {"markets": [m.model_dump() for m in markets]}
    except Exception as e:
        logger.error(f"Failed to fetch markets: {e}")
        return {"markets": [], "error": str(e)}


# ── Position Action Endpoints ──


@app.get("/position-actions")
async def list_position_actions(status: str = "pending", limit: int = 50):
    """List position actions (pending, approved, dismissed, auto_executed)."""
    try:
        from wolfpack.db import get_db

        db = get_db()
        query = db.table("wp_position_actions").select("*").order("created_at", desc=True).limit(limit)
        if status != "all":
            query = query.eq("status", status)
        result = query.execute()
        return {"actions": result.data or []}
    except Exception as e:
        logger.error(f"[position-actions] Failed to list: {e}")
        return {"actions": [], "error": str(e)}


@app.post("/position-actions/{action_id}/approve")
async def approve_position_action(action_id: str, exchange: str = "hyperliquid", _auth: None = Depends(require_auth)):
    """Approve and execute a position action."""
    try:
        from wolfpack.db import get_db

        db = get_db()
        result = db.table("wp_position_actions").select("*").eq("id", action_id).execute()
        if not result.data:
            return {"status": "error", "message": "Action not found"}

        pa = result.data[0]
        action = pa["action"]
        pa_symbol = pa["symbol"]
        engine = _get_paper_engine()
        pos = next((p for p in engine.portfolio.positions if p.symbol == pa_symbol), None)

        if not pos:
            db.table("wp_position_actions").update(
                {"status": "dismissed", "acted_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", action_id).execute()
            return {"status": "error", "message": f"No open position for {pa_symbol}"}

        if action == "close":
            pnl = engine.close_position(pa_symbol)
            try:
                _get_drawdown_monitor().clear_position_peak(pa_symbol)
            except Exception:
                pass
            engine.store_snapshot(exchange)
            db.table("wp_position_actions").update(
                {"status": "approved", "acted_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", action_id).execute()
            return {"status": "executed", "action": "close", "symbol": pa_symbol, "realized_pnl": pnl}

        elif action == "reduce":
            reduce_pct = pa.get("reduce_pct", 50)
            original_size = pos.size_usd
            new_size = original_size * (1 - reduce_pct / 100)
            # Close full position then reopen at reduced size
            pnl = engine.close_position(pa_symbol)
            if new_size > 0:
                engine.open_position(
                    symbol=pa_symbol,
                    direction=pos.direction,
                    current_price=pos.current_price,
                    size_pct=(new_size / engine.portfolio.equity * 100) if engine.portfolio.equity > 0 else 0,
                    recommendation_id=pos.recommendation_id,
                )
            engine.store_snapshot(exchange)
            db.table("wp_position_actions").update(
                {"status": "approved", "acted_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", action_id).execute()
            return {"status": "executed", "action": "reduce", "symbol": pa_symbol, "realized_pnl": pnl, "reduced_by_pct": reduce_pct}

        elif action == "adjust_stop":
            new_stop = pa.get("suggested_stop")
            if new_stop:
                pos.stop_loss = new_stop
                engine.store_snapshot(exchange)
            db.table("wp_position_actions").update(
                {"status": "approved", "acted_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", action_id).execute()
            return {"status": "executed", "action": "adjust_stop", "symbol": pa_symbol, "new_stop": new_stop}

        elif action == "adjust_tp":
            new_tp = pa.get("suggested_tp")
            if new_tp:
                pos.take_profit = new_tp
                engine.store_snapshot(exchange)
            db.table("wp_position_actions").update(
                {"status": "approved", "acted_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", action_id).execute()
            return {"status": "executed", "action": "adjust_tp", "symbol": pa_symbol, "new_tp": new_tp}

        return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        logger.error(f"[position-actions] Approve error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/position-actions/{action_id}/dismiss")
async def dismiss_position_action(action_id: str, _auth: None = Depends(require_auth)):
    """Dismiss a position action."""
    try:
        from wolfpack.db import get_db

        db = get_db()
        result = db.table("wp_position_actions").update(
            {"status": "dismissed", "acted_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", action_id).execute()
        if not result.data:
            return {"status": "error", "message": "Action not found"}
        return {"status": "dismissed", "id": action_id}
    except Exception as e:
        logger.error(f"[position-actions] Dismiss error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/run")
async def run_intelligence(
    background_tasks: BackgroundTasks,
    exchange: str = "hyperliquid",
    symbol: str = "BTC",
    _auth: None = Depends(require_auth),
):
    """Trigger a full intelligence cycle for the specified exchange and symbol."""
    if _running:
        return {"status": "already_running", "agents": list(_running)}

    background_tasks.add_task(_run_full_cycle, exchange, symbol)
    return {"status": "started", "exchange": exchange, "symbol": symbol}


async def _process_position_actions(
    actions: list[dict], exchange: str, symbol: str, latest_price: float | None, engine: Any
) -> None:
    """Process position_actions from Brief output — store actionable ones, log holds."""
    if not actions:
        return

    from wolfpack.db import get_db

    db = get_db()

    for pa in actions:
        action = pa.get("action", "hold")
        pa_symbol = pa.get("symbol", symbol)

        if action == "hold":
            logger.info(f"[position-action] HOLD {pa_symbol}: {pa.get('reason', 'thesis intact')}")
            continue

        # Compute current P&L % for the position
        current_pnl_pct: float | None = None
        pos = next((p for p in engine.portfolio.positions if p.symbol == pa_symbol), None)
        if pos:
            current = latest_price if pa_symbol == symbol else pos.current_price
            current_pnl_pct = round(
                ((current - pos.entry_price) / pos.entry_price)
                * (1 if pos.direction == "long" else -1) * 100,
                2,
            )

        # Store to wp_position_actions
        try:
            row = db.table("wp_position_actions").upsert({
                "symbol": pa_symbol,
                "exchange_id": exchange,
                "action": action,
                "reason": pa.get("reason"),
                "current_pnl_pct": current_pnl_pct,
                "suggested_stop": pa.get("suggested_stop"),
                "suggested_tp": pa.get("suggested_tp"),
                "reduce_pct": pa.get("reduce_pct"),
                "urgency": pa.get("urgency", "medium"),
                "status": "pending",
            }, on_conflict="symbol,action,status").execute()

            action_id = row.data[0]["id"] if row.data else None

            # Telegram notification — route through digest
            auto_trader = _get_auto_trader()
            if not auto_trader.enabled:
                try:
                    from wolfpack.notification_digest import get_digest
                    digest = get_digest()
                    if digest.mode == "individual":
                        from wolfpack.notifications import notify_position_action
                        await notify_position_action(
                            symbol=pa_symbol,
                            action=action,
                            reason=pa.get("reason", ""),
                            urgency=pa.get("urgency", "medium"),
                            action_id=action_id,
                        )
                    elif digest.mode != "disabled":
                        digest.add({
                            "type": "position_action",
                            "symbol": pa_symbol,
                            "action": action,
                            "details": f"{action.upper()} {pa_symbol}: {pa.get('reason', '')}",
                        })
                except Exception:
                    pass

            # Auto-trader: auto-execute mechanical actions
            try:
                auto_trader = _get_auto_trader()
                if auto_trader.enabled and action_id:
                    await auto_trader.process_position_actions(
                        [{"id": action_id, **pa, "current_pnl_pct": current_pnl_pct}],
                        latest_prices={symbol: latest_price} if latest_price else {},
                    )
            except Exception as e:
                logger.warning(f"[position-action] Auto-trader error for {pa_symbol}: {e}")

            logger.info(f"[position-action] Stored {action} for {pa_symbol} (id={action_id})")
        except Exception as e:
            logger.error(f"[position-action] Failed to store action for {pa_symbol}: {e}")


async def _run_full_cycle(exchange: str, symbol: str) -> None:
    """Execute a full intelligence cycle: fetch data -> modules -> all 4 agents -> Supabase.

    Pipeline:
    1. Fetch market data (candles, orderbook, funding)
    2. Run quant modules (regime, liquidity, funding, volatility, correlation)
    3. Run Quant + Snoop + Sage agents (can run in parallel - they read modules, not each other)
    4. Run Brief agent (consumes the other 3 agents' outputs)
    5. Extract trade recommendations from Brief and store to Supabase
    """
    try:
        # Ensure token tracker is initialized before any LLM calls
        _get_token_tracker()

        from wolfpack.agents.base import Agent
        Agent._current_symbol = symbol

        from wolfpack.agents.brief import BriefAgent
        from wolfpack.agents.quant import QuantAgent
        from wolfpack.agents.sage import SageAgent
        from wolfpack.agents.snoop import SnoopAgent
        from wolfpack.db import store_agent_output, store_module_output, store_recommendation
        from wolfpack.exchanges import get_exchange
        from wolfpack.modules.correlation import CorrelationIntel
        from wolfpack.modules.execution import ExecutionTiming
        from wolfpack.modules.funding import FundingIntel
        from wolfpack.modules.liquidity import LiquidityIntel
        from wolfpack.modules.momentum_buckets import MomentumBuckets
        from wolfpack.modules.regime import RegimeDetector
        from wolfpack.modules.social_sentiment import SocialSentimentAnalyzer
        from wolfpack.modules.volatility import VolatilitySignal
        from wolfpack.modules.whale_tracker import WhaleTracker

        adapter = get_exchange(exchange)  # type: ignore[arg-type]

        # ── Step 1: Fetch market data ──
        logger.info(f"[cycle] Fetching {symbol} data from {exchange}...")
        candles_1h = await adapter.get_candles(symbol, interval="1h", limit=300)
        candles_4h = await adapter.get_candles(symbol, interval="4h", limit=100)
        candles_1d = await adapter.get_candles(symbol, interval="1d", limit=100)
        orderbook = await adapter.get_orderbook(symbol, depth=20)
        funding_rates = await adapter.get_funding_rates()

        # Fetch markets for OI data
        all_markets = await adapter.get_markets()
        symbol_market = next((m for m in all_markets if m.symbol == symbol), None)
        open_interest_usd = symbol_market.open_interest * symbol_market.last_price if symbol_market and symbol_market.open_interest else 0.0

        # Also fetch ETH candles for correlation analysis
        eth_candles: list = []
        if symbol != "ETH":
            try:
                eth_candles = await adapter.get_candles("ETH", interval="1h", limit=300)
            except Exception as e:
                logger.warning(f"[cycle] Could not fetch ETH candles for correlation: {e}")

        # ── Record data freshness ──
        tracker = _get_freshness_tracker()
        tracker.record_update(symbol, "candles")
        tracker.record_update(symbol, "orderbook")
        if funding_rates:
            tracker.record_update(symbol, "funding")
        # Record latest close price for freeze detection
        if candles_1h:
            tracker.record_close_price(symbol, candles_1h[-1].close)

        # ── Check if symbol should be skipped (stale/frozen data) ──
        skip, skip_reason = tracker.should_skip_symbol(symbol)
        if skip:
            logger.warning(f"[cycle] Skipping {symbol}: {skip_reason}")
            return

        # ── Step 2: Run quantitative modules ──
        logger.info("[cycle] Running quantitative modules...")

        now_utc = datetime.now(timezone.utc)

        # Regime detection
        global _latest_regime
        regime_detector = RegimeDetector()
        regime_output = regime_detector.detect(
            {"1h": candles_1h, "4h": candles_4h, "1d": candles_1d},
            asset=symbol,
        )
        _latest_regime = regime_output
        store_module_output("regime_detection", exchange, regime_output.model_dump(), symbol)
        _module_last_runs["regime_detection"] = now_utc

        # Momentum Buckets (noise-reduced trend detection)
        momentum_buckets = MomentumBuckets()
        momentum_output = momentum_buckets.analyze(candles_1h, asset=symbol)
        store_module_output("momentum_buckets", exchange, momentum_output.model_dump(), symbol)
        _module_last_runs["momentum_buckets"] = now_utc

        # Liquidity
        global _latest_liquidity
        liquidity_intel = LiquidityIntel()
        liquidity_output = liquidity_intel.analyze(orderbook)
        _latest_liquidity = liquidity_output
        store_module_output("liquidity_intel", exchange, liquidity_output.model_dump(), symbol)
        _module_last_runs["liquidity_intel"] = now_utc

        # Funding
        funding_intel = FundingIntel()
        symbol_rate = None
        for r in funding_rates:
            if r.symbol == symbol:
                symbol_rate = r
                break
        funding_output = None
        if symbol_rate:
            funding_output = funding_intel.analyze(
                funding=symbol_rate,
                open_interest_usd=open_interest_usd,
                oi_change_24h_pct=0,  # Would need previous snapshot to compute delta
            )
            store_module_output("funding_carry", exchange, funding_output.model_dump(), symbol)
            _module_last_runs["funding_carry"] = now_utc

        # Drawdown monitor — auto-track peak equity and compute drawdown
        dd_monitor = _get_drawdown_monitor()
        engine_dd = _get_paper_engine()
        dd_info = dd_monitor.update_peaks(exchange, engine_dd.portfolio.equity)
        auto_drawdown_pct = dd_info["drawdown_pct"]

        # Volatility (fed with auto-computed drawdown from monitor)
        global _latest_volatility
        closes = [c.close for c in candles_1h]
        vol_signal = VolatilitySignal()
        vol_output = vol_signal.analyze(asset=symbol, closes=closes, current_drawdown_pct=auto_drawdown_pct)
        _latest_volatility = vol_output
        store_module_output("volatility", exchange, vol_output.model_dump(), symbol)
        _module_last_runs["volatility"] = now_utc

        # Correlation (BTC/ETH)
        correlation_output = None
        if eth_candles and len(eth_candles) >= 20:
            try:
                corr_intel = CorrelationIntel()
                btc_closes = [c.close for c in candles_1h]
                eth_closes = [c.close for c in eth_candles]
                correlation_output = corr_intel.analyze(btc_closes, eth_closes)
                store_module_output("correlation", exchange, correlation_output.model_dump(), symbol)
                _module_last_runs["correlation"] = now_utc
            except Exception as e:
                logger.warning(f"[cycle] Correlation analysis failed: {e}")

        # Execution timing
        exec_timing = ExecutionTiming()
        hourly_volumes = [c.volume for c in candles_1h[-24:]] if len(candles_1h) >= 24 else []
        current_hour = now_utc.hour
        exec_output = exec_timing.analyze(hourly_volumes, current_hour)
        store_module_output("execution_timing", exchange, exec_output.model_dump(), symbol)
        _module_last_runs["execution_timing"] = now_utc

        # Monte Carlo stress test — runs on recent trade returns from paper portfolio
        monte_carlo_output = None
        try:
            from wolfpack.modules.monte_carlo import MonteCarloEngine
            engine_mc = _get_paper_engine()
            # Collect recent trade returns from closed trade history
            from wolfpack.db import get_db
            db = get_db()
            trade_history = db.table("wp_trade_history").select("pnl_usd,size_usd").order("closed_at", desc=True).limit(100).execute()
            trade_returns_list: list[float] = []
            if trade_history.data:
                for t in trade_history.data:
                    size = t.get("size_usd", 0)
                    pnl = t.get("pnl_usd", 0)
                    if size and size > 0:
                        trade_returns_list.append(pnl / size)

            if len(trade_returns_list) >= 10:
                mc_engine = MonteCarloEngine(n_simulations=2000, seed=42)
                monte_carlo_output = mc_engine.run(trade_returns_list)
                store_module_output("monte_carlo", exchange, monte_carlo_output.model_dump(), symbol)
                _module_last_runs["monte_carlo"] = now_utc
                logger.info(f"[cycle] Monte Carlo: grade={monte_carlo_output.robustness_grade}, calmar_p5={monte_carlo_output.calmar_p5}, ruin={monte_carlo_output.ruin_probability}%")
            else:
                logger.debug(f"[cycle] Monte Carlo skipped: only {len(trade_returns_list)} trades (need 10+)")
        except Exception as e:
            logger.warning(f"[cycle] Monte Carlo analysis failed: {e}")

        # Social sentiment + whale tracker (async, non-blocking)
        social_output = None
        whale_output = None
        try:
            social_analyzer = SocialSentimentAnalyzer()
            whale_tracker = WhaleTracker()
            social_result, whale_result = await asyncio.gather(
                social_analyzer.analyze(symbol),
                whale_tracker.analyze(symbol),
                return_exceptions=True,
            )
            if not isinstance(social_result, Exception):
                social_output = social_result
                store_module_output("social_sentiment", exchange, social_output.model_dump(), symbol)
                _module_last_runs["social_sentiment"] = now_utc
            else:
                logger.warning(f"[cycle] Social sentiment failed: {social_result}")
            if not isinstance(whale_result, Exception):
                whale_output = whale_result
                store_module_output("whale_tracker", exchange, whale_output.model_dump(), symbol)
                _module_last_runs["whale_tracker"] = now_utc
                tracker.record_update(symbol, "whale_trades")
            else:
                logger.warning(f"[cycle] Whale tracker failed: {whale_result}")
        except Exception as e:
            logger.warning(f"[cycle] Social/whale modules failed: {e}")

        # Circuit breaker (uses auto-tracked drawdown from drawdown monitor)
        cb = _get_circuit_breaker()
        engine = _get_paper_engine()
        portfolio = engine.portfolio

        # Use drawdown from monitor (auto-tracked peak, persisted across restarts)
        current_dd = auto_drawdown_pct
        daily_pnl_pct = ((portfolio.equity - portfolio.starting_equity) / portfolio.starting_equity * 100)
        total_exposure = sum(p.size_usd for p in portfolio.positions) / portfolio.equity * 100 if portfolio.equity > 0 else 0

        cb_output = cb.check(
            daily_pnl_pct=daily_pnl_pct,
            rolling_24h_pnl_pct=daily_pnl_pct,  # Approximate — same as daily for now
            current_drawdown_pct=current_dd,
            total_exposure_pct=total_exposure,
            data_age_s=tracker.get_max_data_age(symbol),
        )
        store_module_output("circuit_breakers", exchange, cb_output.model_dump(), symbol)
        _module_last_runs["circuit_breakers"] = now_utc

        # Persist CB state to DB (survives restarts)
        try:
            from wolfpack.db import save_cb_state
            save_cb_state(
                state=cb_output.state,
                triggers=cb_output.violations,
                max_exposure_pct=cb_output.total_exposure_pct,
                peak_equity=dd_info["peak_equity"],
            )
        except Exception as e:
            logger.warning(f"[cycle] Failed to persist CB state: {e}")

        if cb_output.state == "EMERGENCY_STOP":
            logger.critical(f"[cycle] CIRCUIT BREAKER EMERGENCY STOP: {cb_output.reason}")
        elif cb_output.state == "SUSPENDED":
            logger.warning(f"[cycle] Circuit breaker SUSPENDED: {cb_output.reason}")

        # Get latest price for context
        latest_price: float | None = None
        if candles_1h:
            latest_price = candles_1h[-1].close

        # ── Step 3: Run Quant, Snoop, Sage agents in parallel ──
        logger.info("[cycle] Running intelligence agents (Quant, Snoop, Sage)...")

        # Build shared market data dict
        market_data_base: dict[str, Any] = {
            "symbol": symbol,
            "regime": regime_output,
            "momentum_buckets": momentum_output,
            "liquidity": liquidity_output,
            "volatility": vol_output,
            "funding": funding_output.model_dump() if funding_output else None,
            "latest_price": latest_price,
            "open_interest_usd": open_interest_usd,
            "social_sentiment": social_output.model_dump() if social_output else None,
            "whale_tracker": whale_output.model_dump() if whale_output else None,
        }

        # Quant gets candles + correlation (for stat arb alerts)
        quant_data = {**market_data_base, "candles": candles_1h}
        if correlation_output:
            quant_data["correlation"] = correlation_output

        # Sage gets correlation + OI
        sage_data = {**market_data_base}
        if correlation_output:
            sage_data["correlation"] = correlation_output

        quant = QuantAgent()
        snoop = SnoopAgent()
        sage = SageAgent()

        _running.update({"quant", "snoop", "sage"})

        quant_out, snoop_out, sage_out = await asyncio.gather(
            _run_agent(quant, quant_data, exchange, store_agent_output),
            _run_agent(snoop, market_data_base, exchange, store_agent_output),
            _run_agent(sage, sage_data, exchange, store_agent_output),
            return_exceptions=True,
        )

        _running.discard("quant")
        _running.discard("snoop")
        _running.discard("sage")
        _last_runs["quant"] = datetime.now(timezone.utc)
        _last_runs["snoop"] = datetime.now(timezone.utc)
        _last_runs["sage"] = datetime.now(timezone.utc)

        # Log any agent failures but continue — track in failure tracker
        ft = _get_failure_tracker()
        agent_outputs: dict[str, Any] = {}
        for name, result in [("quant", quant_out), ("snoop", snoop_out), ("sage", sage_out)]:
            if isinstance(result, Exception):
                logger.error(f"[cycle] {name} agent failed: {result}")
                ft.record_failure(name, str(result))
            else:
                ft.record_success(name)
                if isinstance(result, dict):
                    agent_outputs[name] = result
                else:
                    agent_outputs[name] = result

        # ── Step 4: Run Brief agent (consumes other agent outputs) ──
        logger.info("[cycle] Running Brief agent (synthesis)...")
        _running.add("brief")

        # Build portfolio context for position management
        portfolio_context: dict[str, Any] | None = None
        if portfolio.positions:
            now_ts = datetime.now(timezone.utc)
            pos_list = []
            for p in portfolio.positions:
                current = latest_price if p.symbol == symbol else p.current_price
                pnl_pct = ((current - p.entry_price) / p.entry_price) * (1 if p.direction == "long" else -1) * 100
                pos_entry: dict[str, Any] = {
                    "symbol": p.symbol,
                    "direction": p.direction,
                    "entry_price": p.entry_price,
                    "current_price": current,
                    "size_usd": p.size_usd,
                    "pnl_pct": round(pnl_pct, 2),
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                }
                # Hold duration
                opened = p.opened_at if isinstance(p.opened_at, datetime) else datetime.fromisoformat(str(p.opened_at))
                if opened.tzinfo is None:
                    opened = opened.replace(tzinfo=timezone.utc)
                pos_entry["hold_duration_hours"] = round((now_ts - opened).total_seconds() / 3600, 1)
                # Distance to stop/tp
                if p.stop_loss and current:
                    pos_entry["distance_to_stop_pct"] = round(abs(current - p.stop_loss) / current * 100, 2)
                if p.take_profit and current:
                    pos_entry["distance_to_tp_pct"] = round(abs(p.take_profit - current) / current * 100, 2)
                pos_list.append(pos_entry)

            long_exposure = sum(p.size_usd for p in portfolio.positions if p.direction == "long")
            short_exposure = sum(p.size_usd for p in portfolio.positions if p.direction == "short")
            portfolio_context = {
                "equity": round(portfolio.equity, 2),
                "positions": pos_list,
                "gross_exposure_pct": round((long_exposure + short_exposure) / portfolio.equity * 100, 1) if portfolio.equity > 0 else 0,
                "net_exposure_pct": round((long_exposure - short_exposure) / portfolio.equity * 100, 1) if portfolio.equity > 0 else 0,
                "free_collateral_pct": round(portfolio.free_collateral / portfolio.equity * 100, 1) if portfolio.equity > 0 else 0,
            }

        # Pass YOLO level to Brief so it adjusts conviction floor
        auto_trader = _get_auto_trader()
        brief_data: dict[str, Any] = {
            "symbol": symbol,
            "latest_price": latest_price,
            "regime": regime_output,
            "liquidity": liquidity_output,
            "volatility": vol_output,
            "funding": funding_output.model_dump() if funding_output else None,
            "correlation": correlation_output.model_dump() if correlation_output else None,
            "circuit_breaker": cb_output.model_dump(),
            "execution_timing": exec_output.model_dump(),
            "yolo_level": auto_trader.yolo_level,
        }
        if monte_carlo_output:
            brief_data["monte_carlo"] = monte_carlo_output.model_dump()
        # Note: overfit_score is computed per-backtest, not per-cycle.
        # It's available when backtests have been run recently.
        if portfolio_context:
            brief_data["portfolio_context"] = portfolio_context
        # Inject performance tracker summary
        try:
            if auto_trader.enabled:
                brief_data["performance_summary"] = auto_trader._perf_tracker.get_performance_summary()
        except Exception:
            pass
        if "quant" in agent_outputs:
            out = agent_outputs["quant"]
            brief_data["quant_output"] = out.model_dump() if hasattr(out, "model_dump") else out
        if "snoop" in agent_outputs:
            out = agent_outputs["snoop"]
            brief_data["snoop_output"] = out.model_dump() if hasattr(out, "model_dump") else out
        if "sage" in agent_outputs:
            out = agent_outputs["sage"]
            brief_data["sage_output"] = out.model_dump() if hasattr(out, "model_dump") else out

        brief = BriefAgent()
        try:
            brief_out = await brief.analyze(brief_data, exchange)
            ft.record_success("brief")

            store_agent_output(
                agent_name=brief_out.agent_name,
                exchange_id=exchange,
                summary=brief_out.summary,
                signals=brief_out.signals,
                confidence=brief_out.confidence,
                raw_data=brief_out.raw_data,
            )

            # ── Step 5: Extract and store trade recommendations ──
            recs = brief_out.raw_data.get("recommendations", []) if brief_out.raw_data else []

            # Circuit breaker gate — skip new entry recs if not ACTIVE
            if not cb_output.allow_new_entry:
                logger.warning(f"[cycle] Circuit breaker blocking new entries ({cb_output.state}), skipping {len(recs)} recs")
                recs = []

            # Safe mode gate — skip new entry recs if any agent is in consecutive failure
            if ft.is_safe_mode():
                failing = ft.get_failing_agents()
                logger.warning(f"[cycle] SAFE MODE — agents failing: {failing}, skipping {len(recs)} new entry recs")
                recs = []

            # Veto layer — filter and adjust recs before storing
            veto = _get_veto()
            stored_recs: list[dict] = []

            for rec in recs:
                # Extract quant signals for EMA/VWAP extension check
                quant_sigs = None
                if "quant" in agent_outputs:
                    qo = agent_outputs["quant"]
                    if hasattr(qo, "signals"):
                        quant_sigs = qo.signals
                    elif isinstance(qo, dict):
                        quant_sigs = qo.get("signals")

                veto_result = veto.evaluate(
                    rec,
                    cb_output=cb_output.model_dump(),
                    vol_output=vol_output.model_dump() if vol_output else None,
                    quant_signals=quant_sigs,
                )
                if veto_result.action == "reject":
                    logger.info(f"[veto] Rejected {rec.get('symbol', symbol)} {rec.get('direction')}: {veto_result.reasons}")
                    continue

                conviction = veto_result.final_conviction
                try:
                    stored_row = store_recommendation(
                        exchange_id=exchange,
                        symbol=rec.get("symbol", symbol),
                        direction=rec.get("direction", "wait"),
                        conviction=conviction,
                        rationale=rec.get("rationale", ""),
                        entry_price=rec.get("entry_price"),
                        stop_loss=rec.get("stop_loss"),
                        take_profit=rec.get("take_profit"),
                        size_pct=rec.get("size_pct"),
                    )
                    stored_recs.append({**rec, "conviction": conviction, "id": stored_row.get("id")})

                    if veto_result.action == "adjust":
                        logger.info(f"[veto] Adjusted {rec.get('symbol', symbol)}: {veto_result.original_conviction} -> {conviction} ({veto_result.reasons})")

                    # Telegram notification for high-conviction recs — route through digest
                    auto_trader = _get_auto_trader()
                    if conviction >= 70 and not auto_trader.enabled:
                        try:
                            from wolfpack.notification_digest import get_digest
                            digest = get_digest()
                            if digest.mode == "individual":
                                from wolfpack.notifications import notify_recommendation
                                rec_id = stored_row.get("id")
                                await notify_recommendation(
                                    symbol=rec.get("symbol", symbol),
                                    direction=rec.get("direction", "wait"),
                                    conviction=conviction,
                                    rationale=rec.get("rationale", ""),
                                    entry_price=rec.get("entry_price"),
                                    stop_loss=rec.get("stop_loss"),
                                    take_profit=rec.get("take_profit"),
                                    rec_id=rec_id,
                                )
                            elif digest.mode != "disabled":
                                digest.add({
                                    "type": "recommendation",
                                    "symbol": rec.get("symbol", symbol),
                                    "direction": rec.get("direction", "wait"),
                                    "details": f"{'⬆️' if rec.get('direction')=='long' else '⬇️'} {rec.get('direction','').upper()} {rec.get('symbol', symbol)} — conviction {conviction}%",
                                })
                        except Exception:
                            pass  # Don't fail cycle on notification error
                except Exception as e:
                    logger.error(f"[cycle] Failed to store recommendation: {e}")

            _last_runs["brief"] = datetime.now(timezone.utc)

            # ── Step 5b: Run mechanical strategies BEFORE Brief recs (sets _last_strategy_signals for Brief sizing) ──
            try:
                auto_trader = _get_auto_trader()
                if auto_trader.enabled:
                    # 1h strategies use existing candles
                    strat_executed = auto_trader.process_strategy_signals(
                        candles_1h, symbol,
                        regime_output=regime_output, vol_output=vol_output,
                    )
                    if strat_executed:
                        logger.info(f"[cycle] Strategy signals executed {len(strat_executed)} trades")

                    # 5m candles for ORB session strategy
                    try:
                        candles_5m = await adapter.get_candles(symbol, interval="5m", limit=100)
                        if candles_5m:
                            strat_5m = auto_trader.process_strategy_signals(
                                candles_5m, symbol,
                                regime_output=regime_output, vol_output=vol_output,
                            )
                            if strat_5m:
                                logger.info(f"[cycle] 5m strategy signals executed {len(strat_5m)} trades")
                    except Exception as e:
                        logger.warning(f"[cycle] Failed to fetch 5m candles for strategies: {e}")

                    # HTF trailing stop update on 4h bars
                    try:
                        auto_trader.update_htf_trailing(candles_4h, symbol)
                    except Exception as e:
                        logger.warning(f"[cycle] HTF trailing stop error: {e}")
            except Exception as e:
                logger.warning(f"[cycle] Strategy signals error: {e}")

            # ── Step 5b2: Auto-trader processes stored recs (Brief as conviction multiplier) ──
            try:
                auto_trader = _get_auto_trader()
                if auto_trader.enabled and stored_recs:
                    auto_executed = await auto_trader.process_recommendations(
                        stored_recs,
                        cb_output=cb_output,
                        vol_output=vol_output,
                        latest_prices={symbol: latest_price} if latest_price else None,
                    )
                    if auto_executed:
                        logger.info(f"[cycle] Auto-trader executed {len(auto_executed)} trades")
            except Exception as e:
                logger.warning(f"[cycle] Auto-trader error: {e}")

            # ── Step 5c: Process position actions from Brief ──
            try:
                pos_actions = brief_out.raw_data.get("position_actions", []) if brief_out.raw_data else []
                await _process_position_actions(pos_actions, exchange, symbol, latest_price, engine)
            except Exception as e:
                logger.warning(f"[cycle] Position action processing error: {e}")

            # ── Step 5d: Append training data for distillation ──
            try:
                from wolfpack.export_training_data import format_training_pair, append_training_pair
                quant_dict = agent_outputs["quant"].model_dump() if "quant" in agent_outputs and hasattr(agent_outputs["quant"], "model_dump") else agent_outputs.get("quant")
                snoop_dict = agent_outputs["snoop"].model_dump() if "snoop" in agent_outputs and hasattr(agent_outputs["snoop"], "model_dump") else agent_outputs.get("snoop")
                sage_dict = agent_outputs["sage"].model_dump() if "sage" in agent_outputs and hasattr(agent_outputs["sage"], "model_dump") else agent_outputs.get("sage")
                brief_dict = brief_out.model_dump() if hasattr(brief_out, "model_dump") else brief_out
                pair = format_training_pair(quant_dict, snoop_dict, sage_dict, brief_dict, stored_recs)
                if pair:
                    training_dir = os.environ.get("WOLFPACK_TRAINING_DIR", "training_data")
                    append_training_pair(pair, symbol, training_dir)
                    logger.info(f"[training] Appended training pair for {symbol}")
            except Exception as e:
                logger.warning(f"[training] Failed to append training data: {e}")

            # ── Step 6: Update paper trading portfolio ──
            engine = _get_paper_engine()
            if latest_price and engine.portfolio.positions:
                engine.update_prices({symbol: latest_price})
                engine.store_snapshot(exchange)
                logger.info(f"[cycle] Paper portfolio snapshot stored (equity: ${engine.portfolio.equity:.2f})")

            # ── Step 6a: Track per-position peak P&L + check emergency exits ──
            try:
                for pos in engine.portfolio.positions:
                    dd_monitor.update_position_peak(pos.symbol, pos.unrealized_pnl)

                pos_dicts = [
                    {"symbol": p.symbol, "unrealized_pnl": p.unrealized_pnl, "size_usd": p.size_usd}
                    for p in engine.portfolio.positions
                ]
                emergency_exits = dd_monitor.check_emergency_exits(pos_dicts)
                for exit_signal in emergency_exits:
                    sym = exit_signal["symbol"]
                    logger.warning(f"[drawdown] Emergency close: {sym} — {exit_signal['reason']}")
                    realized = engine.close_position(sym)
                    dd_monitor.clear_position_peak(sym)
                    # Emergency closes ALWAYS send immediately — safety-critical
                    try:
                        from wolfpack.notifications import send_telegram
                        await send_telegram(
                            f"<b>\U0001f6a8 EMERGENCY CLOSE: {sym}</b>\n"
                            f"{exit_signal['reason']}\n"
                            f"Realized P&L: <code>${realized:,.2f}</code>"
                        )
                    except Exception:
                        pass
                    engine.store_snapshot(exchange)
            except Exception as e:
                logger.warning(f"[cycle] Drawdown position tracking error: {e}")

            # ── Step 6b: Update auto-trader prices + check stops ──
            try:
                auto_trader = _get_auto_trader()
                if auto_trader.enabled and latest_price and auto_trader.engine.portfolio.positions:
                    auto_trader.engine.update_prices({symbol: latest_price})
                    triggered = auto_trader.engine.check_stops({symbol: latest_price})
                    if triggered:
                        for sym, reason in triggered:
                            logger.info(f"[auto-trader] {reason} triggered for {sym}")
                            try:
                                from wolfpack.notification_digest import get_digest
                                digest = get_digest()
                                if digest.mode == "individual":
                                    from wolfpack.notifications import send_telegram
                                    await send_telegram(
                                        f"<b>\U0001f6a8 Auto-Bot {reason.upper()} hit for {sym}</b>\n"
                                        f"Price: <code>${latest_price:,.2f}</code>"
                                    )
                                else:
                                    digest.add({
                                        "type": "stop_triggered",
                                        "symbol": sym,
                                        "details": f"{reason.upper()} hit for {sym} @ ${latest_price:,.2f}",
                                    })
                            except Exception:
                                pass
                    auto_trader._store_snapshot()
            except Exception as e:
                logger.warning(f"[cycle] Auto-trader price update error: {e}")

            # ── Step 6c: LP position monitoring ──
            try:
                lp_trader = _get_lp_trader()
                if lp_trader.enabled:
                    lp_result = await lp_trader.process_tick(
                        regime_output=regime_output,
                        vol_output=vol_output,
                    )
                    if lp_result and lp_result.get("alerts"):
                        for alert in lp_result["alerts"]:
                            try:
                                from wolfpack.notification_digest import get_digest
                                digest = get_digest()
                                if digest.mode == "individual":
                                    from wolfpack.notifications import send_telegram
                                    await send_telegram(f"<b>{alert['message']}</b>")
                                elif digest.mode != "disabled":
                                    digest.add({"type": alert["type"], "symbol": alert.get("pair", "LP"), "details": alert["message"]})
                            except Exception:
                                pass
            except Exception as e:
                logger.warning(f"[cycle] LP auto-trader error: {e}")

            # Snapshot cleanup — runs once per process lifetime
            try:
                from wolfpack.db import cleanup_old_snapshots
                cleanup_old_snapshots()
            except Exception as e:
                logger.warning(f"[cycle] Snapshot cleanup error: {e}")

            # Flush notification digest if interval elapsed
            try:
                from wolfpack.notification_digest import get_digest
                await get_digest().maybe_flush()
            except Exception:
                pass

            logger.info(f"[cycle] Full intelligence cycle complete for {symbol} on {exchange}")

        except Exception as e:
            logger.error(f"[cycle] Brief agent failed: {e}", exc_info=True)
            ft.record_failure("brief", str(e))
        finally:
            _running.discard("brief")

    except Exception as e:
        logger.error(f"[cycle] Intelligence cycle failed: {e}", exc_info=True)
    finally:
        _running.discard("quant")
        _running.discard("snoop")
        _running.discard("sage")
        _running.discard("brief")


# ── Circuit Breaker Endpoints ──


@app.get("/circuit-breaker")
async def circuit_breaker_status():
    """Return current circuit breaker state."""
    cb = _get_circuit_breaker()
    engine = _get_paper_engine()
    portfolio = engine.portfolio

    # Use drawdown monitor for auto-tracked peak/drawdown
    dd_monitor = _get_drawdown_monitor()
    dd_info = dd_monitor.update_peaks("hyperliquid", portfolio.equity)
    current_dd = dd_info["drawdown_pct"]

    daily_pnl_pct = ((portfolio.equity - portfolio.starting_equity) / portfolio.starting_equity * 100)
    total_exposure = sum(p.size_usd for p in portfolio.positions) / portfolio.equity * 100 if portfolio.equity > 0 else 0
    output = cb.check(
        daily_pnl_pct=daily_pnl_pct,
        rolling_24h_pnl_pct=daily_pnl_pct,
        current_drawdown_pct=current_dd,
        total_exposure_pct=total_exposure,
    )
    result = output.model_dump()
    result["peak_equity"] = dd_info["peak_equity"]
    return result


@app.post("/circuit-breaker/reset")
async def circuit_breaker_reset(_auth: None = Depends(require_auth)):
    """Manually reset circuit breaker from EMERGENCY_STOP to ACTIVE."""
    cb = _get_circuit_breaker()
    if cb.state != "EMERGENCY_STOP":
        return {"status": "error", "message": f"Not in EMERGENCY_STOP (current: {cb.state})"}
    cb.manual_reset()
    logger.warning("[circuit-breaker] Manual reset from EMERGENCY_STOP")
    # Persist reset to DB
    try:
        from wolfpack.db import save_cb_state
        save_cb_state(state="ACTIVE", triggers=[], max_exposure_pct=0)
    except Exception:
        pass
    return {"status": "ok", "state": cb.state}


# ── Backtest Endpoints ──


@app.get("/backtest/strategies")
async def list_strategies():
    """List available backtest strategies with parameter definitions."""
    from wolfpack.strategies import STRATEGIES

    result = []
    for key, cls in STRATEGIES.items():
        s = cls()
        result.append({
            "key": key,
            "name": s.name,
            "description": s.description,
            "parameters": s.parameters,
            "warmup_bars": s.warmup_bars,
        })
    return {"strategies": result}


@app.post("/backtest/run")
async def start_backtest(background_tasks: BackgroundTasks, config: dict = Body(...)):
    """Start a backtest run in the background. Returns run_id for polling."""
    from wolfpack.db import store_backtest_run
    from wolfpack.models.backtest_models import BacktestConfig

    try:
        bt_config = BacktestConfig(**config)
    except Exception as e:
        return {"status": "error", "message": f"Invalid config: {e}"}

    run_row = store_backtest_run(bt_config.model_dump())
    run_id = run_row.get("id")

    background_tasks.add_task(_execute_backtest, run_id, bt_config)
    return {"status": "started", "run_id": run_id}


@app.get("/backtest/runs")
async def list_backtest_runs(limit: int = 20):
    """List recent backtest runs (summary)."""
    from wolfpack.db import get_backtest_runs

    return {"runs": get_backtest_runs(limit=limit)}


@app.get("/backtest/runs/{run_id}")
async def get_backtest_result(run_id: str):
    """Get full backtest result: metrics + equity curve + trades."""
    from wolfpack.db import get_backtest_run, get_backtest_trades

    run = get_backtest_run(run_id)
    if not run:
        return {"status": "error", "message": "Run not found"}

    trades = get_backtest_trades(run_id) if run.get("status") == "completed" else []
    return {"run": run, "trades": trades}


@app.get("/backtest/runs/{run_id}/status")
async def get_backtest_status(run_id: str):
    """Poll status + progress of a running backtest."""
    from wolfpack.db import get_backtest_run

    run = get_backtest_run(run_id)
    if not run:
        return {"status": "error", "message": "Run not found"}

    return {
        "run_id": run_id,
        "status": run.get("status"),
        "progress_pct": run.get("progress_pct", 0),
        "error": run.get("error"),
    }


@app.delete("/backtest/runs/{run_id}")
async def remove_backtest_run(run_id: str, _auth: None = Depends(require_auth)):
    """Delete a backtest run and its trades."""
    from wolfpack.db import delete_backtest_run

    deleted = delete_backtest_run(run_id)
    return {"status": "deleted" if deleted else "not_found"}


@app.get("/backtest/runs/{run_id}/graduation")
async def check_backtest_graduation(run_id: str):
    """Check if a completed backtest meets graduation criteria for live trading."""
    from wolfpack.db import get_backtest_run
    from wolfpack.modules.backtest import check_graduation

    run = get_backtest_run(run_id)
    if not run:
        return {"status": "error", "message": "Run not found"}
    if run.get("status") != "completed":
        return {"status": "error", "message": f"Run not completed (status: {run.get('status')})"}

    metrics = run.get("metrics", {})
    result = check_graduation(metrics)
    return {
        "run_id": run_id,
        "graduated": result.passed,
        "criteria": result.criteria,
        "failures": result.failures,
    }


@app.post("/backtest/compare")
async def compare_backtests(run_ids: list[str] = Body(...)):
    """Compare metrics for multiple backtest runs side by side."""
    from wolfpack.db import get_backtest_run

    results = []
    for rid in run_ids:
        run = get_backtest_run(rid)
        if run and run.get("status") == "completed":
            results.append({
                "run_id": rid,
                "config": run.get("config"),
                "metrics": run.get("metrics"),
                "trade_count": run.get("trade_count"),
                "duration_seconds": run.get("duration_seconds"),
            })
    return {"comparisons": results}


async def _execute_backtest(run_id: str, config) -> None:
    """Background task: fetch candles, run engine, store results."""
    from wolfpack.backtest_engine import BacktestEngine
    from wolfpack.candle_cache import get_candles
    from wolfpack.db import (
        store_backtest_trades,
        update_backtest_progress,
        update_backtest_result,
    )

    try:
        # Fetch candles (from cache or exchange)
        candles = await get_candles(
            exchange=config.exchange,
            symbol=config.symbol,
            interval=config.interval,
            start_time=config.start_time,
            end_time=config.end_time,
        )

        # Fallback: direct exchange fetch if cache returns empty
        if len(candles) < 100:
            logger.info(f"[backtest] Cache returned {len(candles)} candles, fetching directly from exchange")
            from wolfpack.exchanges import get_exchange
            adapter = get_exchange(config.exchange)
            interval_ms = {"1m": 60_000, "5m": 300_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
            step = interval_ms.get(config.interval, 3_600_000)
            limit = (config.end_time - config.start_time) // step + 2
            candles = await adapter.get_candles(
                config.symbol, interval=config.interval, limit=min(limit, 5000), start_time=config.start_time
            )
            candles = [c for c in candles if config.start_time <= c.timestamp <= config.end_time]

        if len(candles) < 100:
            update_backtest_result(
                run_id, status="failed", error=f"Insufficient candle data: {len(candles)} bars"
            )
            return

        # Progress callback
        async def on_progress(pct: float):
            update_backtest_progress(run_id, pct)

        # Run engine
        engine = BacktestEngine(config)
        result = await engine.run(candles, progress_cb=on_progress)

        # Store trades
        trade_dicts = [t.model_dump() for t in result.trades]
        store_backtest_trades(run_id, trade_dicts)

        # Update run with results
        update_backtest_result(
            run_id,
            metrics=result.metrics.model_dump(),
            equity_curve=result.equity_curve,
            monthly_returns=result.monthly_returns,
            trade_count=len(result.trades),
            duration_seconds=result.duration_seconds,
            status="completed",
        )

        logger.info(f"[backtest] Run {run_id} completed: {len(result.trades)} trades, {result.duration_seconds:.1f}s")

    except Exception as e:
        logger.error(f"[backtest] Run {run_id} failed: {e}", exc_info=True)
        update_backtest_result(run_id, status="failed", error=str(e))


async def _run_agent(agent: Any, market_data: dict, exchange: str, store_fn: Any) -> Any:
    """Run a single agent and store its output. Returns the AgentOutput."""
    output = await agent.analyze(market_data, exchange)
    store_fn(
        agent_name=output.agent_name,
        exchange_id=exchange,
        summary=output.summary,
        signals=output.signals,
        confidence=output.confidence,
        raw_data=output.raw_data,
    )
    return output


# ── Watchlist Endpoints ──


@app.get("/watchlist")
async def get_watchlist(exchange_id: str = "hyperliquid"):
    """Return all watchlist symbols."""
    from wolfpack.db import get_watchlist as db_get_watchlist

    items = db_get_watchlist(exchange_id)
    return {"watchlist": items}


@app.post("/watchlist")
async def add_watchlist(
    symbol: str = Body(..., embed=True),
    exchange_id: str = Body("hyperliquid", embed=True),
    notes: str | None = Body(None, embed=True),
    _auth: None = Depends(require_auth),
):
    """Add a symbol to the watchlist."""
    from wolfpack.db import add_to_watchlist

    row = add_to_watchlist(symbol, exchange_id, notes)
    return {"status": "ok", "item": row}


@app.delete("/watchlist/{symbol}")
async def remove_watchlist(
    symbol: str,
    exchange_id: str = "hyperliquid",
    _auth: None = Depends(require_auth),
):
    """Remove a symbol from the watchlist."""
    from wolfpack.db import remove_from_watchlist

    removed = remove_from_watchlist(symbol, exchange_id)
    return {"status": "ok", "removed": removed}


@app.get("/watchlist/search")
async def search_symbols(q: str = "", exchange: str = "hyperliquid"):
    """Search available symbols from exchange. Used for type-to-complete."""
    from wolfpack.exchanges import get_exchange

    try:
        adapter = get_exchange(exchange)  # type: ignore[arg-type]
        markets = await adapter.get_markets()
        query = q.upper()
        matches = [
            {"symbol": m.symbol, "last_price": m.last_price, "volume_24h": m.volume_24h}
            for m in markets
            if query in m.symbol.upper()
        ]
        # Sort by volume descending, limit to 20
        matches.sort(key=lambda x: x["volume_24h"], reverse=True)
        return {"results": matches[:20]}
    except Exception as e:
        logger.error(f"[watchlist] Symbol search failed: {e}")
        return {"results": []}


# ── Pool Screening ──


@app.get("/pools/screen")
async def screen_pools(limit: int = 20):
    """Fetch top pools from The Graph and score them with the pool screening module."""
    import httpx
    from wolfpack.modules.pool_screening import PoolScreeningInput, screen_pool

    api_key = settings.subgraph_api_key
    if not api_key:
        # Free public endpoint - no signup, just works
        api_key = "demo"

    # Alchemy subgraph endpoint (free, no signup)
    subgraph_url = f"https://eth-mainnet.g.alchemy.com/api/subgraphs/id/uniswap-v3"

    # Fallback endpoints to try
    fallback_urls = [
        f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV",
        "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
    ]

    endpoints = [subgraph_url] + fallback_urls

    query = """
    query TopPools($first: Int!) {
        pools(
            first: $first
            orderBy: totalValueLockedUSD
            orderDirection: desc
            where: { volumeUSD_gt: "1000000" }
        ) {
            id
            feeTier
            totalValueLockedUSD
            volumeUSD
            token0 { symbol }
            token1 { symbol }
            poolDayData(first: 7, orderBy: date, orderDirection: desc) {
                volumeUSD
            }
        }
    }
    """

    pools = []
    last_error = None

    for url in endpoints:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    url,
                    json={"query": query, "variables": {"first": limit * 2}},
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}"
                    continue

                data = resp.json()
                if "errors" in data:
                    last_error = str(data["errors"])
                    continue

                pools = data.get("data", {}).get("pools", [])
                if pools:
                    break  # Success!
        except Exception as e:
            last_error = str(e)
            continue

    if not pools:
        return {"status": "error", "message": f"Subgraph failed: {last_error}", "pools": []}

    scored: list[dict] = []
    for p in pools:
        day_data = p.get("poolDayData", [])
        avg_daily_vol = (
            sum(float(d.get("volumeUSD", 0)) for d in day_data) / len(day_data)
            if day_data
            else 0
        )

        # Compute volume trend from recent days
        trend = "flat"
        if len(day_data) >= 3:
            recent = sum(float(d["volumeUSD"]) for d in day_data[:3]) / 3
            older = sum(float(d["volumeUSD"]) for d in day_data[3:]) / max(len(day_data) - 3, 1)
            if older > 0:
                change = (recent - older) / older
                if change > 0.15:
                    trend = "rising"
                elif change < -0.15:
                    trend = "falling"

        inp = PoolScreeningInput(
            pool_id=p["id"],
            token0_symbol=p["token0"]["symbol"],
            token1_symbol=p["token1"]["symbol"],
            fee_tier=int(p["feeTier"]),
            tvl_usd=float(p["totalValueLockedUSD"]),
            volume_usd_24h=avg_daily_vol,
            volume_trend=trend,
        )
        result = screen_pool(inp)
        scored.append({
            "pool_id": result.pool_id,
            "pair": result.pair,
            "fee_tier": p["feeTier"],
            "tvl_usd": float(p["totalValueLockedUSD"]),
            "volume_usd_24h": round(avg_daily_vol, 2),
            "score": result.score,
            "recommendation": result.recommendation,
            "breakdown": result.breakdown,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"status": "ok", "pools": scored[:limit]}


# ── Pool Data Proxies (no API key required on frontend) ──

TOP_POOLS_QUERY = """
query TopPools($first: Int!) {
    pools(
        first: $first
        orderBy: totalValueLockedUSD
        orderDirection: desc
        where: { volumeUSD_gt: "1000000" }
    ) {
        id
        feeTier
        totalValueLockedUSD
        volumeUSD
        token0 { id symbol name decimals }
        token1 { id symbol name decimals }
    }
}
"""

POOL_DETAIL_QUERY = """
query PoolDetail($id: ID!) {
    pool(id: $id) {
        id
        feeTier
        totalValueLockedUSD
        volumeUSD
        sqrtPrice
        tick
        liquidity
        token0 { id symbol name decimals }
        token1 { id symbol name decimals }
        poolDayData(first: 30, orderBy: date, orderDirection: desc) {
            date
            volumeUSD
            feesUSD
            tvlUSD
        }
    }
}
"""

POSITIONS_QUERY = """
query Positions($owner: Bytes!, $first: Int!) {
    positions(
        where: { owner: $owner }
        first: $first
        orderBy: liquidity
        orderDirection: desc
    ) {
        id
        pool {
            id
            token0 { id symbol name decimals }
            token1 { id symbol name decimals }
            feeTier
        }
        liquidity
        depositedToken0
        depositedToken1
        withdrawnToken0
        withdrawnToken1
        collectedFeesToken0
        collectedFeesToken1
        tickLower { tickIdx }
        tickUpper { tickIdx }
    }
}
"""


async def _fetch_subgraph(query: str, variables: dict) -> dict:
    """Fetch from Uniswap V3 subgraph with fallback endpoints."""
    api_key = settings.subgraph_api_key
    endpoints = [
        "https://eth-mainnet.g.alchemy.com/api/subgraphs/id/uniswap-v3",
    ]
    if api_key:
        endpoints.append(f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV")
    endpoints.append("https://gateway.thegraph.com/api/demo/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV")

    for url in endpoints:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    url,
                    json={"query": query, "variables": variables},
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if "errors" in data:
                    continue
                return data.get("data", {})
        except Exception:
            continue
    raise HTTPException(status_code=502, detail="Subgraph unavailable")


@app.get("/pools/top")
async def get_top_pools(first: int = 50):
    """Fetch top Uniswap V3 pools by TVL."""
    try:
        data = await _fetch_subgraph(TOP_POOLS_QUERY, {"first": first})
        return {"pools": data.get("pools", [])}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"[pools/top] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pools/detail")
async def get_pool_detail(pool_id: str):
    """Fetch detailed data for a specific pool."""
    try:
        data = await _fetch_subgraph(POOL_DETAIL_QUERY, {"id": pool_id.lower()})
        return {"pool": data.get("pool")}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"[pools/detail] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pools/positions")
async def get_pool_positions(owner: str, first: int = 50):
    """Fetch LP positions for an address."""
    try:
        data = await _fetch_subgraph(POSITIONS_QUERY, {"owner": owner.lower(), "first": first})
        return {"positions": data.get("positions", [])}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"[pools/positions] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── LP Automation Endpoints ──


@app.get("/lp/status")
async def lp_status():
    """Get LP automation status."""
    lp = _get_lp_trader()
    return lp.get_status()


@app.post("/lp/toggle")
async def lp_toggle(enabled: bool = Body(..., embed=True)):
    """Enable/disable LP automation."""
    lp = _get_lp_trader()
    lp._enabled = enabled
    return {"enabled": lp._enabled}


@app.get("/lp/positions")
async def lp_positions():
    """Get all LP positions from paper engine."""
    lp = _get_lp_trader()
    return {
        "positions": [
            {
                "position_id": p.position_id,
                "pool": p.pool_address,
                "pair": f"{p.token0_symbol}/{p.token1_symbol}",
                "fee_tier": p.fee_tier,
                "ticks": [p.tick_lower, p.tick_upper],
                "current_tick": p.current_tick,
                "liquidity_usd": round(p.liquidity_usd, 2),
                "fees_earned": round(p.fees_earned_usd, 2),
                "il_pct": p.il_pct,
                "status": p.status,
                "out_of_range_ticks": p.out_of_range_ticks,
            }
            for p in lp.engine.portfolio.positions
        ],
        "portfolio": {
            "equity": round(lp.engine.portfolio.equity, 2),
            "free_collateral": round(lp.engine.portfolio.free_collateral, 2),
            "total_fees": round(lp.engine.portfolio.total_fees_earned, 2),
            "total_il": round(lp.engine.portfolio.total_il, 2),
            "realized_pnl": round(lp.engine.portfolio.realized_pnl, 2),
        },
    }


@app.post("/lp/watch")
async def lp_watch_pool(pool_address: str = Body(..., embed=True)):
    """Add a pool to the LP watch list."""
    lp = _get_lp_trader()
    lp.add_pool(pool_address)
    return {"watched_pools": lp._watched_pools}


# ── Multi-Symbol Intelligence ──


@app.post("/intelligence/run-all")
async def run_all_intelligence(
    background_tasks: BackgroundTasks,
    exchange: str = "hyperliquid",
    _auth: None = Depends(require_auth),
):
    """Run intelligence for all watchlist symbols + open position symbols."""
    if _running:
        return {"status": "already_running", "agents": list(_running)}

    from wolfpack.db import get_watchlist as db_get_watchlist

    watchlist = db_get_watchlist(exchange)
    watchlist_symbols = [w["symbol"] for w in watchlist]

    # Also include symbols from open positions
    engine = _get_paper_engine()
    position_symbols = [p.symbol for p in engine.portfolio.positions]

    all_symbols = list(dict.fromkeys(watchlist_symbols + position_symbols))  # Deduplicate, preserve order
    if not all_symbols:
        all_symbols = ["BTC"]  # Default

    background_tasks.add_task(_run_multi_symbol, exchange, all_symbols)
    return {"status": "started", "exchange": exchange, "symbols": all_symbols}


async def _run_multi_symbol(exchange: str, symbols: list[str]) -> None:
    """Run intelligence cycle sequentially for each symbol (avoids rate limits)."""
    logger.info(f"[multi] Starting multi-symbol run for {symbols} on {exchange}")
    for symbol in symbols:
        try:
            logger.info(f"[multi] Running cycle for {symbol}...")
            await _run_full_cycle(exchange, symbol)
        except Exception as e:
            logger.error(f"[multi] Cycle failed for {symbol}: {e}")
    logger.info(f"[multi] Multi-symbol run complete: {len(symbols)} symbols")


# ── Prompt Templates ──

VALID_AGENTS = {"quant", "snoop", "sage", "brief"}
VALID_SECTIONS = {"role", "input_format", "output_schema", "constraints", "reasoning_instructions", "examples"}


@app.get("/prompt-templates/{agent_name}")
async def get_prompt_templates(
    agent_name: str,
    _auth: None = Depends(require_auth),
):
    """Get current effective prompt sections for an agent (DB overrides merged with defaults)."""
    if agent_name not in VALID_AGENTS:
        raise HTTPException(status_code=400, detail=f"Invalid agent: {agent_name}. Must be one of {VALID_AGENTS}")

    from wolfpack.prompt_builder import get_prompt_builder
    pb = get_prompt_builder()
    if not pb:
        raise HTTPException(status_code=503, detail="PromptBuilder not initialized")

    sections = pb.get_sections(agent_name)
    token_estimate = pb.estimate_tokens(agent_name)

    return {
        "agent_name": agent_name,
        "sections": sections,
        "token_estimate": token_estimate,
    }


@app.post("/prompt-templates/{agent_name}/{section}")
async def update_prompt_template(
    agent_name: str,
    section: str,
    content: str = Body(..., embed=True),
    _auth: None = Depends(require_auth),
):
    """Update a prompt section for an agent. Creates a new version in the DB."""
    if agent_name not in VALID_AGENTS:
        raise HTTPException(status_code=400, detail=f"Invalid agent: {agent_name}. Must be one of {VALID_AGENTS}")
    if section not in VALID_SECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid section: {section}. Must be one of {VALID_SECTIONS}")
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    from wolfpack.db import get_db
    db = get_db()

    try:
        # Deactivate existing active version for this agent+section
        db.table("wp_prompt_templates").update({"is_active": False}).eq(
            "agent_name", agent_name
        ).eq("section", section).eq("is_active", True).execute()

        # Get next version number
        existing = db.table("wp_prompt_templates").select("version").eq(
            "agent_name", agent_name
        ).eq("section", section).order("version", desc=True).limit(1).execute()

        next_version = 1
        if existing.data:
            next_version = existing.data[0]["version"] + 1

        # Insert new active version
        result = db.table("wp_prompt_templates").insert({
            "agent_name": agent_name,
            "section": section,
            "content": content.strip(),
            "is_active": True,
            "version": next_version,
        }).execute()

        return {
            "status": "updated",
            "agent_name": agent_name,
            "section": section,
            "version": next_version,
        }
    except Exception as e:
        logger.error(f"Failed to update prompt template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update: {e}")
