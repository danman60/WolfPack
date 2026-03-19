# Current Work - WolfPack

## Last Session Summary
Implemented Kraken exchange adapter (Python CLI + TypeScript proxy), AI dashboard visualizations (SentimentGauge, PredictionAccuracy, PredictionOverlay, SignalFeed), EMA/VWAP extension filter for the Quant agent, and prediction scoring module. Fixed multiple bugs found during 3 rounds of automated testing. Configured API auth between Vercel and Droplet intel service.

## What Changed
- [048d0dd] Kraken adapter + AI dashboard visualizations (15 files, 1313 insertions)
- [0091970] Fix Kraken description in Settings + Signal Feed raw JSON formatting
- [9a612ff] EMA/VWAP extension filter + veto conviction penalty + test suite updates
- [infra] Set API_SECRET_KEY on Droplet, NEXT_PUBLIC_INTEL_API_KEY on Vercel, redeployed

## Build Status
PASSING — Next.js 16.1.6 Turbopack, 3.9s, 10 static pages

## Known Bugs & Issues
- UX-ISSUE: Quant agent displays raw JSON in Latest Analysis section instead of prose (other agents display formatted summaries)
- UX-SUGGESTION: PredictionAccuracy shows "0%" — needs message "Predictions tracked after trades execute"
- UX-SUGGESTION: Portfolio win rate shows "--" instead of calculating from closed trades
- UX-SUGGESTION: Backtest failure doesn't surface error message to user ("No results yet" instead of reason)
- Backtest on VPS returns "Insufficient candle data: 0 bars" — candle cache/fetch issue on Droplet

## Tests
- 3 test runs this session: v1 (35/35 smoke), v2 (22/39, blocked by 403), v3 (34/39, 12/12 oracle match)
- Latest: tests/reports/run-20260319-213924/report.md — 87% pass rate (97% excluding skips)
- 4 skipped: approve/reject rec (no pending), backtest results (failed run), activity log (no trades)
- All DB oracle checks PASS (portfolio, watchlist CRUD, close position, backtest delete, agent outputs)

## Next Steps
1. Fix Quant agent raw JSON display (format regime_assessment into prose summary)
2. Run DB migration for wp_prediction_performance table via Supabase MCP
3. Fix backtest candle fetch on Droplet (returns 0 bars — cache or exchange adapter issue)
4. Add win rate calculation to Portfolio page (currently shows "--")
5. Test Kraken CLI end-to-end on a machine with the binary installed
6. Run prediction scorer after 24h of recommendations accumulate

## Gotchas for Next Session
- API auth: Droplet API_SECRET_KEY and Vercel NEXT_PUBLIC_INTEL_API_KEY are now set and working
- Kraken CLI binary at ~/.cargo/bin/kraken — NOT installed on Droplet (1GB RAM VPS, only 24GB disk 98% full)
- EMA/VWAP extension filter: penalties -8 (3-5% EMA), -15 (>5% EMA), -5 (5-10% VWAP), -15 (>10% VWAP)
- Veto layer accepts optional quant_signals param — wired in api.py _run_full_cycle
- Test flows in tests/agent/flow-*.md — agent-powered tests via playwright-cli
- Vercel project name is "wolf-pack" (not "app") — linked via `vercel link --project wolf-pack`

## Files Touched This Session
### Created
- intel/wolfpack/exchanges/kraken.py (Python Kraken CLI adapter)
- app/src/lib/exchange/kraken.ts (TypeScript proxy adapter)
- intel/wolfpack/modules/prediction_scorer.py (scoring module)
- app/src/lib/hooks/usePredictions.ts (React Query hooks)
- app/src/components/charts/SentimentGauge.tsx
- app/src/components/charts/PredictionAccuracy.tsx
- app/src/components/charts/PredictionOverlay.tsx
- app/src/components/charts/SignalFeed.tsx
- supabase/migrations/20260319_kraken_and_predictions.sql
- tests/agent/ (TEST_PLAN.md, 4 flow files, lib helpers)

### Modified
- intel/wolfpack/exchanges/base.py (ExchangeId + "kraken")
- intel/wolfpack/exchanges/__init__.py (register KrakenExchange)
- intel/wolfpack/api.py (paper endpoints, prediction endpoints, orderbook, veto wiring)
- intel/wolfpack/agents/quant.py (EMA 9, VWAP, extension signals)
- intel/wolfpack/veto.py (EMA/VWAP conviction penalty)
- app/src/lib/exchange/types.ts (ExchangeId + config)
- app/src/lib/exchange/index.ts (export KrakenAdapter)
- app/src/app/intelligence/page.tsx (mount new visualizations)
- app/src/app/settings/page.tsx (Kraken description fix)
