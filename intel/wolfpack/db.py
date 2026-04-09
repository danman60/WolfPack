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
    result = db.table("wp_agent_outputs").upsert(
        row, on_conflict="agent_name,exchange_id"
    ).execute()
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
    result = db.table("wp_module_outputs").upsert(
        row, on_conflict="module_name,exchange_id,symbol"
    ).execute()
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


# ---------------------------------------------------------------------------
# Watchlist helpers
# ---------------------------------------------------------------------------


def get_watchlist(exchange_id: str = "hyperliquid") -> list[dict]:
    """Fetch all watchlist symbols for an exchange."""
    db = get_db()
    result = (
        db.table("wp_watchlist")
        .select("*")
        .eq("exchange_id", exchange_id)
        .order("added_at")
        .execute()
    )
    return result.data or []


def add_to_watchlist(symbol: str, exchange_id: str = "hyperliquid", notes: str | None = None) -> dict:
    """Add a symbol to the watchlist. Returns the inserted row."""
    db = get_db()
    row: dict = {"symbol": symbol.upper(), "exchange_id": exchange_id}
    if notes:
        row["notes"] = notes
    result = db.table("wp_watchlist").upsert(row, on_conflict="symbol,exchange_id").execute()
    return result.data[0] if result.data else row


def remove_from_watchlist(symbol: str, exchange_id: str = "hyperliquid") -> bool:
    """Remove a symbol from the watchlist."""
    db = get_db()
    result = (
        db.table("wp_watchlist")
        .delete()
        .eq("symbol", symbol.upper())
        .eq("exchange_id", exchange_id)
        .execute()
    )
    return bool(result.data)


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


# ---------------------------------------------------------------------------
# Circuit breaker state persistence
# ---------------------------------------------------------------------------


def save_cb_state(
    state: str,
    triggers: list[str],
    max_exposure_pct: float,
    peak_equity: float | None = None,
    wallet_id: str | None = None,
) -> dict:
    """Upsert circuit breaker state — one row per wallet (or singleton for back-compat)."""
    db = get_db()
    # Use wallet_id as the singleton key when provided so each wallet has
    # independent circuit breaker state. Fall back to legacy "current" key
    # when no wallet_id is passed (pre-wave-4 callers).
    singleton_key = wallet_id if wallet_id else "current"
    row = {
        "singleton_key": singleton_key,
        "state": state,
        "triggers": triggers,
        "max_exposure_pct": max_exposure_pct,
        "peak_equity": peak_equity,
        "wallet_id": wallet_id,
    }
    result = db.table("wp_circuit_breaker_state").upsert(
        row, on_conflict="singleton_key"
    ).execute()
    return result.data[0] if result.data else row


def load_cb_state(wallet_id: str | None = None) -> dict | None:
    """Load the most recent circuit breaker state from DB.

    When wallet_id is provided, filters to that wallet's row. Otherwise returns
    the most recent row regardless of wallet (back-compat).
    """
    db = get_db()
    query = db.table("wp_circuit_breaker_state").select("*")
    if wallet_id:
        query = query.eq("wallet_id", wallet_id)
    result = (
        query
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]


# ---------------------------------------------------------------------------
# Snapshot cleanup (called once per day from cycle)
# ---------------------------------------------------------------------------

_snapshot_cleanup_done: bool = False


def cleanup_old_snapshots() -> None:
    """Prune old portfolio snapshots: keep all from last 7 days, 1/day for older.

    Only runs once per process lifetime (resets on restart). Safe to call every cycle.
    """
    global _snapshot_cleanup_done
    if _snapshot_cleanup_done:
        return
    _snapshot_cleanup_done = True

    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    db = get_db()

    for table in ("wp_portfolio_snapshots", "wp_auto_portfolio_snapshots"):
        try:
            # Fetch all old snapshot IDs + timestamps
            result = (
                db.table(table)
                .select("id, created_at")
                .lt("created_at", cutoff)
                .order("created_at", desc=True)
                .execute()
            )
            if not result.data:
                continue

            # Group by calendar day, keep only the latest per day
            by_day: dict[str, str] = {}
            for row in result.data:
                day = row["created_at"][:10]  # YYYY-MM-DD
                if day not in by_day:
                    by_day[day] = row["id"]

            keep_ids = set(by_day.values())
            delete_ids = [r["id"] for r in result.data if r["id"] not in keep_ids]

            if not delete_ids:
                continue

            # Delete in batches of 100
            for i in range(0, len(delete_ids), 100):
                batch = delete_ids[i : i + 100]
                db.table(table).delete().in_("id", batch).execute()
        except Exception:
            pass  # Non-critical — will retry next restart
