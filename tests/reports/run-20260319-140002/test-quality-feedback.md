# Test Quality Feedback
**Run ID:** run-20260319-140002

## What Worked Well
- **Oracle triple-verification** caught real data consistency: portfolio equity matched DB within rounding
- **Watchlist CRUD cycle** was the only data mutation and cleaned up after itself — ledger tracked it correctly
- **Exchange toggle testing** across multiple pages caught the Kraken description bug in Settings
- **Snapshot-before-click protocol** consistently identified correct element refs

## Test Coverage Gaps
- **No backtest execution test** — we configured but didn't run. A backtest run would test the full intel service proxy + DB write flow
- **No paper trade execution** — order form was tested but not submitted. Would verify trade creation + portfolio update
- **No Auto-Bot enable test** — toggle was not clicked to avoid side effects. Should test enable/disable cycle
- **Intel service dependency** — Many features (predictions, pool data, Kraken chart data) require the intel service. Tests logged these as expected failures but couldn't verify the full flow

## Suggested Improvements
1. Add a test flow that runs a backtest (short, 7d BTC) and verifies results appear in DB and UI
2. Add a paper trade submission flow (small $10 position) with position verification and close
3. Test with intel service running to verify prediction charts, signal feed content, and pool data
4. Add responsive testing — current tests are at default 1280x720 viewport only
5. Test error recovery — what happens when switching exchanges mid-operation?

## Test Infrastructure Notes
- `playwright-cli` eval with `window.scrollTo` sometimes navigates to `about:blank` — needed re-navigation
- Snapshot filter script works well for finding interactive elements
- Screenshot resize keeps file sizes manageable (73-157KB per image)
