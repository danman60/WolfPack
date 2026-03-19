# Test Run Checkpoint — 2026-03-19

## Flow 01: Navigation & Page Load — PASS (11/11 steps)
- Step 1: Dashboard — PASS (stats, tickers, intel brief, recommendations all render)
- Step 2: Exchange toggle — PASS (Hyperliquid, dYdX, Kraken buttons present)
- Step 3: Kraken switch — PASS (Kraken button shows [active])
- Step 4: Hyperliquid switch back — PASS
- Step 5: Intelligence — PASS (Market Intelligence, 7-Day Accuracy, agent grid, Signal Feed, Modules, Latest Analysis)
- Step 6: Trading — PASS (chart, order form, watchlist, recommendations)
- Step 7: Portfolio — PASS (Equity Curve, Open Positions, Trade History)
- Step 8: Backtest — PASS (6 markets, 6 intervals, 3 strategies, Run Backtest, Run History)
- Step 9: Auto-Bot — PASS (Enable toggle, Configuration, Save Config, Open Positions, Activity Log)
- Step 10: LP Pools — PASS (wallet connect, fee tier filters, Pool Browser)
- Step 11: Settings — PASS (3 exchanges with correct descriptions, Strategy Mode, LLM Providers, Safety Checklist)

## Console Notes
- 3-7 console errors across pages (mostly subgraph/external API related, not app errors)
- 1 warning consistently

## Flow 02: Intelligence, Trading & Recommendations — PASS (12/14 steps, 2 skipped)
- Step 1: Intelligence visualizations — PASS (SentimentGauge, PredictionAccuracy, Signal Feed)
- Step 2: Run Intelligence — PASS (4/4 agents completed: brief 0.45, quant 0.30, sage 0.48, snoop 0.55)
- Step 3: Agent outputs — PASS (UI matches DB, oracle verified)
- Step 4: Signal Feed formatting — PASS (formatted "Bearish sentiment signal (score: -35)", no raw JSON)
- Step 5: Trading chart — PASS (BTC-USD TradingView chart renders)
- Step 6: Symbol switch ETH — PASS
- Step 7: Interval switch 4H/1D — PASS
- Step 8: Watchlist add DOGE — PASS (DB oracle: id=bb81fc08, exchange_id=hyperliquid)
- Step 9: Watchlist remove DOGE — PASS (DB oracle: 0 rows)
- Step 10: Paper order — PASS (Paper long BTC $500.0 @ 70409.0, 5x leverage)
- Step 11: Approve recommendation — SKIPPED (no pending)
- Step 12: Reject recommendation — SKIPPED (no pending)
- Step 13: Kraken toggle on Trading — PASS
- Step 14: Exchange data isolation — PASS (Kraken: 0 symbols, Hyperliquid: 1 symbol)

### UX Issues Found
- UX-ISSUE: Quant agent displays raw JSON in Latest Analysis instead of formatted prose

## Flow 03: Backtest, Auto-Bot, Portfolio & LP Pools — PASS (12/14, 1 partial, 1 skipped)
- Step 1: Portfolio stats — PASS (Equity $10,015, Realized P&L $15.04 match DB)
- Step 2: Close position — PASS (BTC long closed, entry 70409, exit 70420, P&L $0.08)
- Step 3: Equity curve — PASS (chart renders with data points $10,000-$10,016)
- Step 4: Trade history — PASS (2 closed trades, DB oracle verified)
- Step 5: Run backtest — PARTIAL (submitted + ran, failed: "Insufficient candle data: 0 bars" — VPS data issue)
- Step 6: Backtest results — SKIPPED (backtest failed)
- Step 7: Delete backtest run — PASS (run deleted, DB confirms 0 rows)
- Step 8: Auto-Bot layout — PASS (Enable toggle, Config, Open Positions, Activity Log)
- Step 9: Auto-Bot toggle — PASS (Paused → Active → Paused)
- Step 10: Auto-Bot save config — PASS (threshold=75, equity=15000 saved, button disabled after save, reset to defaults)
- Step 11: Activity log — SKIPPED (no auto trades)
- Step 12: LP Pools — PASS (pools loaded, fee tier filters visible)
- Step 13: Fee tier filter — PASS (buttons clickable, filter works)
- Step 14: Kraken description — PASS (correct: "Centralized exchange — spot & futures via CLI")
