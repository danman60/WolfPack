# Current Work - WolfPack

## Active Task
Frontend Data & UX Upgrade — 4 features — COMPLETE

## Recent Changes (This Session)
- `c25adbb` — feat: 24h change, TradingView chart, trade history, auto-bot page

### What was implemented:
1. **24h % Change** — `use24hChange(symbol)` hook in useMarketData.ts, displayed on dashboard BTC/ETH tickers and trading page
2. **TradingView Chart** — lightweight-charts candlestick chart with SMA(20,50), EMA(12), Bollinger Bands, RSI(14), MACD(12,26,9), 6 timeframes (1m-1D), 3 tabs (Price/Volume/Indicators)
3. **Trade History** — `wp_trade_history` Supabase table, `_store_closed_trade()` in paper_trading.py, `GET /portfolio/trades` endpoint, `useTradeHistory` hook, trade history section on /portfolio
4. **Auto-Bot Page** — `/auto-bot` route with enable/disable toggle, bucket stats, configuration (conviction threshold + equity), open positions, pending position actions, activity log. `POST /auto-trader/config` backend endpoint. `useAutoTraderTrades` + `useConfigureAutoTrader` hooks. Nav link added.

### New files:
- `app/src/app/auto-bot/page.tsx` — dedicated auto-trader page
- `app/src/components/TradingChart.tsx` — lightweight-charts wrapper with indicators
- `app/src/lib/indicators.ts` — pure math: SMA, EMA, BB, RSI, MACD

### Modified files:
- `app/src/lib/hooks/useMarketData.ts` — use24hChange hook
- `app/src/app/page.tsx` — 24h change on PriceTicker
- `app/src/app/trading/page.tsx` — TradingChart replaces recharts, 24h change
- `app/src/app/portfolio/page.tsx` — trade history section
- `app/src/components/Nav.tsx` — Auto-Bot nav link
- `app/src/lib/hooks/useIntelligence.ts` — 3 new hooks
- `intel/wolfpack/api.py` — GET /portfolio/trades, POST /auto-trader/config
- `intel/wolfpack/paper_trading.py` — _store_closed_trade()

## Next Steps
1. Deploy to VPS: `cd /root/WolfPack && git pull`
2. Test all 4 features in browser
3. Verify chart renders with live data
4. Test auto-bot config persistence
5. Close a position and verify trade history populates

## Context for Next Session
- lightweight-charts is browser-only — must use dynamic import + useEffect (no SSR)
- Trade history stores on close_position() — both manual and auto-trader closes
- Auto-bot config is in-memory (resets on restart) — env vars are boot defaults
- `POST /auto-trader/config` only resets equity if no open positions
