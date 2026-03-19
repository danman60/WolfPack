# Flow 03: Backtest Execution, Auto-Bot CRUD, Portfolio Close & LP Pools

## Purpose
Full CRUD testing of backtest (configure, run, view results, delete), Auto-Bot (toggle, save config, verify trades), portfolio (close position, verify P&L), and LP Pools (filter, data verification). All mutations verified via DB oracle.

---

## Section A: Portfolio

## Step 1: Portfolio Page — Verify Stats Match DB

### Action
Navigate to https://wolf-pack-eight.vercel.app/portfolio

### Verify UI
Snapshot. Note all stat values: equity, realized P&L, unrealized P&L, win rate.

### Verify DB
```sql
SELECT equity, realized_pnl, unrealized_pnl, free_collateral
FROM wp_portfolio_snapshots
ORDER BY created_at DESC LIMIT 1;
```
Compare each value to UI display. Assert they match (within rounding).

### Screenshot
`flow-03-step-01-portfolio-stats.png`

---

## Step 2: Portfolio Page — Close Position (if open)

### Action
If "Open Positions" section shows positions:
1. Note the first position's symbol, direction, entry price, unrealized P&L
2. Click the "Close" button for that position

### Verify UI
- Position disappears from open positions list
- Equity and realized P&L update
- Success message appears

### Verify DB
```sql
SELECT symbol, direction, entry_price, exit_price, pnl_usd, closed_at
FROM wp_trade_history
ORDER BY closed_at DESC LIMIT 1;
```
Assert: closed_at is within last 60 seconds, symbol matches.

Also verify portfolio snapshot updated:
```sql
SELECT equity, realized_pnl FROM wp_portfolio_snapshots
ORDER BY created_at DESC LIMIT 1;
```

IF NO OPEN POSITIONS: Log "No positions to close — SKIPPED" and continue.

ORACLE_TAG: closed_position

### Screenshot
`flow-03-step-02-position-closed.png`

---

## Step 3: Portfolio Page — Equity Curve Renders

### Verify UI
Snapshot the equity curve chart. Confirm:
- LineChart renders with time axis and equity values
- If data exists: line shows equity progression over time
- If no data: empty state message shown

### Screenshot
`flow-03-step-03-equity-curve.png`

---

## Step 4: Portfolio Page — Trade History

### Verify UI
Scroll to trade history section. Confirm:
- If trades exist: table shows symbol, direction, entry/exit price, P&L, date
- If no trades: "No closed trades yet" message

### Verify DB
```sql
SELECT symbol, direction, entry_price, exit_price, pnl_usd
FROM wp_trade_history
ORDER BY closed_at DESC LIMIT 5;
```
Compare first row to UI first row.

### Screenshot
`flow-03-step-04-trade-history.png`

---

## Section B: Backtest

## Step 5: Backtest Page — Configure and Run

### Action
Navigate to /backtest

1. Select first available strategy from dropdown
2. Select "BTC" as symbol
3. Select "1h" as interval
4. Click "7" days preset
5. **Click "Run Backtest" / "Start" button**

### Verify UI
- Button shows "Running..." or progress indicator
- Progress bar appears showing 0% → increasing

### Wait for completion
Poll every 5 seconds. Timeout: 120 seconds. If timeout: log "TIMEOUT" and continue.

### Verify DB
```sql
SELECT id, status, config->>'strategy' as strategy, config->>'symbol' as symbol,
       trade_count, progress_pct, created_at
FROM wp_backtest_runs
ORDER BY created_at DESC LIMIT 1;
```
Assert: status='completed' (or 'running' if still in progress), symbol='BTC'.

ORACLE_TAG: backtest_run

### Screenshot
`flow-03-step-05-backtest-running.png`
`flow-03-step-05b-backtest-complete.png`

---

## Step 6: Backtest Page — View Results

### Action
After backtest completes, verify results display:

### Verify UI
- Hero metrics card appears with Total Return %, Win Rate, Sharpe Ratio, Max Drawdown
- Equity curve chart renders
- Click "Trades" tab if available — verify trade table shows entries with entry/exit/P&L

### Verify DB
```sql
SELECT id, status, trade_count, metrics->>'total_return_pct' as return_pct,
       metrics->>'win_rate' as win_rate, metrics->>'sharpe_ratio' as sharpe
FROM wp_backtest_runs
ORDER BY created_at DESC LIMIT 1;
```
Compare metrics to UI values.

IF BACKTEST FAILED OR TIMED OUT: Log "Backtest did not complete — results check SKIPPED" and continue.

### Screenshot
`flow-03-step-06-backtest-results.png`

---

## Step 7: Backtest Page — Delete Run

### Action
In the "Run History" section, find the run we just created. Click the delete button (trash icon or "Delete").

### Verify UI
- Run disappears from history list
- If it was selected, results panel clears

### Verify DB
```sql
SELECT id FROM wp_backtest_runs WHERE id = '<run_id from step 5>';
```
Assert: 0 rows (deleted).

### Screenshot
`flow-03-step-07-backtest-deleted.png`

---

## Section C: Auto-Bot

## Step 8: Auto-Bot Page — Verify Layout

### Action
Navigate to /auto-bot

### Verify UI
Snapshot. Confirm:
- Toggle switch visible (shows current enabled/disabled state)
- Stats: equity, P&L, return %, open positions
- Configuration section: equity input, conviction threshold input, "Save" button
- Activity log section
- Pending position actions section (if any)

### Screenshot
`flow-03-step-08-autobot-layout.png`

---

## Step 9: Auto-Bot Page — Toggle Enable/Disable (CRITICAL)

### Action
Note current state (enabled or disabled). Click the toggle button.

### Verify UI
- Status badge changes (Active → Paused or Paused → Active)
- Button text updates accordingly
- Wait 2 seconds for state to propagate

### Verify DB
```sql
-- The auto-trader status is managed in-memory via the intel service API
-- Verify via the API response
```
Navigate away and back to /auto-bot. Verify the toggle state persisted.

### Toggle back to original state
Click toggle again to restore original state.

### Screenshot
`flow-03-step-09-autobot-toggled.png`

---

## Step 10: Auto-Bot Page — Save Configuration (CRITICAL)

### Action
1. Click into Conviction Threshold field
2. Clear it and type "75"
3. Click into Equity field (if visible)
4. Clear it and type "15000"
5. **Click "Save" / "Save Config" / "Update Config" button**

### Verify UI
- Success feedback: "Saved!" text, checkmark, or toast appears
- Config saved flag visible for ~2 seconds
- Fields may clear after save

### Verify persistence
Navigate to /trading and back to /auto-bot. Verify the threshold shows 75 (or the new value persisted).

### Reset config after test
Set threshold back to 80 and equity back to original, save again.

### Screenshot
`flow-03-step-10-autobot-config-saved.png`

---

## Step 11: Auto-Bot Page — Activity Log Data Accuracy

### Verify UI
If trades exist in Activity Log:
- Pick first trade, note: symbol, direction, entry_price, conviction %

### Verify DB
```sql
SELECT symbol, direction, entry_price, conviction, status, opened_at
FROM wp_auto_trades
ORDER BY opened_at DESC LIMIT 3;
```
Compare first row to UI first row. Assert values match.

IF NO TRADES: Log "No auto trades — SKIPPED" and continue.

### Screenshot
`flow-03-step-11-autobot-trades.png`

---

## Section D: LP Pools

## Step 12: LP Pools Page — Load and Verify

### Action
Navigate to /pools

### Verify UI
- Fee tier filter buttons: "All", "0.01%", "0.05%", "0.3%", "1%"
- Pool table area (may show data or error — subgraph depends on external API)
- Wallet connect button visible

### Screenshot
`flow-03-step-12-pools.png`

---

## Step 13: LP Pools — Fee Tier Filter Test

### Action
If pools loaded:
1. Count total pool rows displayed
2. Click "0.3%" filter button
3. Count pool rows after filtering

### Verify UI
- "0.3%" button is highlighted
- Pool count decreased (or same if all are 0.3%)
- Click "All" — original count restored

IF POOLS FAILED TO LOAD: Log "Pool data unavailable — filter test SKIPPED" and continue.

### Screenshot
`flow-03-step-13-pools-filter.png`

---

## Section E: Settings Verification

## Step 14: Settings — Kraken Description Fixed

### Action
Navigate to /settings

### Verify UI
- Exchange Configuration section lists 3 exchanges:
  - Hyperliquid: "On-chain perpetual futures (L1)"
  - dYdX: "Decentralized perpetual exchange (Cosmos)"
  - Kraken: "Centralized exchange — spot & futures via CLI" (NOT dYdX's description)
- Active exchange has green indicator

### Screenshot
`flow-03-step-14-settings-kraken.png`

---

## Summary
- **Total steps**: 14
- **CRUD operations**: Close position, run backtest, delete backtest, toggle auto-bot, save auto-bot config
- **DB oracle checks**: 8 (portfolio stats, close position, trade history, backtest run/results/delete, auto trades)
- **Key new coverage**: Order execution (close), backtest full lifecycle, auto-bot toggle+save (all were previously untested)
