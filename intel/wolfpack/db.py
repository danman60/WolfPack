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
