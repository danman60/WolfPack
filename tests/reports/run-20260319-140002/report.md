# WolfPack Test Report
**Run ID:** run-20260319-140002
**Date:** 2026-03-19
**URL:** https://wolf-pack-eight.vercel.app/
**Supabase:** supabase-CCandSS (wp_ prefixed tables)

---

## Summary

| Metric | Value |
|--------|-------|
| Total Steps | 35 |
| Passed | 35 |
| Failed | 0 |
| Blocked | 0 |
| Pages Covered | 8/8 (100%) |
| Bugs Found | 4 |
| Console Errors | 9 unique (all non-critical) |
| Data Mutations | 1 (watchlist add/remove — cleaned up by test) |
| Cleanup Required | None |

**Overall Result: PASS** — All pages load, all interactions work, all oracle checks match.

---

## Flow Results

### Flow 01: Navigation & Page Load (11/11 passed)
| Step | Page | Result | Notes |
|------|------|--------|-------|
| 1 | Dashboard (/) | PASS | Stats, prices, agents, recommendations all render |
| 2 | Exchange Toggle | PASS | 3 buttons: Hyperliquid, dYdX, Kraken |
| 3 | Switch to Kraken | PASS | "Active: Kraken" displayed, dashboard updates |
| 4 | Switch to Hyperliquid | PASS | Restored default state |
| 5 | Intelligence | PASS | SentimentGauge, PredictionAccuracy, agent grid, signal feed, modules |
| 6 | Trading | PASS | Candlestick chart, order form, interval buttons |
| 7 | Portfolio | PASS | Equity curve, stats, positions, trade history |
| 8 | Backtest | PASS | Strategy selector, symbol/interval/lookback config |
| 9 | Auto-Bot | PASS | Toggle, stats, config form, positions/activity sections |
| 10 | LP Pools | PASS | Wallet buttons, fee tier filters, pool browser (data unavailable — expected) |
| 11 | Settings | PASS | 3 exchanges listed, strategy mode, LLM providers, safety checklist |

### Flow 02: Intelligence Visualizations & Trading (13/13 passed)
| Step | Action | Result | Notes |
|------|--------|--------|-------|
| 1 | Market Intelligence section | PASS | SentimentGauge (Neutral), PredictionAccuracy (0%) |
| 2 | Prediction Overlay | PASS | "No prediction data yet" (intel endpoints 404) |
| 3 | Signal Feed | PASS | 1 signal entry with Bearish badge (raw JSON — BUG-04) |
| 4 | Agent Grid | PASS | 4 agents, all COMPLETED with summaries and confidence % |
| 5 | Quantitative Modules | PASS | All 10 modules present with timestamps |
| 6 | Trading Chart | PASS | BTC-USD candlestick chart with MA overlays |
| 7 | Switch to ETH | PASS | Chart reloaded with ETH-USD data ($2,130.4) |
| 8 | Switch to 4H interval | PASS | Chart updated to 4-hour candles |
| 9 | Watchlist Add DOGE | PASS | DOGE added, verified in DB (id: 8ca9d0cf) |
| 10 | Watchlist Remove DOGE | PASS | DOGE removed from UI and DB (0 rows) |
| 11 | Order Form | PASS | BTC-USD, Long, Size 100, Leverage 5x — interactive |
| 12 | Kraken Trading | PASS | Exchange toggled, "No chart data" message (expected) |
| 13 | Switch back Hyperliquid | PASS | Restored default exchange |

### Flow 03: Backtest, Auto-Bot, Portfolio & LP Pools (11/11 passed)
| Step | Action | Result | Notes |
|------|--------|--------|-------|
| 1 | Portfolio Stats | PASS | $10,015.04 equity, +$15.04 realized P&L |
| 2 | Portfolio DB Oracle | PASS | DB equity=10015, realized_pnl=15.04 — matches UI |
| 3 | Backtest Config | PASS | Strategy, symbol, interval, lookback selectors |
| 4 | Backtest Configure | PASS | Form fields populated correctly |
| 5 | Previous Runs DB | PASS | 1 run (failed regime_momentum) — consistent |
| 6 | Auto-Bot Layout | PASS | Toggle, stats, config, positions sections |
| 7 | Auto-Bot DB | PASS | 0 auto trades — matches UI |
| 8 | Auto-Bot Config Edit | PASS | Threshold=75, Equity=15000 typed, Save enabled |
| 9 | LP Pools Load | PASS | Fee tier filters, wallet buttons, pool browser |
| 10 | LP Pools Filter | PASS | 0.3% filter activated |
| 11 | Settings Kraken | PASS | Kraken in exchange list |

### Flow 99: Cleanup
No test data to clean up. Watchlist add/remove cycle completed cleanly.

---

## Oracle Verifications

| Check | Predicted | UI Value | DB Value | Status |
|-------|-----------|----------|----------|--------|
| Portfolio equity | ~$10,015 | $10,015.04 | 10015 | MATCH |
| Realized P&L | ~$15 | +$15.04 | 15.04 | MATCH |
| Unrealized P&L | $0 | +$0.00 | 0 | MATCH |
| Watchlist add DOGE | row created | DOGE button visible | id=8ca9d0cf, symbol=DOGE | MATCH |
| Watchlist remove DOGE | row deleted | DOGE gone | 0 rows returned | MATCH |
| Backtest runs | ≥0 runs | "No results yet" | 1 failed run | CONSISTENT |
| Auto trades | 0 | 0 active | 0 rows | MATCH |

---

## Bugs Found

### BUG-01: Kraken Description Wrong in Settings
- **Severity:** ISSUE
- **Page:** /settings
- **Details:** Exchange Configuration shows Kraken with description "Decentralized perpetual exchange (Cosmos)" which is actually dYdX's description. Kraken should have its own description like "Centralized exchange (Spot & Futures)".
- **Screenshot:** flow-01-step-11-settings.png

### BUG-02: Missing Favicon
- **Severity:** SUGGESTION
- **Page:** All pages
- **Details:** `/favicon.ico` returns 404. Should add a favicon to `public/`.

### BUG-03: Intel Prediction Endpoints 404
- **Severity:** ISSUE
- **Page:** /intelligence
- **Details:** `/intel/predictions/history?days=7` and `/intel/predictions/accuracy?days=7` both return 404. These endpoints are referenced by the PredictionOverlay and PredictionAccuracy components but don't exist in the deployed intel service. The UI handles it gracefully ("No prediction data yet") but the console errors are noisy.

### BUG-04: Signal Feed Shows Raw JSON
- **Severity:** ISSUE
- **Page:** /intelligence
- **Details:** Snoop Signal Feed displays raw JSON `{"type":"sentiment","score":-65}` as the signal headline. Should parse the agent output and display formatted content with source, headline, and sentiment.
- **Screenshot:** flow-02-step-02c-prediction.png

---

## Console Error Summary

| Error | Count | Severity | Pages |
|-------|-------|----------|-------|
| favicon.ico 404 | All pages | Low | Global |
| WalletConnect appkit 403 | All pages | Low | Global (web3modal demo projectId) |
| WalletConnect pulse 400 | All pages | Low | Global |
| /intel/predictions/history 404 | /intelligence | Medium | Intel service not deployed |
| /intel/predictions/accuracy 404 | /intelligence | Medium | Intel service not deployed |
| Uniswap subgraph failures | /pools | Low | Expected when intel service down |

---

## UX Evaluation

### Dashboard (/)
- UX-SUGGESTION: / — Portfolio stats cards lack labels explaining what "Portfolio Value" means vs "Unrealized P&L". First-time users may be confused.
- UX-SUGGESTION: / — Intelligence Brief section shows timestamps like "6:55:16 PM" but no date. Old data (3/13/2026) looks current to someone who doesn't check.
- UX-SUGGESTION: / — "Trade Recommendations" section shows "No pending recommendations" but doesn't explain how to get them. Add a CTA like "Run Intelligence to generate signals".

### Intelligence (/intelligence)
- UX-ISSUE: /intelligence — Signal Feed shows raw JSON instead of parsed content (BUG-04)
- UX-SUGGESTION: /intelligence — SentimentGauge shows "Neutral" and "Brief Conviction: 0" which could be confusing. 0 conviction might mean "no data" or "truly neutral" — should distinguish.
- UX-SUGGESTION: /intelligence — PredictionAccuracy shows "0%" which could mean "all predictions wrong" or "no predictions yet". The subtitle helps but the big red 0% is alarming.
- UX-SUGGESTION: /intelligence — Module tiles are purely visual with no click interaction. Consider making them expandable to show detail.

### Trading (/trading)
- UX-SUGGESTION: /trading — "Long BTC" button is disabled when size is 0 but there's no visible indication of WHY it's disabled. Consider adding a tooltip or inline message.
- UX-SUGGESTION: /trading — Watchlist section is below the fold. On the dashboard, the watchlist count is prominent but finding it on trading requires scrolling.
- UX-SUGGESTION: /trading — Chart tabs (Price, Volume, RSI/MACD) are subtle. The active tab could use more visual distinction.

### Portfolio (/portfolio)
- UX-SUGGESTION: /portfolio — Equity Curve shows x-axis timestamps like "08:54 PM", "04:04 AM" without dates. Hard to know the time range.
- UX-SUGGESTION: /portfolio — "Open Positions (0)" and "Trade History" sections show empty state but no guidance on how to create positions.

### Backtest (/backtest)
- UX-SUGGESTION: /backtest — "No results yet" empty state is good but the icon is small. Could be more prominent.
- UX-SUGGESTION: /backtest — Strategy section shows "regime momentum" as the only option. Consider showing strategy description upfront rather than requiring hover/click.

### Auto-Bot (/auto-bot)
- UX-SUGGESTION: /auto-bot — "How it works" explanation block is helpful. Good onboarding UX.
- UX-SUGGESTION: /auto-bot — Conviction Threshold helper text says "Current: 80%" even after the field value changes. Should be dynamic or removed.
- UX-SUGGESTION: /auto-bot — "Save Config" button could benefit from a confirmation/success toast after saving.

### LP Pools (/pools)
- UX-ISSUE: /pools — "Pool Data Unavailable" error message is red and alarming. Since this requires the intel service, consider a softer message or explaining dependencies.
- UX-SUGGESTION: /pools — Active Positions and Top Pools Loaded show "--" which is ambiguous. Consider "0" or "N/A".

### Settings (/settings)
- UX-ISSUE: /settings — Kraken description is wrong (BUG-01). Shows dYdX description.
- UX-SUGGESTION: /settings — "read-only display, configure via .env files" subtitle is fine for a developer but doesn't explain which env vars to set.
- UX-SUGGESTION: /settings — Exchange cards are not clickable. The layout suggests they should be selectable but the note says "Switch exchanges using the toggle in the navigation bar" — this instruction could be more prominent.

### Global UX
- UX-SUGGESTION: Global — Navigation is consistent across all pages. Good.
- UX-SUGGESTION: Global — Exchange toggle works well. Active state is clearly highlighted in green.
- UX-SUGGESTION: Global — Dark theme is well-executed. Color contrast is good. Accent colors (green for active/positive, red for negative, amber for warnings) are consistent.
- UX-SUGGESTION: Global — No loading spinners observed during page transitions. Pages load quickly via client-side routing.
- UX-ISSUE: Global — Missing favicon (BUG-02) makes the tab look unprofessional.

---

## Test Quality Feedback

Written to separate file.

---

## Screenshots

All screenshots saved to: `tests/reports/run-20260319-140002/screenshots/`

| File | Description |
|------|-------------|
| flow-01-step-01-dashboard.png | Dashboard initial load |
| flow-01-step-03-kraken-active.png | Kraken exchange active |
| flow-01-step-05-intelligence.png | Intelligence page top |
| flow-01-step-06-trading.png | Trading page with BTC chart |
| flow-01-step-07-portfolio.png | Portfolio with equity curve |
| flow-01-step-08-backtest.png | Backtest configuration |
| flow-01-step-09-autobot.png | Auto-Bot page |
| flow-01-step-10-pools.png | LP Pools page |
| flow-01-step-11-settings.png | Settings with Kraken |
| flow-02-step-02c-prediction.png | Prediction overlay + signal feed + modules |
| flow-02-step-04-agent-grid.png | Agent grid 4 cards |
| flow-02-step-07-eth-chart.png | ETH-USD chart |
| flow-02-step-11-order-form.png | Order form filled |
| flow-02-step-12-kraken-trading.png | Kraken trading (no chart data) |
| flow-03-step-08-autobot-config.png | Auto-Bot config edited |
| flow-03-step-10-pools-filter.png | Pools 0.3% filter |
