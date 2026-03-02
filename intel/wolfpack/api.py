"""FastAPI application — exposes intelligence endpoints to the frontend."""

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks
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


@app.post("/intelligence/run")
async def run_intelligence(
    background_tasks: BackgroundTasks,
    exchange: str = "hyperliquid",
    symbol: str = "BTC",
):
    """Trigger a full intelligence cycle for the specified exchange and symbol."""
    if "quant" in _running:
        return {"status": "already_running", "exchange": exchange}

    background_tasks.add_task(_run_quant_cycle, exchange, symbol)
    return {"status": "started", "exchange": exchange, "symbol": symbol}


async def _run_quant_cycle(exchange: str, symbol: str) -> None:
    """Execute a full Quant intelligence cycle: fetch data → modules → LLM → Supabase."""
    _running.add("quant")
    try:
        from wolfpack.exchanges import get_exchange
        from wolfpack.modules.regime import RegimeDetector
        from wolfpack.modules.liquidity import LiquidityIntel
        from wolfpack.modules.funding import FundingIntel
        from wolfpack.modules.volatility import VolatilitySignal
        from wolfpack.agents.quant import QuantAgent
        from wolfpack.db import store_agent_output, store_module_output

        adapter = get_exchange(exchange)  # type: ignore[arg-type]

        # Fetch data in parallel-ish (sequential for now, can asyncio.gather later)
        logger.info(f"Fetching {symbol} data from {exchange}...")
        candles_1h = await adapter.get_candles(symbol, interval="1h", limit=300)
        orderbook = await adapter.get_orderbook(symbol, depth=20)
        funding_rates = await adapter.get_funding_rates()

        # Run modules
        logger.info("Running quantitative modules...")

        # Regime detection (takes Candle objects directly, supports multi-TF)
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

        # Run Quant agent
        logger.info("Running Quant agent LLM analysis...")
        quant = QuantAgent()
        market_data = {
            "symbol": symbol,
            "candles": candles_1h,
            "regime": regime_output,
            "liquidity": liquidity_output,
            "volatility": vol_output,
            "funding": funding_output.model_dump() if funding_output else None,
        }
        agent_output = await quant.analyze(market_data, exchange)

        # Store to Supabase
        store_agent_output(
            agent_name=agent_output.agent_name,
            exchange_id=exchange,
            summary=agent_output.summary,
            signals=agent_output.signals,
            confidence=agent_output.confidence,
            raw_data=agent_output.raw_data,
        )

        _last_runs["quant"] = datetime.now(timezone.utc)
        logger.info(f"Quant cycle complete for {symbol} on {exchange}")

    except Exception as e:
        logger.error(f"Quant cycle failed: {e}", exc_info=True)
    finally:
        _running.discard("quant")
