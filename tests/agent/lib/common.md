# Common Test Configuration - WolfPack

## Browser Session
Use `playwright-cli -s=wolftest` for ALL browser commands.

## App Info
- **Type**: Next.js 15 webapp on Vercel
- **URL**: https://wolf-pack-eight.vercel.app/
- **Auth**: None — single-user personal app, no login required
- **Data backend**: Python FastAPI intel service proxied via `/intel/*`
- **DB**: Supabase (public schema, `wp_` prefixed tables)

## Navigation
Top nav bar with links:
- Dashboard (`/`)
- Intelligence (`/intelligence`)
- Trading (`/trading`)
- Portfolio (`/portfolio`)
- Backtest (`/backtest`)
- Auto-Bot (`/auto-bot`)
- LP Pools (`/pools`)
- Settings (`/settings`)

Exchange toggle in nav: buttons for "Hyperliquid", "dYdX", "Kraken"

## Snapshot Protocol
Before every click/fill:
```
playwright-cli -s=wolftest snapshot --filename=tests/agent/tmp/raw.yml
cat tests/agent/tmp/raw.yml | tests/agent/lib/snapshot-filter.sh
```

After every navigation:
```
playwright-cli -s=wolftest console warning
playwright-cli -s=wolftest network
```

After every important state change:
```
playwright-cli -s=wolftest screenshot --filename=REPORT_DIR/screenshots/flow-NN-step-NN.png
tests/agent/lib/screenshot-resize.sh REPORT_DIR/screenshots/flow-NN-step-NN.png
```

## Data Dependencies
- Market data comes from exchange APIs via the intel service
- Agent outputs stored in `wp_agent_outputs` table
- Module outputs in `wp_module_outputs`
- Recommendations in `wp_trade_recommendations`
- Portfolio in `wp_portfolio_snapshots`
- No user-created content — this is a read-heavy dashboard with some paper trading actions

## Key Interactions
- Exchange toggle: click exchange name button in nav to switch
- Run Intelligence: button on Intelligence page
- Approve/Reject recommendations: buttons on Trading page
- Paper trade: form on Trading page (symbol, direction, size)
- Close position: button on Portfolio page
- Backtest: config form + run on Backtest page
- Auto-Bot: toggle + config on Auto-Bot page
- Watchlist: add/remove symbols on Trading page
