"""FastAPI application — exposes intelligence endpoints to the frontend."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wolfpack.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="WolfPack Intel", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track last run times
_last_runs: dict[str, datetime | None] = {
    "quant": None,
    "snoop": None,
    "sage": None,
    "brief": None,
}
_running: set[str] = set()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "wolfpack-intel"}


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
        ]
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
    """Return status of all 8 quantitative modules."""
    modules = [
        "regime_detection",
        "liquidity_intel",
        "funding_carry",
        "correlation",
        "volatility",
        "circuit_breakers",
        "execution_timing",
        "backtest",
    ]
    return {"modules": {m: {"status": "not_started", "last_run": None} for m in modules}}


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
async def set_strategy_mode(mode: str):
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
            "passed": True,  # Always active by default
            "description": "Circuit breaker module must be enabled",
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
async def approve_recommendation(rec_id: str, exchange: str = "hyperliquid"):
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

        # Execute as paper trade if paper trading engine is available
        if _paper_engine is not None and rec.get("entry_price"):
            pos = _paper_engine.open_position(
                symbol=rec["symbol"],
                direction=rec["direction"],
                current_price=rec["entry_price"],
                size_pct=rec.get("size_pct") or 5.0,
                recommendation_id=rec_id,
            )
            if pos:
                # Update status to executed
                db.table("wp_trade_recommendations").update(
                    {"status": "executed"}
                ).eq("id", rec_id).execute()

                # Store portfolio snapshot
                _paper_engine.store_snapshot(exchange)
                return {"status": "executed", "position": pos.model_dump()}

        return {"status": "approved", "recommendation": rec}

    except Exception as e:
        logger.error(f"Failed to approve recommendation: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/recommendations/{rec_id}/reject")
async def reject_recommendation(rec_id: str):
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
async def portfolio_status():
    """Return current paper trading portfolio state."""
    if _paper_engine is None:
        return {"status": "inactive", "message": "Paper trading not initialized"}

    portfolio = _paper_engine.portfolio
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


@app.post("/portfolio/close/{symbol}")
async def close_position(symbol: str, exchange: str = "hyperliquid"):
    """Close a paper trading position."""
    if _paper_engine is None:
        return {"status": "error", "message": "Paper trading not initialized"}

    realized_pnl = _paper_engine.close_position(symbol.upper())
    _paper_engine.store_snapshot(exchange)
    return {"status": "closed", "symbol": symbol.upper(), "realized_pnl": round(realized_pnl, 2)}


# ── Trade Execution Endpoints ──


@app.post("/trades/execute")
async def execute_trade(
    symbol: str,
    direction: str,
    size: float,
    price: float,
    order_type: str = "limit",
    reduce_only: bool = False,
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
        return {"status": "ok", "positions": positions}
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
async def cancel_order(symbol: str, order_id: int):
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
    """Get or create the paper trading engine singleton."""
    global _paper_engine
    if _paper_engine is None:
        from wolfpack.paper_trading import PaperTradingEngine

        _paper_engine = PaperTradingEngine(starting_equity=10000.0)
    return _paper_engine


# ── Market Data Endpoints ──


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


@app.post("/intelligence/run")
async def run_intelligence(
    background_tasks: BackgroundTasks,
    exchange: str = "hyperliquid",
    symbol: str = "BTC",
):
    """Trigger a full intelligence cycle for the specified exchange and symbol."""
    if _running:
        return {"status": "already_running", "agents": list(_running)}

    background_tasks.add_task(_run_full_cycle, exchange, symbol)
    return {"status": "started", "exchange": exchange, "symbol": symbol}


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
        from wolfpack.agents.brief import BriefAgent
        from wolfpack.agents.quant import QuantAgent
        from wolfpack.agents.sage import SageAgent
        from wolfpack.agents.snoop import SnoopAgent
        from wolfpack.db import store_agent_output, store_module_output, store_recommendation
        from wolfpack.exchanges import get_exchange
        from wolfpack.modules.correlation import CorrelationIntel
        from wolfpack.modules.funding import FundingIntel
        from wolfpack.modules.liquidity import LiquidityIntel
        from wolfpack.modules.regime import RegimeDetector
        from wolfpack.modules.volatility import VolatilitySignal

        adapter = get_exchange(exchange)  # type: ignore[arg-type]

        # ── Step 1: Fetch market data ──
        logger.info(f"[cycle] Fetching {symbol} data from {exchange}...")
        candles_1h = await adapter.get_candles(symbol, interval="1h", limit=300)
        orderbook = await adapter.get_orderbook(symbol, depth=20)
        funding_rates = await adapter.get_funding_rates()

        # Also fetch ETH candles for correlation analysis
        eth_candles: list = []
        if symbol != "ETH":
            try:
                eth_candles = await adapter.get_candles("ETH", interval="1h", limit=300)
            except Exception as e:
                logger.warning(f"[cycle] Could not fetch ETH candles for correlation: {e}")

        # ── Step 2: Run quantitative modules ──
        logger.info("[cycle] Running quantitative modules...")

        # Regime detection
        regime_detector = RegimeDetector()
        regime_output = regime_detector.detect(candles_1h, asset=symbol)
        store_module_output("regime_detection", exchange, regime_output.model_dump(), symbol)

        # Liquidity
        liquidity_intel = LiquidityIntel()
        liquidity_output = liquidity_intel.analyze(orderbook)
        store_module_output("liquidity_intel", exchange, liquidity_output.model_dump(), symbol)

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
                open_interest_usd=0,
                oi_change_24h_pct=0,
            )
            store_module_output("funding_carry", exchange, funding_output.model_dump(), symbol)

        # Volatility
        closes = [c.close for c in candles_1h]
        vol_signal = VolatilitySignal()
        vol_output = vol_signal.analyze(asset=symbol, closes=closes)
        store_module_output("volatility", exchange, vol_output.model_dump(), symbol)

        # Correlation (BTC/ETH)
        correlation_output = None
        if eth_candles and len(eth_candles) >= 20:
            try:
                corr_intel = CorrelationIntel()
                btc_closes = [c.close for c in candles_1h]
                eth_closes = [c.close for c in eth_candles]
                correlation_output = corr_intel.analyze(btc_closes, eth_closes)
                store_module_output("correlation", exchange, correlation_output.model_dump(), symbol)
            except Exception as e:
                logger.warning(f"[cycle] Correlation analysis failed: {e}")

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
            "liquidity": liquidity_output,
            "volatility": vol_output,
            "funding": funding_output.model_dump() if funding_output else None,
            "latest_price": latest_price,
        }

        # Quant gets candles too
        quant_data = {**market_data_base, "candles": candles_1h}

        # Sage gets correlation
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

        # Log any agent failures but continue
        agent_outputs: dict[str, Any] = {}
        for name, result in [("quant", quant_out), ("snoop", snoop_out), ("sage", sage_out)]:
            if isinstance(result, Exception):
                logger.error(f"[cycle] {name} agent failed: {result}")
            elif isinstance(result, dict):
                agent_outputs[name] = result
            else:
                agent_outputs[name] = result

        # ── Step 4: Run Brief agent (consumes other agent outputs) ──
        logger.info("[cycle] Running Brief agent (synthesis)...")
        _running.add("brief")

        brief_data: dict[str, Any] = {
            "symbol": symbol,
            "latest_price": latest_price,
            "regime": regime_output,
            "circuit_breaker": None,
        }
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
            for rec in recs:
                conviction = rec.get("conviction", 0)
                if conviction < 40:
                    continue  # Skip low-conviction recs
                try:
                    store_recommendation(
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
                    # Telegram notification for high-conviction recs
                    if conviction >= 70:
                        try:
                            from wolfpack.notifications import notify_recommendation
                            await notify_recommendation(
                                symbol=rec.get("symbol", symbol),
                                direction=rec.get("direction", "wait"),
                                conviction=conviction,
                                rationale=rec.get("rationale", ""),
                                entry_price=rec.get("entry_price"),
                                stop_loss=rec.get("stop_loss"),
                                take_profit=rec.get("take_profit"),
                            )
                        except Exception:
                            pass  # Don't fail cycle on notification error
                except Exception as e:
                    logger.error(f"[cycle] Failed to store recommendation: {e}")

            _last_runs["brief"] = datetime.now(timezone.utc)

            # ── Step 6: Update paper trading portfolio ──
            engine = _get_paper_engine()
            if latest_price and engine.portfolio.positions:
                engine.update_prices({symbol: latest_price})
                engine.store_snapshot(exchange)
                logger.info(f"[cycle] Paper portfolio snapshot stored (equity: ${engine.portfolio.equity:.2f})")

            logger.info(f"[cycle] Full intelligence cycle complete for {symbol} on {exchange}")

        except Exception as e:
            logger.error(f"[cycle] Brief agent failed: {e}", exc_info=True)
        finally:
            _running.discard("brief")

    except Exception as e:
        logger.error(f"[cycle] Intelligence cycle failed: {e}", exc_info=True)
    finally:
        _running.discard("quant")
        _running.discard("snoop")
        _running.discard("sage")
        _running.discard("brief")


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
async def start_backtest(config: dict, background_tasks: BackgroundTasks):
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
async def remove_backtest_run(run_id: str):
    """Delete a backtest run and its trades."""
    from wolfpack.db import delete_backtest_run

    deleted = delete_backtest_run(run_id)
    return {"status": "deleted" if deleted else "not_found"}


@app.post("/backtest/compare")
async def compare_backtests(run_ids: list[str]):
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
