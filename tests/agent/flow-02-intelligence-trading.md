# Flow 02: Intelligence, Trading & Recommendations (Full CRUD)

## Purpose
Test intelligence execution, trading order submission, recommendation approval/rejection, watchlist CRUD, chart interactions, and exchange data isolation. All mutations verified via DB oracle.

---

## Step 1: Intelligence Page — Verify New Visualizations Render

### Action
Navigate to https://wolf-pack-eight.vercel.app/intelligence

### Verify UI
Snapshot. Confirm:
- "Market Intelligence" section with SentimentGauge (semicircle SVG) and PredictionAccuracy (radial chart)
- SentimentGauge shows SELL/BUY labels and needle
- PredictionAccuracy shows percentage and "7-Day Accuracy" label
- "Prediction vs Reality" section below agent grid
- "Snoop Signal Feed" section with formatted signals (NOT raw JSON)
- Agent grid: 4 cards with wolf head icons
- Quantitative Modules: 10 tiles

### Screenshot
`flow-02-step-01-intelligence.png`

---

## Step 2: Intelligence Page — Run Intelligence Cycle

### Action
Click the "Run Intelligence" button (top right, green button).

### Verify UI
- Button changes to "Running..." and becomes disabled
- Wait for completion: poll agent grid status every 5 seconds, timeout 120s
- After completion: at least 2 agents should show "completed" status with recent timestamps

### Verify DB
```sql
SELECT agent_name, confidence, created_at
FROM wp_agent_outputs
WHERE created_at > now() - interval '5 minutes'
ORDER BY created_at DESC;
```
Assert: at least 1 row returned (Brief or Quant).

### Screenshot
`flow-02-step-02-intel-running.png` (during run)
`flow-02-step-02b-intel-complete.png` (after completion)

---

## Step 3: Intelligence Page — Verify Agent Outputs Populated

### Verify UI
Snapshot the "Latest Analysis" section. Confirm:
- At least 1 agent has a summary paragraph displayed
- Confidence bar shows a non-zero value
- Signal badges appear (trend, risk, recommendation, etc.)

### Verify DB
```sql
SELECT agent_name, summary, confidence
FROM wp_agent_outputs
ORDER BY created_at DESC LIMIT 4;
```
Compare UI summaries to DB summaries for each agent.

ORACLE_TAG: agent_outputs_check

### Screenshot
`flow-02-step-03-latest-analysis.png`

---

## Step 4: Intelligence Page — Signal Feed Shows Formatted Content

### Verify UI
Scroll to "Snoop Signal Feed" section. Confirm:
- Entries show source label, timestamp, and readable headline text
- NO raw JSON objects like `{"type":"sentiment","score":-65}` visible
- Sentiment badges (Bullish/Neutral/Bearish) render with correct colors
- If signal has type=sentiment and score, headline should read like "Bearish sentiment signal (score: -65)"

### Screenshot
`flow-02-step-04-signal-feed.png`

---

## Step 5: Trading Page — Chart Loads with Data

### Action
Navigate to /trading

### Verify UI
- Candlestick chart renders with price data for BTC (default)
- Current price displayed with 24h change %
- Interval buttons visible (1h default active)

### Screenshot
`flow-02-step-05-trading-chart.png`

---

## Step 6: Trading Page — Switch Symbol to ETH

### Action
Click "ETH" in symbol selector buttons.

### Verify UI
- Chart reloads with ETH data
- Price display updates to ETH price range (~$2,000-$4,000)

### Screenshot
`flow-02-step-06-eth-chart.png`

---

## Step 7: Trading Page — Switch Interval to 4h then 1d

### Action
Click "4h" interval button, screenshot, then click "1d".

### Verify UI
- 4h: fewer, wider candles than 1h
- 1d: even fewer candles (~7 for 1 week)
- Chart x-axis labels change appropriately

### Screenshot
`flow-02-step-07-interval-4h.png`
`flow-02-step-07b-interval-1d.png`

---

## Step 8: Trading Page — Watchlist Add Symbol

### Action
Find watchlist section. Click "+" or search input. Type "DOGE". Click DOGE in results.

### Verify UI
DOGE appears in watchlist with price info.

### Verify DB
```sql
SELECT id, symbol, exchange_id, added_at FROM wp_watchlist
WHERE symbol = 'DOGE' ORDER BY added_at DESC LIMIT 1;
```
Assert: row exists with symbol='DOGE', exchange_id='hyperliquid'.

ORACLE_TAG: watchlist_doge

### Screenshot
`flow-02-step-08-watchlist-add.png`

---

## Step 9: Trading Page — Watchlist Remove Symbol

### Action
Click the remove/X button next to DOGE in the watchlist.

### Verify UI
DOGE disappears from watchlist.

### Verify DB
```sql
SELECT id FROM wp_watchlist WHERE symbol = 'DOGE' AND exchange_id = 'hyperliquid';
```
Assert: 0 rows.

### Screenshot
`flow-02-step-09-watchlist-remove.png`

---

## Step 10: Trading Page — Submit Paper Order (CRITICAL)

### Action
Switch back to BTC symbol if needed. Then:
1. Click "Long" direction toggle
2. Enter "100" in Size (USD) field
3. Set leverage to 5x (slider or input)
4. Optionally set Stop Loss and Take Profit if fields are visible
5. Click the "Long BTC" submit button

### Verify UI
- Success message or toast appears (e.g., "Paper long BTC $100 @ $XX,XXX")
- Button returns to enabled state
- Order result message shows executed price and leveraged size

### Verify DB
```sql
SELECT symbol, direction, size_usd, entry_price, created_at
FROM wp_portfolio_snapshots
ORDER BY created_at DESC LIMIT 1;
```
Check that equity/positions updated.

Also check portfolio endpoint reflects new position.

### Screenshot
`flow-02-step-10-order-submitted.png`

---

## Step 11: Trading Page — Approve Recommendation (if pending)

### Action
Scroll to "Trade Recommendations" section on Trading page. If pending recommendations exist:
1. Note the first recommendation's symbol, direction, conviction
2. Click "Approve" button on it

### Verify UI
- Recommendation disappears from pending list or shows "approved" status
- Success confirmation appears

### Verify DB
```sql
SELECT id, symbol, direction, conviction, status
FROM wp_trade_recommendations
WHERE status = 'approved'
ORDER BY created_at DESC LIMIT 1;
```
Assert: status='approved' for the recommendation we approved.

IF NO PENDING RECOMMENDATIONS: Log "No pending recommendations to approve — SKIPPED" and continue.

### Screenshot
`flow-02-step-11-rec-approved.png`

---

## Step 12: Trading Page — Reject Recommendation (if pending)

### Action
If another pending recommendation exists:
1. Click "Reject" button on it

### Verify UI
- Recommendation disappears or shows "rejected"

### Verify DB
```sql
SELECT id, status FROM wp_trade_recommendations
WHERE status = 'rejected'
ORDER BY created_at DESC LIMIT 1;
```

IF NO PENDING RECOMMENDATIONS: Log "SKIPPED" and continue.

### Screenshot
`flow-02-step-12-rec-rejected.png`

---

## Step 13: Exchange Toggle — Switch to Kraken

### Action
Click "Kraken" in the exchange toggle.

### Verify UI
- "Kraken" button highlighted
- Trading chart area updates (may show "No chart data" — expected since Kraken CLI not on VPS)
- Console: log any errors but don't fail (Kraken CLI subprocess errors expected)

### Screenshot
`flow-02-step-13-kraken-trading.png`

---

## Step 14: Exchange Data Isolation Check

### Action
While on Kraken exchange, check the watchlist section.

### Verify UI
- Watchlist should be empty or show different symbols than Hyperliquid watchlist
- If we added DOGE to Hyperliquid watchlist (step 8) and removed it (step 9), both exchanges should show empty

### Switch back to Hyperliquid
Click "Hyperliquid" in exchange toggle. Verify chart reloads with data.

### Screenshot
`flow-02-step-14-exchange-isolation.png`

---

## Summary
- **Total steps**: 14
- **CRUD operations**: Watchlist add/remove, paper order submission, recommendation approve/reject, intelligence run
- **DB oracle checks**: 7 (agent outputs, watchlist add/remove, portfolio, rec approve/reject)
- **Key new coverage**: Order submission (was untested), rec approval/rejection (was untested), intelligence run (was untested), signal feed formatting (BUG-04 fix)
