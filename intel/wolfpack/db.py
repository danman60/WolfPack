"""Supabase client — shared database access for the intel service."""

from supabase import create_client, Client
from wolfpack.config import settings

_client: Client | None = None


def get_db() -> Client:
    """Get or create the Supabase client singleton."""
    global _client
    if _client is None:
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


def store_agent_output(
    agent_name: str,
    exchange_id: str,
    summary: str,
    signals: list[dict],
    confidence: float,
    raw_data: dict | None = None,
) -> dict:
    """Store an agent output in wp_agent_outputs and return the inserted row."""
    db = get_db()
    row = {
        "agent_name": agent_name,
        "exchange_id": exchange_id,
        "summary": summary,
        "signals": signals,
        "confidence": confidence,
        "raw_data": raw_data,
    }
    result = db.table("wp_agent_outputs").insert(row).execute()
    return result.data[0] if result.data else row


def store_module_output(
    module_name: str,
    exchange_id: str,
    output: dict,
    symbol: str | None = None,
) -> dict:
    """Store a module output in wp_module_outputs."""
    db = get_db()
    row = {
        "module_name": module_name,
        "exchange_id": exchange_id,
        "output": output,
        "symbol": symbol,
    }
    result = db.table("wp_module_outputs").insert(row).execute()
    return result.data[0] if result.data else row


def store_recommendation(
    exchange_id: str,
    symbol: str,
    direction: str,
    conviction: int,
    rationale: str,
    agent_output_id: str | None = None,
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    size_pct: float | None = None,
) -> dict:
    """Store a trade recommendation in wp_trade_recommendations."""
    db = get_db()
    row = {
        "exchange_id": exchange_id,
        "symbol": symbol,
        "direction": direction,
        "conviction": conviction,
        "rationale": rationale,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "size_pct": size_pct,
        "agent_output_id": agent_output_id,
    }
    result = db.table("wp_trade_recommendations").insert(row).execute()
    return result.data[0] if result.data else row


def get_latest_agent_outputs(limit: int = 4) -> list[dict]:
    """Fetch latest output per agent."""
    db = get_db()
    result = (
        db.table("wp_agent_outputs")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit * 2)
        .execute()
    )
    # Deduplicate by agent_name, keeping latest
    seen: dict[str, dict] = {}
    for row in result.data or []:
        name = row["agent_name"]
        if name not in seen:
            seen[name] = row
    return list(seen.values())


def get_latest_recommendations(status: str = "pending", limit: int = 10) -> list[dict]:
    """Fetch latest trade recommendations by status."""
    db = get_db()
    result = (
        db.table("wp_trade_recommendations")
        .select("*")
        .eq("status", status)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


# ---------------------------------------------------------------------------
# Backtest helpers
# ---------------------------------------------------------------------------


def store_backtest_run(config: dict) -> dict:
    """Insert a new backtest run row (status=running). Returns row with id."""
    db = get_db()
    row = {"config": config, "status": "running", "progress_pct": 0}
    result = db.table("wp_backtest_runs").insert(row).execute()
    return result.data[0] if result.data else row


def update_backtest_result(
    run_id: str,
    metrics: dict | None = None,
    equity_curve: list | None = None,
    monthly_returns: list | None = None,
    trade_count: int = 0,
    duration_seconds: float = 0,
    status: str = "completed",
    error: str | None = None,
    progress_pct: float = 100,
) -> dict:
    """Update a backtest run with results."""
    db = get_db()
    update: dict = {"status": status, "progress_pct": progress_pct}
    if metrics is not None:
        update["metrics"] = metrics
    if equity_curve is not None:
        update["equity_curve"] = equity_curve
    if monthly_returns is not None:
        update["monthly_returns"] = monthly_returns
    if trade_count:
        update["trade_count"] = trade_count
    if duration_seconds:
        update["duration_seconds"] = duration_seconds
    if error:
        update["error"] = error
    if status in ("completed", "failed"):
        update["completed_at"] = "now()"
    result = db.table("wp_backtest_runs").update(update).eq("id", run_id).execute()
    return result.data[0] if result.data else update


def update_backtest_progress(run_id: str, progress_pct: float) -> None:
    """Update progress percentage for a running backtest."""
    db = get_db()
    db.table("wp_backtest_runs").update({"progress_pct": progress_pct}).eq("id", run_id).execute()


def get_backtest_runs(limit: int = 20) -> list[dict]:
    """Fetch recent backtest runs (summary — no equity curve)."""
    db = get_db()
    result = (
        db.table("wp_backtest_runs")
        .select("id, config, status, metrics, trade_count, duration_seconds, progress_pct, error, created_at, completed_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_backtest_run(run_id: str) -> dict | None:
    """Fetch a single backtest run with full data."""
    db = get_db()
    result = db.table("wp_backtest_runs").select("*").eq("id", run_id).execute()
    if not result.data:
        return None
    return result.data[0]


def delete_backtest_run(run_id: str) -> bool:
    """Delete a backtest run (cascades to trades)."""
    db = get_db()
    result = db.table("wp_backtest_runs").delete().eq("id", run_id).execute()
    return bool(result.data)


def store_backtest_trades(run_id: str, trades: list[dict]) -> int:
    """Bulk insert backtest trades. Returns count inserted."""
    if not trades:
        return 0
    db = get_db()
    rows = [{"run_id": run_id, **t} for t in trades]
    # Insert in batches of 500
    inserted = 0
    for i in range(0, len(rows), 500):
        batch = rows[i : i + 500]
        result = db.table("wp_backtest_trades").insert(batch).execute()
        inserted += len(result.data) if result.data else 0
    return inserted


def get_backtest_trades(run_id: str) -> list[dict]:
    """Fetch all trades for a backtest run."""
    db = get_db()
    result = (
        db.table("wp_backtest_trades")
        .select("*")
        .eq("run_id", run_id)
        .order("entry_time")
        .execute()
    )
    return result.data or []


# ---------------------------------------------------------------------------
# Candle cache helpers
# ---------------------------------------------------------------------------


def store_candles(rows: list[dict]) -> int:
    """Bulk upsert candles to cache. Returns count."""
    if not rows:
        return 0
    db = get_db()
    stored = 0
    for i in range(0, len(rows), 500):
        batch = rows[i : i + 500]
        result = db.table("wp_candle_cache").upsert(batch, on_conflict="exchange_id,symbol,interval,timestamp").execute()
        stored += len(result.data) if result.data else 0
    return stored


def get_cached_candles(
    exchange: str, symbol: str, interval: str, start_time: int, end_time: int
) -> list[dict]:
    """Fetch cached candles for a time range."""
    db = get_db()
    result = (
        db.table("wp_candle_cache")
        .select("timestamp, open, high, low, close, volume")
        .eq("exchange_id", exchange)
        .eq("symbol", symbol)
        .eq("interval", interval)
        .gte("timestamp", start_time)
        .lte("timestamp", end_time)
        .order("timestamp")
        .execute()
    )
    return result.data or []
