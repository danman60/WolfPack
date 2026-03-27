# Current Work - WolfPack

## Last Session Summary
Built the YOLO Meter feature — a single UI slider on the Auto-Bot page that controls trading aggressiveness across all 6 throttle layers (conviction threshold, veto floor, trade limits, penalty scaling, cooldown, position sizing). Set to level 4 (YOLO) to increase trade activity on paper trading.

## What Changed
- `24ff3b4` feat: YOLO Meter — single slider controls trading aggressiveness (5 files)
  - `intel/wolfpack/auto_trader.py` — YOLO_PROFILES dict (5 levels), `_apply_yolo_profile()`, configurable veto/CB params
  - `intel/wolfpack/veto.py` — BriefVeto now accepts conviction_floor, penalty_multiplier, rejection_cooldown_hours
  - `intel/wolfpack/api.py` — POST /auto-trader/yolo-level endpoint
  - `app/src/lib/hooks/useIntelligence.ts` — useSetYoloLevel mutation, AutoTraderStatus extended
  - `app/src/app/auto-bot/page.tsx` — YOLO Meter slider UI with gradient track, 5 labeled stops, profile stats grid

## Build Status
PASSING — Next.js build clean, Python imports verified, GitNexus re-indexed (1,004 symbols)

## Known Bugs & Issues
- YOLO level is stored in-memory only (resets on intel service restart). Should persist to Supabase wp_settings or similar.
- Circuit breaker MAX_TRADES_PER_DAY is still hardcoded at 4 in circuit_breaker.py — the YOLO meter relaxes the CB check in auto_trader.py but doesn't modify the CB module itself. At levels 4-5, CB SUSPENDED state is ignored (only EMERGENCY_STOP blocks).

## Incomplete Work
- None — feature is complete and building

## Tests
- No test run this session
- Untested: YOLO meter UI interaction, API endpoint, profile application during intelligence cycle

## Next Steps (priority order)
1. Deploy intel service with YOLO meter changes and verify trades execute at level 4
2. Persist yolo_level to Supabase so it survives service restarts
3. Monitor auto-bot activity over next 24h — expect significantly more trades at level 4
4. Consider wiring MAX_TRADES_PER_DAY in circuit_breaker.py to YOLO profile for full integration
5. Run backtest with OverfitDetector to validate IS/OOS splits

## Gotchas for Next Session
- YOLO level defaults to 4 in code (`auto_trader.py:23`) — if user wants to change default, edit there
- The veto penalty_multiplier at level 4 is 0.25 (penalties quartered), at level 5 is 0.0 (penalties disabled)
- At levels 4-5, only EMERGENCY_STOP blocks trades (CB SUSPENDED is bypassed)
- Pre-existing uncommitted files (tests/, overnight notes, .claude/) are from prior sessions — not from this session

## Files Touched This Session
- `intel/wolfpack/auto_trader.py` — YOLO profiles + apply logic
- `intel/wolfpack/veto.py` — configurable conviction floor, penalties, cooldown
- `intel/wolfpack/api.py` — /auto-trader/yolo-level endpoint
- `app/src/lib/hooks/useIntelligence.ts` — useSetYoloLevel hook
- `app/src/app/auto-bot/page.tsx` — YOLO Meter UI component
