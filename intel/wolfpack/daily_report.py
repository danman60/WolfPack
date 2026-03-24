"""WolfPack Daily Intelligence Report — 9 AM ET email digest.

Queries the intel API for the last 24h:
- Paper trades executed, P&L, portfolio state
- Prediction accuracy (scored vs actual)
- Recommendations generated, acted on, hit rates
- Module health, cycle count, agent performance
- Monte Carlo robustness, regime history

Sends dark-theme HTML email via Resend API.
Runs as: python -m wolfpack.daily_report
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("wolfpack.daily_report")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
TO_EMAIL = "danieljohnabrahamson@gmail.com"
FROM_EMAIL = "WolfPack Intel <onboarding@resend.dev>"
API_BASE = "http://localhost:8000"
AUTH_TOKEN = os.environ.get("API_SECRET_KEY", "")


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        h["Authorization"] = f"Bearer {AUTH_TOKEN}"
    return h


def _get(path: str) -> dict:
    """GET from the local intel API."""
    try:
        r = httpx.get(f"{API_BASE}{path}", headers=_headers(), timeout=15)
        return r.json()
    except Exception as e:
        logger.warning(f"API call failed: {path}: {e}")
        return {}


def _post(path: str) -> dict:
    """POST to the local intel API."""
    try:
        r = httpx.post(f"{API_BASE}{path}", headers=_headers(), timeout=30)
        return r.json()
    except Exception as e:
        logger.warning(f"API POST failed: {path}: {e}")
        return {}


def _pnl_color(val: float) -> str:
    if val > 0:
        return "#4ade80"
    elif val < 0:
        return "#f87171"
    return "#64748b"


def _pnl_prefix(val: float) -> str:
    if val > 0:
        return f"+${val:,.2f}"
    elif val < 0:
        return f"-${abs(val):,.2f}"
    return "$0.00"


def _pct_color(val: float) -> str:
    if val >= 70:
        return "#4ade80"
    elif val >= 50:
        return "#fbbf24"
    return "#f87171"


def gather_data() -> dict:
    """Collect all data from the intel API for the report."""
    data = {}

    # Portfolio state
    data["portfolio"] = _get("/portfolio")

    # Trade history
    data["trades"] = _get("/portfolio/trades?limit=50")

    # Recommendations
    data["recommendations"] = _get("/intelligence/recommendations?limit=50")

    # Agent status
    data["agents"] = _get("/agents/status")

    # Module status
    data["modules"] = _get("/modules/status")

    # Auto-trader status
    data["auto_trader"] = _get("/auto-trader/status")

    # Prediction accuracy
    data["accuracy"] = _get("/predictions/accuracy?days=1")

    # Health
    data["health"] = _get("/health/deep")

    # Circuit breaker
    data["circuit_breaker"] = _get("/circuit-breaker")

    return data


def filter_24h(items: list, date_key: str = "created_at") -> list:
    """Filter items to last 24 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = []
    for item in items:
        ts_str = item.get(date_key)
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts >= cutoff:
                result.append(item)
        except (ValueError, TypeError):
            continue
    return result


def build_html(data: dict) -> str:
    """Build the dark-theme HTML email."""
    now_et = datetime.now(timezone(timedelta(hours=-4)))
    date_display = now_et.strftime("%A, %B %-d, %Y")
    generated_time = now_et.strftime("%I:%M %p ET")

    # Portfolio
    portfolio = data.get("portfolio", {})
    equity = portfolio.get("equity", 0)
    starting = portfolio.get("starting_equity", 10000)
    realized = portfolio.get("realized_pnl", 0)
    unrealized = portfolio.get("unrealized_pnl", 0)
    total_pnl = realized + unrealized
    total_pnl_pct = (total_pnl / starting * 100) if starting > 0 else 0
    positions = portfolio.get("positions", [])
    win_rate = portfolio.get("win_rate", 0) * 100
    closed_trades_total = portfolio.get("closed_trades", 0)

    # Trades in last 24h
    all_trades = data.get("trades", {}).get("trades", [])
    recent_trades = filter_24h(all_trades, "closed_at")
    trades_24h_pnl = sum(t.get("pnl_usd", 0) for t in recent_trades)
    trades_24h_count = len(recent_trades)
    trades_24h_wins = sum(1 for t in recent_trades if t.get("pnl_usd", 0) > 0)

    # Recommendations in last 24h
    all_recs = data.get("recommendations", {}).get("recommendations", [])
    recent_recs = filter_24h(all_recs)
    recs_24h = len(recent_recs)
    recs_acted = sum(1 for r in recent_recs if r.get("status") in ("approved", "executed"))
    recs_pending = sum(1 for r in recent_recs if r.get("status") == "pending")
    avg_conviction = (
        sum(r.get("conviction", 0) for r in recent_recs) / len(recent_recs)
        if recent_recs else 0
    )

    # Prediction accuracy
    accuracy = data.get("accuracy", {})
    accuracy_pct = accuracy.get("accuracy_pct", 0)
    total_scored = accuracy.get("total_scored", 0)

    # Auto-trader
    auto = data.get("auto_trader", {})
    auto_enabled = auto.get("enabled", False)

    # Health
    health = data.get("health", {})
    health_status = health.get("status", "unknown")
    cb = data.get("circuit_breaker", {})
    cb_state = cb.get("state", "UNKNOWN")

    # Agents
    agents = data.get("agents", {}).get("agents", [])

    # --- Build HTML ---
    trades_rows = ""
    for t in recent_trades[:10]:
        symbol = t.get("symbol", "?")
        direction = t.get("direction", "?")
        entry = t.get("entry_price", 0)
        exit_p = t.get("exit_price", 0)
        pnl = t.get("pnl_usd", 0)
        size = t.get("size_usd", 0)
        pnl_pct = (pnl / size * 100) if size > 0 else 0
        dir_color = "#4ade80" if direction == "long" else "#f87171"
        closed = t.get("closed_at", "")[:16].replace("T", " ")

        trades_rows += f"""<tr>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#cbd5e1;font-weight:600;">{symbol}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);"><span style="color:{dir_color};font-weight:600;">{direction.upper()}</span></td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#cbd5e1;">${entry:,.0f}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#cbd5e1;">${exit_p:,.0f}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:{_pnl_color(pnl)};font-weight:600;">{_pnl_prefix(pnl)}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:{_pnl_color(pnl_pct)};">{pnl_pct:+.1f}%</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#64748b;font-size:11px;">{closed}</td>
</tr>"""

    if not trades_rows:
        trades_rows = '<tr><td colspan="7" style="padding:12px 6px;color:#475569;font-style:italic;">No trades closed in last 24h</td></tr>'

    # Open positions
    positions_rows = ""
    for p in positions:
        symbol = p.get("symbol", "?")
        direction = p.get("direction", "?")
        entry = p.get("entry_price", 0)
        current = p.get("current_price", 0)
        upnl = p.get("unrealized_pnl", 0)
        dir_color = "#4ade80" if direction == "long" else "#f87171"
        positions_rows += f"""<tr>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#cbd5e1;font-weight:600;">{symbol}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);"><span style="color:{dir_color};font-weight:600;">{direction.upper()}</span></td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#cbd5e1;">${entry:,.2f}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#cbd5e1;">${current:,.2f}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:{_pnl_color(upnl)};font-weight:600;">{_pnl_prefix(upnl)}</td>
</tr>"""

    # Recommendation log
    recs_rows = ""
    for r in recent_recs[:8]:
        symbol = r.get("symbol", "?")
        direction = r.get("direction", "?")
        conviction = r.get("conviction", 0)
        status = r.get("status", "?")
        rationale = r.get("rationale", "")[:60]
        dir_color = "#4ade80" if direction == "long" else ("#f87171" if direction == "short" else "#64748b")
        status_colors = {"executed": "#4ade80", "approved": "#38bdf8", "pending": "#fbbf24", "rejected": "#f87171"}
        s_color = status_colors.get(status, "#64748b")
        created = r.get("created_at", "")[:16].replace("T", " ")

        recs_rows += f"""<tr>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#64748b;font-size:11px;">{created}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#cbd5e1;font-weight:600;">{symbol}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);"><span style="color:{dir_color};font-weight:600;">{direction.upper()}</span></td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:{_pct_color(conviction)};">{conviction}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);"><span style="color:{s_color};font-weight:600;">{status.upper()}</span></td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#94a3b8;font-size:11px;">{rationale}</td>
</tr>"""

    # Agent status rows
    agent_rows = ""
    for a in agents:
        name = a.get("name", "?")
        last_run = a.get("last_run", "never")
        if last_run and last_run != "never":
            try:
                lr = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                ago = (datetime.now(timezone.utc) - lr).total_seconds() / 60
                last_display = f"{ago:.0f}m ago"
                health_dot = "🟢" if ago < 60 else ("🟡" if ago < 360 else "🔴")
            except (ValueError, TypeError):
                last_display = "?"
                health_dot = "⚪"
        else:
            last_display = "never"
            health_dot = "🔴"

        agent_rows += f"""<tr>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#cbd5e1;">{health_dot} {name}</td>
<td style="padding:7px 6px;border-bottom:1px solid rgba(51,65,85,0.5);color:#94a3b8;">{last_display}</td>
</tr>"""

    # CB state styling
    cb_colors = {"ACTIVE": "#4ade80", "SUSPENDED": "#fbbf24", "EMERGENCY_STOP": "#f87171"}
    cb_color = cb_colors.get(cb_state, "#64748b")

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px;margin:0;">
<div style="max-width:720px;margin:0 auto;">

<!-- Header -->
<div style="background:linear-gradient(135deg,#1e293b 0%,#312e81 100%);border:1px solid #334155;border-radius:16px 16px 0 0;padding:32px;">
<h1 style="font-size:24px;font-weight:700;color:#f1f5f9;margin:0;">WolfPack Intelligence Report</h1>
<div style="font-size:14px;color:#94a3b8;margin-top:4px;">{date_display} &mdash; 24h Digest</div>
</div>

<div style="background:#1e293b;border:1px solid #334155;border-top:none;border-radius:0 0 16px 16px;padding:28px 24px;">

<!-- Stats Grid -->
<table width="100%" cellpadding="0" cellspacing="4" style="margin-bottom:24px;"><tr>
<td style="background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px 6px;text-align:center;width:14%;">
  <div style="font-size:20px;font-weight:800;color:#f1f5f9;">${equity:,.0f}</div>
  <div style="font-size:9px;color:#64748b;text-transform:uppercase;margin-top:4px;">Equity</div></td>
<td style="background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px 6px;text-align:center;width:14%;">
  <div style="font-size:20px;font-weight:800;color:{_pnl_color(total_pnl)};">{_pnl_prefix(total_pnl)}</div>
  <div style="font-size:9px;color:#64748b;text-transform:uppercase;margin-top:4px;">Total P&L</div></td>
<td style="background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px 6px;text-align:center;width:14%;">
  <div style="font-size:20px;font-weight:800;color:{_pnl_color(trades_24h_pnl)};">{_pnl_prefix(trades_24h_pnl)}</div>
  <div style="font-size:9px;color:#64748b;text-transform:uppercase;margin-top:4px;">24h P&L</div></td>
<td style="background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px 6px;text-align:center;width:14%;">
  <div style="font-size:20px;font-weight:800;color:#38bdf8;">{trades_24h_count}</div>
  <div style="font-size:9px;color:#64748b;text-transform:uppercase;margin-top:4px;">Trades 24h</div></td>
<td style="background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px 6px;text-align:center;width:14%;">
  <div style="font-size:20px;font-weight:800;color:{_pct_color(win_rate)};">{win_rate:.0f}%</div>
  <div style="font-size:9px;color:#64748b;text-transform:uppercase;margin-top:4px;">Win Rate</div></td>
<td style="background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px 6px;text-align:center;width:14%;">
  <div style="font-size:20px;font-weight:800;color:#a78bfa;">{recs_24h}</div>
  <div style="font-size:9px;color:#64748b;text-transform:uppercase;margin-top:4px;">Signals</div></td>
<td style="background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px 6px;text-align:center;width:14%;">
  <div style="font-size:20px;font-weight:800;color:{cb_color};">{cb_state}</div>
  <div style="font-size:9px;color:#64748b;text-transform:uppercase;margin-top:4px;">Circuit</div></td>
</tr></table>

<!-- Trades -->
<h2 style="font-size:14px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin:24px 0 12px 0;padding-bottom:8px;border-bottom:1px solid #334155;">Closed Trades (24h)</h2>
<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
<thead><tr>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Symbol</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Side</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Entry</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Exit</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">P&L</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">%</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Closed</th>
</tr></thead>
<tbody>{trades_rows}</tbody>
</table>"""

    # Open positions section (only if there are any)
    if positions:
        html += f"""
<!-- Open Positions -->
<h2 style="font-size:14px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin:24px 0 12px 0;padding-bottom:8px;border-bottom:1px solid #334155;">Open Positions ({len(positions)})</h2>
<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
<thead><tr>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Symbol</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Side</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Entry</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Current</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Unrealized P&L</th>
</tr></thead>
<tbody>{positions_rows}</tbody>
</table>"""

    html += f"""
<!-- Recommendations -->
<h2 style="font-size:14px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin:24px 0 12px 0;padding-bottom:8px;border-bottom:1px solid #334155;">Intelligence Signals (24h)</h2>
<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
<thead><tr>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Time</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Symbol</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Dir</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Conv</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Status</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Rationale</th>
</tr></thead>
<tbody>{recs_rows if recs_rows else '<tr><td colspan="6" style="padding:12px 6px;color:#475569;font-style:italic;">No signals generated in last 24h</td></tr>'}</tbody>
</table>

<!-- System Health -->
<h2 style="font-size:14px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin:24px 0 12px 0;padding-bottom:8px;border-bottom:1px solid #334155;">System Health</h2>
<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
<thead><tr>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Agent</th>
<th style="padding:8px 6px;text-align:left;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase;border-bottom:1px solid #334155;">Last Run</th>
</tr></thead>
<tbody>{agent_rows}</tbody>
</table>

<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:8px;">
<tr><td style="padding:4px 6px;color:#94a3b8;">Auto-trader</td><td style="padding:4px 6px;color:{'#4ade80' if auto_enabled else '#f87171'};font-weight:600;">{'ENABLED' if auto_enabled else 'DISABLED'}</td></tr>
<tr><td style="padding:4px 6px;color:#94a3b8;">Circuit Breaker</td><td style="padding:4px 6px;color:{cb_color};font-weight:600;">{cb_state}</td></tr>
<tr><td style="padding:4px 6px;color:#94a3b8;">Service Health</td><td style="padding:4px 6px;color:{'#4ade80' if health_status == 'healthy' else '#fbbf24'};font-weight:600;">{health_status.upper()}</td></tr>
<tr><td style="padding:4px 6px;color:#94a3b8;">Prediction Accuracy</td><td style="padding:4px 6px;color:{_pct_color(accuracy_pct)};font-weight:600;">{accuracy_pct:.0f}% ({total_scored} scored)</td></tr>
<tr><td style="padding:4px 6px;color:#94a3b8;">All-time Trades</td><td style="padding:4px 6px;color:#cbd5e1;">{closed_trades_total} closed</td></tr>
</table>

<!-- Footer -->
<div style="text-align:center;font-size:11px;color:#475569;margin-top:20px;padding-top:16px;border-top:1px solid #334155;">
Generated at {generated_time} &mdash; WolfPack Intel v0.1
</div>
</div>
</div>
</body>
</html>"""

    return html


def send_email(html: str, subject: str) -> bool:
    """Send HTML email via Resend API."""
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY not set — cannot send email")
        return False

    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_EMAIL,
                "to": [TO_EMAIL],
                "subject": subject,
                "html": html,
            },
            timeout=30,
        )
        if r.status_code in (200, 201):
            resp = r.json()
            logger.info(f"Email sent: {resp.get('id', 'ok')}")
            return True
        else:
            logger.error(f"Resend API error {r.status_code}: {r.text}")
            return False
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def main():
    """Generate and send the daily report."""
    logger.info("Generating WolfPack daily intelligence report...")

    data = gather_data()
    html = build_html(data)

    now_et = datetime.now(timezone(timedelta(hours=-4)))
    subject = f"WolfPack Intel Report — {now_et.strftime('%b %-d, %Y')}"

    # Save locally for debugging
    report_path = "/tmp/wolfpack-daily-report.html"
    with open(report_path, "w") as f:
        f.write(html)
    logger.info(f"Report saved to {report_path}")

    if send_email(html, subject):
        logger.info(f"Report sent to {TO_EMAIL}")
    else:
        logger.error("Failed to send report email")
        sys.exit(1)


if __name__ == "__main__":
    main()
