# Test Quality Feedback — Run 2026-03-19

## Test Plan Quality
- **Coverage**: Excellent — all 8 pages tested, CRUD operations for watchlist/backtest/auto-bot/portfolio
- **Oracle verification**: DB checks matched UI values in all cases tested
- **Exchange isolation**: Properly verified Kraken vs Hyperliquid watchlist separation

## What Worked Well
- Snapshot-filter.sh efficiently surfaced interactive elements for fast verification
- Screenshot-resize.sh kept image sizes manageable
- Test flows were ordered logically (read-only navigation first, then mutations)
- Cleanup flow was unnecessary — watchlist add/remove cycle self-cleaned

## What Could Be Improved
1. **Backtest flow assumes intel VPS has candle data** — should have a fallback assertion for "failed but submitted correctly"
2. **Recommendation approve/reject** depends on pending recs existing — consider seeding a test recommendation via DB insert
3. **Auto-Bot activity log** always empty — need a way to trigger auto-trades for testing (run intel with bot enabled)
4. **Signal Feed verification** could be more specific — assert exact formatting patterns rather than just "no raw JSON"
5. **Order form test** could verify the order appears in portfolio positions list immediately after submission
6. **Console errors** (3-7 per page) were noted but not classified — should categorize as expected (external API) vs unexpected

## Missing Test Coverage
- Mobile responsive layout testing
- Error state handling (what happens when intel VPS is completely down?)
- Concurrent exchange switching while data is loading
- Backtest with different strategies and symbols
- LP Pools wallet connection flow (requires actual wallet)
