# Test Plan - WolfPack

## App Description
Personal crypto trading and intelligence platform. Multi-agent AI analysis (Quant, Snoop, Sage, Brief) + paper trading + backtesting + Uniswap V3 LP pool management. Supports Hyperliquid, dYdX, and Kraken exchanges.

## App Type
webapp

## Deployed URL
https://wolf-pack-eight.vercel.app/

## Supabase Project
supabase-CCandSS (wp_ prefixed tables in public schema)

## DB Schema
public

## Auth Pattern
None — single-user personal app, no login/auth required.

## Pre-flight Checklist
1. Verify deployed URL loads (GET returns 200)
2. Verify Supabase MCP: `execute_sql("SELECT 1 as mcp_check")` on supabase-CCandSS
3. Verify `/intel/health` proxy works (GET returns {"status":"ok"})

## Pages (8 total)
| Page | Path | Key Features |
|------|------|-------------|
| Dashboard | `/` | Portfolio stats, live prices, agent status, recommendations, positions |
| Intelligence | `/intelligence` | Sentiment gauge, prediction accuracy, agent grid, signal feed, modules |
| Trading | `/trading` | Chart, order form, watchlist, recommendations, symbol search |
| Portfolio | `/portfolio` | Equity curve, positions, trade history, close positions |
| Backtest | `/backtest` | Strategy config, run backtest, results with equity curve |
| Auto-Bot | `/auto-bot` | Toggle, config (equity, threshold), trades list, position actions |
| LP Pools | `/pools` | Uniswap V3 pools, screening scores, wallet connect, LP management |
| Settings | `/settings` | Exchange config (read-only), strategy mode, LLM providers, safety checklist |

## Test Flows (execution order)
1. `flow-01-navigation.md` — 11 steps: Load all 8 pages, verify rendering, exchange toggle, Kraken
2. `flow-02-intelligence-trading.md` — 14 steps: Run intelligence, order submission, rec approve/reject, watchlist CRUD, exchange isolation
3. `flow-03-backtest-autobot.md` — 14 steps: Portfolio close position, backtest full lifecycle (run+results+delete), auto-bot toggle+save, LP pools filter
4. `flow-99-cleanup.md` — Ledger-based cleanup

## DB Tables (read-only verification — no test data creation needed for most)
- `wp_agent_outputs` — Latest agent analysis per agent
- `wp_module_outputs` — Latest module outputs
- `wp_trade_recommendations` — Pending/executed recommendations
- `wp_portfolio_snapshots` — Portfolio equity over time
- `wp_trade_history` — Closed trades
- `wp_auto_trades` — Auto-trader executions
- `wp_prediction_performance` — Prediction accuracy tracking (NEW)
- `wp_watchlist` — Watched symbols
- `wp_backtest_runs` — Backtest configurations and results
- `wp_backtest_trades` — Individual backtest trades

## Key Verification Points
1. **Exchange toggle**: Kraken appears as 3rd option, clicking it changes active exchange display
2. **Intelligence page**: SentimentGauge, PredictionAccuracy, PredictionOverlay, SignalFeed render
3. **Trading page**: Chart loads with candle data, order form fields work, watchlist add/remove
4. **Portfolio page**: Equity curve chart renders, positions list shows
5. **Backtest page**: Strategy list loads, can configure and start a run
6. **Settings page**: Shows 3 exchanges (including Kraken), strategy mode displays

## Cleanup SQL
```sql
-- Only needed if watchlist items were added during testing
DELETE FROM wp_watchlist WHERE symbol LIKE 'TEST%';
-- Only needed if backtest was run during testing
-- (identified by specific run_id tracked in ledger)
```
