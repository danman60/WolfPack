"""Export WolfPack agent outputs as instruction-tuning JSONL for LLM distillation.

Usage:
    python -m wolfpack.export_training_data --dry-run
    python -m wolfpack.export_training_data --output-dir intel/training_data/ --symbol BTC
"""

import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from wolfpack.db import get_db

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the Brief, a crypto trading analyst that synthesizes inputs from "
    "three specialist agents — the Quant (technical analysis), the Snoop "
    "(sentiment and on-chain), and the Sage (macro and scenarios) — into "
    "actionable trade recommendations. Output a concise market assessment and, "
    "when conditions warrant, a specific trade recommendation with entry, stop "
    "loss, take profit, position size, and conviction level (0-100)."
)

AGENT_LABELS = {
    "quant": "Quant Analysis",
    "snoop": "Sentiment Analysis",
    "sage": "Macro Analysis",
}

CYCLE_WINDOW_MINUTES = 5


def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO timestamp string to a timezone-aware datetime."""
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


def _format_signals(signals: list[dict] | None) -> str:
    """Format a list of signal objects into readable text."""
    if not signals:
        return "No signals."
    lines = []
    for sig in signals:
        name = sig.get("name") or sig.get("signal") or sig.get("type", "signal")
        value = sig.get("value", sig.get("score", ""))
        direction = sig.get("direction", "")
        parts = [f"- **{name}**"]
        if value != "":
            parts.append(f": {value}")
        if direction:
            parts.append(f" ({direction})")
        # Include any extra keys as context
        extras = {k: v for k, v in sig.items()
                  if k not in ("name", "signal", "type", "value", "score", "direction")}
        if extras:
            parts.append(f" — {extras}")
        lines.append("".join(parts))
    return "\n".join(lines)


def _build_user_content(agents: dict[str, dict]) -> str:
    """Assemble the user prompt from quant, snoop, sage agent outputs."""
    sections = []
    for agent_name in ("quant", "snoop", "sage"):
        output = agents.get(agent_name)
        if not output:
            continue
        label = AGENT_LABELS[agent_name]
        confidence = output.get("confidence", 0)
        summary = output.get("summary", "No summary available.")
        signals = output.get("signals", [])
        section = (
            f"## {label} (confidence: {confidence:.2f})\n"
            f"{summary}\n\n"
            f"### Signals\n"
            f"{_format_signals(signals)}"
        )
        sections.append(section)
    return "\n\n".join(sections)


def _build_assistant_content(brief: dict, recommendation: dict | None) -> str:
    """Assemble the assistant response from Brief output + recommendation."""
    parts = [brief.get("summary", "No summary available.")]

    if recommendation:
        rec = recommendation
        rec_lines = [
            "",
            "## Trade Recommendation",
            f"- **Symbol:** {rec.get('symbol', 'N/A')}",
            f"- **Direction:** {rec.get('direction', 'N/A')}",
            f"- **Conviction:** {rec.get('conviction', 'N/A')}",
        ]
        if rec.get("entry_price") is not None:
            rec_lines.append(f"- **Entry:** {rec['entry_price']}")
        if rec.get("stop_loss") is not None:
            rec_lines.append(f"- **Stop Loss:** {rec['stop_loss']}")
        if rec.get("take_profit") is not None:
            rec_lines.append(f"- **Take Profit:** {rec['take_profit']}")
        if rec.get("size_pct") is not None:
            rec_lines.append(f"- **Position Size:** {rec['size_pct']}%")
        if rec.get("rationale"):
            rec_lines.append(f"\n**Rationale:** {rec['rationale']}")
        parts.append("\n".join(rec_lines))

    return "\n".join(parts)


def _group_into_cycles(outputs: list[dict]) -> list[list[dict]]:
    """Group agent outputs into intel cycles (within CYCLE_WINDOW_MINUTES of each other)."""
    if not outputs:
        return []

    # Sort by created_at
    sorted_outputs = sorted(outputs, key=lambda r: r["created_at"])

    cycles: list[list[dict]] = []
    current_cycle: list[dict] = [sorted_outputs[0]]
    cycle_start = _parse_ts(sorted_outputs[0]["created_at"])

    for row in sorted_outputs[1:]:
        row_ts = _parse_ts(row["created_at"])
        if (row_ts - cycle_start) <= timedelta(minutes=CYCLE_WINDOW_MINUTES):
            current_cycle.append(row)
        else:
            cycles.append(current_cycle)
            current_cycle = [row]
            cycle_start = row_ts

    if current_cycle:
        cycles.append(current_cycle)

    return cycles


def _paginated_fetch(db, table: str, min_date: str | None = None) -> list[dict]:
    """Fetch all rows from a table with pagination."""
    all_rows: list[dict] = []
    offset = 0
    batch_size = 1000
    while True:
        query = db.table(table).select("*").order("created_at")
        if min_date:
            query = query.gte("created_at", min_date)
        result = query.range(offset, offset + batch_size - 1).execute()
        rows = result.data or []
        all_rows.extend(rows)
        if len(rows) < batch_size:
            break
        offset += batch_size
    return all_rows


def fetch_all_agent_outputs(db, min_date: str | None = None) -> list[dict]:
    """Fetch all agent outputs, optionally filtered by date."""
    return _paginated_fetch(db, "wp_agent_outputs", min_date)


def fetch_all_recommendations(db, min_date: str | None = None) -> list[dict]:
    """Fetch all trade recommendations, optionally filtered by date."""
    return _paginated_fetch(db, "wp_trade_recommendations", min_date)


def match_recommendation_to_cycle(
    cycle_agents: dict[str, dict],
    recommendations: list[dict],
) -> dict | None:
    """Find a recommendation that matches a cycle by agent_output_id or timestamp."""
    brief = cycle_agents.get("brief")
    if not brief:
        return None

    brief_id = brief.get("id")
    brief_ts = _parse_ts(brief["created_at"])

    # First try exact match via agent_output_id
    for rec in recommendations:
        if rec.get("agent_output_id") == brief_id:
            return rec

    # Fall back to timestamp proximity
    window = timedelta(minutes=CYCLE_WINDOW_MINUTES)
    best: dict | None = None
    best_delta = window
    for rec in recommendations:
        rec_ts = _parse_ts(rec["created_at"])
        delta = abs(rec_ts - brief_ts)
        if delta <= best_delta:
            best_delta = delta
            best = rec
    return best


def build_training_examples(
    outputs: list[dict],
    recommendations: list[dict],
    symbol_filter: str | None = None,
) -> list[dict]:
    """Build instruction-tuning examples from agent outputs and recommendations."""
    cycles = _group_into_cycles(outputs)
    examples: list[dict] = []
    stats = {
        "total_cycles": len(cycles),
        "complete_cycles": 0,
        "incomplete_cycles": 0,
        "matched_recommendations": 0,
        "by_symbol": defaultdict(int),
        "by_status": defaultdict(int),
        "by_direction": defaultdict(int),
    }

    for cycle in cycles:
        # Group by agent_name — keep latest per agent within cycle
        agents: dict[str, dict] = {}
        for row in cycle:
            name = row["agent_name"]
            if name not in agents or row["created_at"] > agents[name]["created_at"]:
                agents[name] = row

        # Need all 4 agents for a complete cycle
        required = {"quant", "snoop", "sage", "brief"}
        if not required.issubset(agents.keys()):
            stats["incomplete_cycles"] += 1
            continue

        stats["complete_cycles"] += 1

        # Match recommendation
        rec = match_recommendation_to_cycle(agents, recommendations)

        # Determine symbol from recommendation or brief signals
        symbol = "MULTI"
        if rec:
            symbol = rec.get("symbol", "MULTI")
        elif agents["brief"].get("signals"):
            for sig in agents["brief"]["signals"]:
                if sig.get("symbol"):
                    symbol = sig["symbol"]
                    break

        # Apply symbol filter
        if symbol_filter and symbol.upper() != symbol_filter.upper():
            continue

        # Build the training example
        user_content = _build_user_content(agents)
        assistant_content = _build_assistant_content(agents["brief"], rec)

        cycle_time = agents["brief"]["created_at"]
        exchange = agents["brief"].get("exchange_id", "unknown")

        metadata: dict = {
            "cycle_time": cycle_time,
            "symbol": symbol,
            "exchange": exchange,
        }
        if rec:
            stats["matched_recommendations"] += 1
            metadata["recommendation_status"] = rec.get("status", "unknown")
            metadata["recommendation_direction"] = rec.get("direction", "unknown")
            metadata["conviction"] = rec.get("conviction", 0)
            stats["by_status"][rec.get("status", "unknown")] += 1
            stats["by_direction"][rec.get("direction", "unknown")] += 1

        stats["by_symbol"][symbol] += 1

        example = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": assistant_content},
            ],
            "metadata": metadata,
        }
        examples.append(example)

    return examples, stats


def format_training_pair(
    quant_output: dict | None,
    snoop_output: dict | None,
    sage_output: dict | None,
    brief_output: dict | None,
    recommendations: list[dict] | None = None,
) -> dict | None:
    """Format a single intel cycle into an instruction-tuning training pair.

    Args:
        quant_output: Quant agent output dict (must have summary, confidence, signals).
        snoop_output: Snoop agent output dict.
        sage_output: Sage agent output dict.
        brief_output: Brief agent output dict.
        recommendations: List of stored trade recommendation dicts.

    Returns:
        A training example dict with messages and metadata, or None if incomplete.
    """
    if not brief_output:
        return None

    # Build agent dict in the format _build_user_content expects
    agents: dict[str, dict] = {}
    for name, output in [("quant", quant_output), ("snoop", snoop_output), ("sage", sage_output)]:
        if output:
            agents[name] = output

    if not agents:
        return None

    user_content = _build_user_content(agents)

    # Pick the first recommendation (if any) for the assistant response
    rec = recommendations[0] if recommendations else None
    assistant_content = _build_assistant_content(brief_output, rec)

    # Determine symbol
    symbol = "MULTI"
    if rec:
        symbol = rec.get("symbol", "MULTI")

    metadata: dict = {
        "cycle_time": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
    }
    if rec:
        metadata["recommendation_status"] = rec.get("status", "pending")
        metadata["recommendation_direction"] = rec.get("direction", "unknown")
        metadata["conviction"] = rec.get("conviction", 0)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ],
        "metadata": metadata,
    }


def append_training_pair(
    training_pair: dict,
    symbol: str,
    output_dir: str = "training_data",
) -> str:
    """Append a single training pair as one JSONL line to the symbol-specific file.

    Args:
        training_pair: The training example dict from format_training_pair.
        symbol: Trading symbol (e.g. "BTC", "ETH").
        output_dir: Directory to write JSONL files into.

    Returns:
        The file path that was written to.
    """
    os.makedirs(output_dir, exist_ok=True)
    safe_name = symbol.replace("/", "-").replace(" ", "_").lower()
    filepath = os.path.join(output_dir, f"{safe_name}.jsonl")
    with open(filepath, "a") as f:
        f.write(json.dumps(training_pair) + "\n")
    return filepath


def write_examples(
    examples: list[dict],
    output_dir: str,
    fmt: str = "jsonl",
) -> dict[str, int]:
    """Write examples to output directory, split by symbol. Returns file counts."""
    os.makedirs(output_dir, exist_ok=True)

    # Group by symbol
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for ex in examples:
        symbol = ex["metadata"]["symbol"]
        by_symbol[symbol].append(ex)

    file_counts: dict[str, int] = {}
    for symbol, symbol_examples in by_symbol.items():
        safe_name = symbol.replace("/", "-").replace(" ", "_").lower()
        if fmt == "jsonl":
            filepath = os.path.join(output_dir, f"{safe_name}.jsonl")
            with open(filepath, "w") as f:
                for ex in symbol_examples:
                    f.write(json.dumps(ex) + "\n")
        else:
            filepath = os.path.join(output_dir, f"{safe_name}.json")
            with open(filepath, "w") as f:
                json.dump(symbol_examples, f, indent=2)

        file_counts[filepath] = len(symbol_examples)
        logger.info("Wrote %d examples to %s", len(symbol_examples), filepath)

    return file_counts


def main():
    parser = argparse.ArgumentParser(
        description="Export WolfPack agent outputs as instruction-tuning data"
    )
    parser.add_argument(
        "--output-dir",
        default="intel/training_data/",
        help="Output directory for JSONL files (default: intel/training_data/)",
    )
    parser.add_argument(
        "--min-date",
        default=None,
        help="Only include cycles after this date (ISO format, e.g. 2026-01-01)",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="Filter by trading symbol (e.g. BTC, ETH)",
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "json"],
        default="jsonl",
        help="Output format (default: jsonl)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stats without writing files",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("Connecting to Supabase...")
    db = get_db()

    logger.info("Fetching agent outputs...")
    outputs = fetch_all_agent_outputs(db, min_date=args.min_date)
    logger.info("Fetched %d agent outputs", len(outputs))

    logger.info("Fetching trade recommendations...")
    recommendations = fetch_all_recommendations(db, min_date=args.min_date)
    logger.info("Fetched %d trade recommendations", len(recommendations))

    logger.info("Building training examples...")
    examples, stats = build_training_examples(
        outputs, recommendations, symbol_filter=args.symbol
    )

    # Print stats
    print("\n=== Training Data Export Stats ===")
    print(f"Total cycles found:      {stats['total_cycles']}")
    print(f"Complete cycles (4/4):   {stats['complete_cycles']}")
    print(f"Incomplete (skipped):    {stats['incomplete_cycles']}")
    print(f"Matched recommendations: {stats['matched_recommendations']}")
    print(f"Training examples:       {len(examples)}")

    if stats["by_symbol"]:
        print("\nBy symbol:")
        for sym, count in sorted(stats["by_symbol"].items()):
            print(f"  {sym:12s} {count:>5d}")

    if stats["by_status"]:
        print("\nBy recommendation status:")
        for status, count in sorted(stats["by_status"].items()):
            print(f"  {status:12s} {count:>5d}")

    if stats["by_direction"]:
        print("\nBy direction:")
        for direction, count in sorted(stats["by_direction"].items()):
            print(f"  {direction:12s} {count:>5d}")

    if args.dry_run:
        print("\n[DRY RUN] No files written.")
        return

    if not examples:
        print("\nNo training examples to write.")
        return

    file_counts = write_examples(examples, args.output_dir, fmt=args.format)
    print(f"\nWrote {len(examples)} examples to {len(file_counts)} files in {args.output_dir}")
    for path, count in file_counts.items():
        print(f"  {path}: {count} examples")


if __name__ == "__main__":
    main()
