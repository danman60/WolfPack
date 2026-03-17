# Current Work - WolfPack

## Active Task
None — last task completed.

## Recent Changes (2026-03-13)
- Built full Playwright CLI business logic test suite (tests/20-27)
- Updated helpers.js with new utilities: isBackendUp, skipTest, clickButton, waitForAPI, fillByLabel, getButtonTexts, assertOkResponse
- Updated run-all.sh to support SUITE=smoke|workflow|all
- Installed intel backend Python venv at intel/.venv/
- All 20 tests passing on production (https://wolf-pack-eight.vercel.app/)

### Workflow Tests Created
| File | Test | Notes |
|------|------|-------|
| 20-paper-trade.js | Order form fill + submit | Tolerates Supabase 500 in dev |
| 21-intelligence-cycle.js | Run Intelligence, verify agent outputs | |
| 22-approve-reject.js | Approve/reject recommendations | Needs prior intel run for data |
| 23-close-position.js | Close position on Portfolio page | Tolerates Supabase 500 in dev |
| 24-autobot-toggle.js | Toggle Auto-Bot, save config, revert | |
| 25-exchange-switch.js | Switch HL↔dYdX, verify data refresh | UI-only, no backend needed |
| 26-backtest.js | Configure + run backtest | Button text is "Run Backtest" |
| 27-watchlist.js | Add/remove symbols from watchlist | |

## Blockers / Open Questions
- Exchange context doesn't persist across page navigation (resets to Hyperliquid)
- No recommendations generated in test runs — approve/reject test can't fully exercise buttons
- intel/.env not configured locally (no Supabase creds) — some endpoints return 500 in dev

## Next Steps
- Generate intelligence data so approve/reject test can be fully validated
- Fix exchange persistence across navigation (if it's a bug)
- Consider adding test for full trade lifecycle: place order → run intel → approve rec → close position

## Context for Next Session
- Dev server: port 3001 (port 3000 used by Remotion)
- Intel backend: `cd intel && source .venv/bin/activate && uvicorn wolfpack.api:app --port 8000`
- Production: https://wolf-pack-eight.vercel.app/
- Test runner: `bash tests/run-all.sh <url>` or `SUITE=workflow bash tests/run-all.sh <url>`
- All 20 tests green on production as of 2026-03-13
