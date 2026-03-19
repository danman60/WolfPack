"""Prediction scorer — evaluates past trade recommendations against actual price moves."""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


async def score_predictions(days: int = 7) -> dict:
    """Score trade recommendations from the last N days.

    For each recommendation where 24h+ has elapsed since creation:
    1. Fetch the price at prediction time and 24h later
    2. Score: correct if price moved >0.5% in predicted direction
    3. Insert/update wp_prediction_performance
    """
    from wolfpack.db import get_db

    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    scoring_threshold = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    # Get recommendations that are old enough to score but haven't been scored yet
    result = db.table("wp_trade_recommendations").select("*").gte(
        "created_at", cutoff
    ).lte(
        "created_at", scoring_threshold
    ).neq(
        "status", "pending"
    ).execute()

    recs = result.data or []
    if not recs:
        return {"scored": 0, "message": "No recommendations ready to score"}

    # Check which ones are already scored
    rec_ids = [r["id"] for r in recs]
    scored_result = db.table("wp_prediction_performance").select("recommendation_id").in_(
        "recommendation_id", rec_ids
    ).execute()
    already_scored = {r["recommendation_id"] for r in (scored_result.data or [])}

    unscored = [r for r in recs if r["id"] not in already_scored]
    if not unscored:
        return {"scored": 0, "message": "All eligible recommendations already scored"}

    scored_count = 0
    for rec in unscored:
        try:
            symbol = rec.get("symbol", "BTC")
            direction = rec.get("direction", "long")
            exchange_id = rec.get("exchange_id", "hyperliquid")
            entry_price = rec.get("entry_price")

            if not entry_price:
                continue

            # Fetch price 24h after recommendation
            from wolfpack.exchanges import get_exchange
            adapter = get_exchange(exchange_id)  # type: ignore[arg-type]

            # Get candles around the 24h mark
            rec_time = datetime.fromisoformat(rec["created_at"])
            if rec_time.tzinfo is None:
                rec_time = rec_time.replace(tzinfo=timezone.utc)
            target_time = rec_time + timedelta(hours=24)

            candles = await adapter.get_candles(
                symbol, interval="1h", limit=2,
                start_time=int(target_time.timestamp() * 1000)
            )

            if not candles:
                continue

            price_after = candles[0].close

            # Score direction
            price_change_pct = ((price_after - entry_price) / entry_price) * 100
            if direction == "long":
                outcome = "correct" if price_change_pct > 0.5 else ("incorrect" if price_change_pct < -0.5 else "neutral")
                pnl_pct = price_change_pct
            else:  # short
                outcome = "correct" if price_change_pct < -0.5 else ("incorrect" if price_change_pct > 0.5 else "neutral")
                pnl_pct = -price_change_pct

            db.table("wp_prediction_performance").insert({
                "recommendation_id": rec["id"],
                "agent_name": "brief",
                "exchange_id": exchange_id,
                "symbol": symbol,
                "predicted_direction": direction,
                "predicted_conviction": rec.get("conviction"),
                "predicted_at": rec["created_at"],
                "price_at_prediction": entry_price,
                "price_after": price_after,
                "check_interval_hours": 24,
                "outcome": outcome,
                "pnl_pct": round(pnl_pct, 4),
                "scored_at": datetime.now(timezone.utc).isoformat(),
            }).execute()

            scored_count += 1
            logger.info(f"[scorer] {symbol} {direction}: {outcome} ({pnl_pct:+.2f}%)")

        except Exception as e:
            logger.warning(f"[scorer] Failed to score rec {rec.get('id')}: {e}")

    return {"scored": scored_count, "total_eligible": len(unscored)}


def get_prediction_accuracy(days: int = 7) -> dict:
    """Get accuracy stats for the last N days."""
    from wolfpack.db import get_db

    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    result = db.table("wp_prediction_performance").select("outcome").gte(
        "scored_at", cutoff
    ).execute()

    rows = result.data or []
    total = len(rows)
    if total == 0:
        return {"accuracy_pct": 0, "total_scored": 0, "correct": 0, "incorrect": 0, "neutral": 0}

    correct = sum(1 for r in rows if r["outcome"] == "correct")
    incorrect = sum(1 for r in rows if r["outcome"] == "incorrect")
    neutral = sum(1 for r in rows if r["outcome"] == "neutral")
    scorable = correct + incorrect
    accuracy = round((correct / scorable) * 100, 1) if scorable > 0 else 0

    return {
        "accuracy_pct": accuracy,
        "total_scored": total,
        "correct": correct,
        "incorrect": incorrect,
        "neutral": neutral,
    }


def get_prediction_history(days: int = 7) -> list[dict]:
    """Get scored predictions with timestamps for charting."""
    from wolfpack.db import get_db

    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    result = db.table("wp_prediction_performance").select("*").gte(
        "scored_at", cutoff
    ).order("predicted_at", desc=False).execute()

    return result.data or []
