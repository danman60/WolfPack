# Test Quality Feedback — run-20260319-145155

## Test Suite Quality
- **Coverage:** Good — 8/8 pages tested, all major CRUD flows attempted
- **Oracle verification:** 3/3 DB checks matched perfectly. Would be higher if intel service was up.
- **Screenshots:** 23 captured, covering all major states

## What Worked Well
- Snapshot-filter pipeline efficiently identified interactive elements
- DB oracle checks caught real values and confirmed accuracy
- Exchange toggle and data isolation tests were thorough and meaningful
- UX evaluation found actionable issues (error messaging, feedback)

## What Could Improve
- **Intel service dependency is a single point of failure.** 6 of 39 steps blocked by one service. Consider:
  - Adding a pre-flight health check for `/intel/health` (already in TEST_PLAN.md but wasn't enforced as a gate)
  - Marking intel-dependent steps with explicit "requires: intel_service" dependency tag
  - Having a fallback mode that tests UI rendering with mocked/existing data when intel is down
- **Watchlist CRUD and order submission are untestable when intel is down.** These are critical paths that should have direct Supabase fallback options for testing.
- **The test plan has 39 steps but many are conditional (SKIPPED when no data).** Consider seeding test data via Supabase before running tests to ensure full coverage regardless of app state.
- **Backtest run created a test row that couldn't be cleaned up.** The delete API also goes through intel. Should track these better and offer manual SQL cleanup.

## Recommendations for Test Plan v2
1. Add `/intel/health` pre-flight as hard gate — skip all intel-dependent steps if down
2. Seed test data (watchlist items, recommendations, positions) via direct Supabase SQL before testing
3. Add explicit dependency graph: `Step 10 depends_on: intel_service_up`
4. Add timing to each step for performance regression tracking
5. Consider separate "UI-only" and "full-stack" test modes
