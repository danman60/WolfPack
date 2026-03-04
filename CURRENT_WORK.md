# Current Work - WolfPack

## Active Task
Intelligence system enhancements — social sentiment, whale tracking, OI wiring, watchlist.

## Recent Changes (This Session)
- Wired real Open Interest from Hyperliquid `get_markets()` into funding module (was hardcoded 0)
- New module: `social_sentiment.py` — Fear & Greed Index + CoinGecko trending + community scores
- New module: `whale_tracker.py` — large trade detection from Hyperliquid recent trades
- Orchestrated both new modules in `api.py` intelligence cycle (parallel via asyncio.gather)
- Enhanced Snoop agent — consumes social sentiment + whale tracker data, new output fields
- Enhanced Sage agent — consumes OI + social + whale data, OI divergence signal
- Supabase migration: `wp_watchlist` table (symbol, exchange_id, unique constraint)
- Watchlist API: GET/POST/DELETE `/watchlist`, `/watchlist/search` for type-to-complete
- Multi-symbol intelligence: `POST /intelligence/run-all` runs for all watchlist + position symbols
- Frontend: watchlist hooks (useWatchlist, useAddToWatchlist, useRemoveFromWatchlist, useSymbolSearch, useRunAllIntelligence)
- Trading page: watchlist section with chips, search dropdown, "Run All Intel" button
- Dashboard: watchlist count stat card

## Files Changed
- `intel/wolfpack/modules/social_sentiment.py` — NEW
- `intel/wolfpack/modules/whale_tracker.py` — NEW
- `intel/wolfpack/modules/__init__.py` — added new modules to exports
- `intel/wolfpack/agents/snoop.py` — enhanced with social + whale data
- `intel/wolfpack/agents/sage.py` — enhanced with OI + social + whale data
- `intel/wolfpack/api.py` — OI wiring, new module orchestration, watchlist endpoints, run-all
- `intel/wolfpack/db.py` — watchlist CRUD helpers
- `app/src/lib/hooks/useIntelligence.ts` — watchlist hooks
- `app/src/app/trading/page.tsx` — watchlist UI
- `app/src/app/page.tsx` — watchlist count on dashboard

## Next Steps
1. Deploy to VPS: `cd /root/WolfPack && git pull && kill uvicorn && restart`
2. Test live: trigger `/intelligence/run?symbol=BTC`, verify OI + social + whale in outputs
3. Test watchlist: add SOL, verify persist, search works
4. Test run-all with BTC + ETH on watchlist
