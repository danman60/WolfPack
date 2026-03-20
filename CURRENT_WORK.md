# Current Work - WolfPack

## Last Session Summary
Two sessions combined: Built Kraken exchange adapter (Python CLI + TS proxy), AI dashboard visualizations (SentimentGauge, PredictionAccuracy, PredictionOverlay, SignalFeed), EMA/VWAP extension filter, prediction scoring module, glossary tooltip system (87 terms), toast notifications with animated intelligence progress bar, and scheduled cron jobs for intelligence + prediction scoring.

## What Changed
- [048d0dd] Kraken adapter + AI dashboard visualizations (9 new files, 1313 insertions)
- [0091970] Bug fixes: Kraken description in Settings, Signal Feed raw JSON
- [9a612ff] EMA/VWAP extension filter + veto penalties + test suite
- [6d53ddd] Test reports (3 runs, v3: 34/39 pass, 12/12 oracle match)
- [e7648b4] Glossary tooltip system (87 terms, Term.tsx with Framer Motion, Dashboard wired)
- [af46dce] Toast notifications (sonner) + animated IntelProgress bar
- [infra] API_SECRET_KEY on Droplet, NEXT_PUBLIC_INTEL_API_KEY on Vercel
- [infra] Cron: intelligence every 4h + prediction scorer daily 6am ET

## Build Status
PASSING — Next.js 16.1.6 Turbopack, 3.9s, 10 static pages

## Known Bugs & Issues
- UX-ISSUE: Quant agent displays raw JSON in Latest Analysis instead of prose
- UX-SUGGESTION: PredictionAccuracy shows "0%" — needs "Predictions tracked after trades" message
- UX-SUGGESTION: Portfolio win rate shows "--" instead of calculating from closed trades
- UX-SUGGESTION: Backtest failure doesn't surface error message to user
- Backtest on VPS returns "Insufficient candle data: 0 bars" — candle cache/fetch issue on Droplet

## Incomplete Work
- **Glossary tooltips**: Foundation done (glossary.ts + Term.tsx + Dashboard page). 7 remaining pages + 4 chart components need `<Term>` wrapping. Plan: docs/plans/2026-03-19-glossary-tooltips.md
- Need /design-pass on Term.tsx after all pages wired

## Tests
- 3 test runs (v1 smoke, v2 blocked by 403, v3 with auth: 34/39 pass)
- Latest: tests/reports/run-20260319-213924/report.md — 12/12 oracle matches
- Toast + progress bar NOT yet tested (deployed after last test run)

## Next Steps
1. **Wrap remaining 7 pages with `<Term>` glossary tooltips** (intelligence, trading, portfolio, backtest, auto-bot, pools, settings)
2. Run /design-pass on Term.tsx for polish
3. Fix Quant agent raw JSON display
4. Run DB migration for wp_prediction_performance table via Supabase MCP
5. Fix backtest candle fetch on Droplet (returns 0 bars)
6. Add win rate calculation to Portfolio page
7. Test Kraken CLI end-to-end on a machine with the binary

## Gotchas for Next Session
- **Droplet crons active**: Intelligence runs every 4h, scorer daily 6am ET. Logs at /var/log/wolfpack-*.log
- **API auth**: Droplet API_SECRET_KEY and Vercel NEXT_PUBLIC_INTEL_API_KEY both set to `1bee9d...b43b`
- **Vercel project**: `wolf-pack` (not `app`). Link with `vercel link --project wolf-pack`
- **Kraken CLI**: `~/.cargo/bin/kraken` — NOT installed on Droplet (1GB VPS, 98% disk)
- **EMA/VWAP veto**: penalties -8/-15 for EMA extension, -5/-15 for VWAP. Wired in api.py
- **GitNexus**: Indexed (943 nodes, 2383 edges). `.gitnexus/` exists.
- **sonner toast**: Added to layout.tsx, wired in useIntelligence.ts and trading/page.tsx
- **framer-motion**: Installed for Term.tsx and IntelProgress.tsx

## Files Touched This Session
### Created
- intel/wolfpack/exchanges/kraken.py, app/src/lib/exchange/kraken.ts
- intel/wolfpack/modules/prediction_scorer.py
- app/src/lib/hooks/usePredictions.ts
- app/src/components/charts/{SentimentGauge,PredictionAccuracy,PredictionOverlay,SignalFeed}.tsx
- app/src/lib/glossary.ts, app/src/components/Term.tsx
- app/src/components/IntelProgress.tsx
- supabase/migrations/20260319_kraken_and_predictions.sql
- tests/agent/ (TEST_PLAN.md, 4 flows, lib helpers)
- docs/plans/2026-03-19-glossary-tooltips.md

### Modified
- intel/wolfpack/exchanges/{base.py,__init__.py}, intel/wolfpack/api.py
- intel/wolfpack/agents/quant.py (EMA/VWAP), intel/wolfpack/veto.py
- app/src/lib/exchange/{types.ts,index.ts}, app/src/app/intelligence/page.tsx
- app/src/app/{settings,trading}/page.tsx, app/src/app/page.tsx
- app/src/app/layout.tsx (Toaster), app/src/lib/hooks/useIntelligence.ts (toast)
