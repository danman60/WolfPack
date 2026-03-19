# Flow 01: Navigation & Page Load Verification

## Purpose
Verify all 8 pages load without errors, navigation works, and the new Kraken exchange toggle appears.

---

## Step 1: Load Dashboard (/)

### Action
Navigate to https://wolf-pack-eight.vercel.app/

### Verify UI
Snapshot. Confirm:
- Page title contains "WolfPack" in the nav bar
- "Dashboard" link is active/highlighted in nav
- Portfolio stats cards visible: "Portfolio Value", "Unrealized P&L", "Open Positions", "Watchlist"
- Live price tickers visible: "BTC-USD", "ETH-USD"
- "Intelligence Brief" section with agent rows (The Quant, The Snoop, The Sage, The Brief)
- "Trade Recommendations" section visible
- Console: no errors
- Network: no 4xx/5xx (note: intel service calls may 502 if VPS is down — log but don't fail)

### Screenshot
`flow-01-step-01-dashboard.png`

---

## Step 2: Verify Exchange Toggle — Kraken Present

### Action
Locate the exchange toggle in the navigation bar (top right area). It should be a segmented button group.

### Verify UI
Snapshot the exchange toggle. Confirm:
- Three buttons visible: "Hyperliquid", "dYdX", "Kraken"
- One button is highlighted/active (default: Hyperliquid)
- Toggle is visually rendered as a segmented control with rounded corners

### Screenshot
`flow-01-step-02-exchange-toggle.png`

---

## Step 3: Switch to Kraken Exchange

### Action
Click the "Kraken" button in the exchange toggle.

### Verify UI
Snapshot. Confirm:
- "Kraken" button is now highlighted/active
- "Hyperliquid" and "dYdX" buttons are no longer active
- Dashboard still renders (may show different data or loading states)

### Screenshot
`flow-01-step-03-kraken-active.png`

---

## Step 4: Switch Back to Hyperliquid

### Action
Click the "Hyperliquid" button in the exchange toggle.

### Verify UI
Confirm "Hyperliquid" is active again.

---

## Step 5: Navigate to Intelligence (/intelligence)

### Action
Click "Intelligence" in the top navigation bar.

### Verify UI
Snapshot. Confirm:
- Page heading: "Intelligence Brief"
- Subtitle mentions the active exchange name
- "Run Intelligence" button visible (top right)
- **NEW — Market Intelligence section**: contains SentimentGauge (semicircle SVG) and PredictionAccuracy (radial chart)
- Agent grid: 4 cards (The Quant, The Snoop, The Sage, The Brief) with status badges
- **NEW — Prediction vs Reality section**: chart area (may show "No prediction data yet" if empty)
- **NEW — Snoop Signal Feed section**: scrollable list (may show "No signals yet" if empty)
- Quantitative Modules grid: 10 module tiles
- "Latest Analysis" section
- Console: no errors
- Network: check for failed requests

### Screenshot
`flow-01-step-05-intelligence.png`

---

## Step 6: Navigate to Trading (/trading)

### Action
Click "Trading" in the top navigation bar.

### Verify UI
Snapshot. Confirm:
- Trading chart area visible (candlestick chart with TradingChart component)
- Symbol selector visible with options (BTC, ETH, SOL, etc.)
- Order form visible with fields: direction toggle (Long/Short), size input, leverage slider
- Watchlist section visible
- Recommendations section visible
- Console: no errors

### Screenshot
`flow-01-step-06-trading.png`

---

## Step 7: Navigate to Portfolio (/portfolio)

### Action
Click "Portfolio" in the top navigation bar.

### Verify UI
Snapshot. Confirm:
- Page heading: "Portfolio" or similar
- Portfolio stats visible (equity, P&L, win rate)
- Equity curve chart area (may be empty if no history)
- Positions section
- Trade history section
- Console: no errors

### Screenshot
`flow-01-step-07-portfolio.png`

---

## Step 8: Navigate to Backtest (/backtest)

### Action
Click "Backtest" in the top navigation bar.

### Verify UI
Snapshot. Confirm:
- Configuration form visible: strategy select, symbol select, interval, date range
- "Run Backtest" or "Start" button visible
- Previous runs list (may be empty)
- Console: no errors

### Screenshot
`flow-01-step-08-backtest.png`

---

## Step 9: Navigate to Auto-Bot (/auto-bot)

### Action
Click "Auto-Bot" in the top navigation bar.

### Verify UI
Snapshot. Confirm:
- Auto-Bot header with enable/disable toggle
- Stats: equity, P&L, return %, open positions
- Configuration section: equity input, conviction threshold input, "Save" button
- Trades list section
- Console: no errors

### Screenshot
`flow-01-step-09-autobot.png`

---

## Step 10: Navigate to LP Pools (/pools)

### Action
Click "LP Pools" in the top navigation bar.

### Verify UI
Snapshot. Confirm:
- Pool list/table visible (may show loading or "Connect Wallet" prompt)
- Fee tier filter buttons: "All", "0.01%", "0.05%", "0.3%", "1%"
- Pool screening scores if data loaded
- Console: no errors (subgraph API failures are expected — log but don't fail)

### Screenshot
`flow-01-step-10-pools.png`

---

## Step 11: Navigate to Settings (/settings)

### Action
Click "Settings" in the top navigation bar.

### Verify UI
Snapshot. Confirm:
- Page heading: "Settings"
- Subtitle: "Platform configuration"
- "Exchange Configuration" section showing exchanges:
  - Hyperliquid with description "On-chain perpetual futures (L1)"
  - dYdX with description
  - **Verify Kraken appears in the exchange list** (may show with description or just name)
- "Strategy Mode" section showing Paper Trading / Live Trading options
- "Safety Checklist" with items (private key, circuit breaker, etc.)
- LLM Providers section: Anthropic, DeepSeek, OpenRouter
- Console: no errors

### Screenshot
`flow-01-step-11-settings.png`

---

## Summary
- **Total steps**: 11
- **Pages covered**: 8/8
- **Key verification**: Kraken in exchange toggle (Step 2-3), new Intelligence visualizations (Step 5), Settings exchange list (Step 11)
- **No data mutation** — this flow is read-only navigation
