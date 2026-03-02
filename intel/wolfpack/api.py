"""FastAPI application — exposes intelligence endpoints to the frontend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wolfpack.config import settings

app = FastAPI(title="WolfPack Intel", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "wolfpack-intel"}


@app.get("/agents/status")
async def agent_status():
    """Return status of all 4 intelligence agents."""
    return {
        "agents": [
            {"name": "The Quant", "status": "idle", "last_run": None},
            {"name": "The Snoop", "status": "idle", "last_run": None},
            {"name": "The Sage", "status": "idle", "last_run": None},
            {"name": "The Brief", "status": "idle", "last_run": None},
        ]
    }


@app.get("/intelligence/latest")
async def latest_intelligence():
    """Return latest intelligence brief from all agents."""
    return {
        "quant": None,
        "snoop": None,
        "sage": None,
        "brief": None,
        "timestamp": None,
    }


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
async def run_intelligence(exchange: str = "hyperliquid"):
    """Trigger a full intelligence cycle for the specified exchange."""
    # TODO: Wire up agent orchestration
    return {"status": "queued", "exchange": exchange}
