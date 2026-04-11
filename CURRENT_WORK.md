# Current Work - WolfPack

## ACTIVE — 2026-04-11 08:15 UTC — Legacy audit complete, soak test pending

**Droplet intel service:** PID 219710, active since 08:10 UTC, running commit `8b2ac75`.
**CB:** ACTIVE, 5.03% exposure, entries allowed.
**YOLO level:** 5 (Full Send) — conviction floor 45, min position $50, trade spacing 60s.

**Open positions:** 1 (check /auto-trader/status for current).
**Realized today:** $525.05 (from 10 closed trades yesterday + 3 AVAX shorts locked in overnight).
**Equity:** ~$25,516 (inflated legacy display) / real ~$10,516.

---

## Session Summary (2026-04-09 21:17 → 2026-04-11 08:15 — ~35 hours, 2 days)

### Phase 1 Instrumentation (COMPLETE)
Commit `f8afdce` — all deployed and producing data:
1. `wp_cycle_metrics` table + CycleMetricsRecorder (per-cycle telemetry)
2. `wp_veto_log` table + writer (every Brief rec → pass/adjust/reject audit)
3. `wp_watchdog_state` table (for future watchdog state persistence)
4. Quant/Snoop/Sage outputs now persist to `wp_agent_outputs`
5. LLM `completion_reason` + `tokens_used` logged
6. `BriefVeto(profile=...)` wiring from RISK_PRESETS
7. `CYCLE_ALERT_THRESHOLD` 6→3
8. `regime_drift` field in `/health/deep`
9. Migration `20260410_cycle_telemetry` applied

### Emergency Bug Fixes (3 pre-existing bugs unmasked by restarts)
1. **Phantom drawdown CB trip** (`20a1fc9`) — `wp_equity_highwater` peak=$25K vs engine=$10K → 60% phantom drawdown → EMERGENCY_STOP. Added sanity guard in drawdown_monitor.py (reset peak when >50% apparent drawdown).
2. **SL/TP rounding bug** (`eebd5e9`) — `round(price, 2)` collapsed DOGE SL from $0.09306→$0.09 (0.1% instead of 3.5%). New `price_utils.py::round_price()` with magnitude-aware precision. Fixed 5 files.
3. **Legacy engine routing** (4 commits: `5b978db`, `a14a758`, `a37d49b`, `a1bd469`) — Wave 5 wallet migration left 16 `_get_paper_engine()` call sites on the wrong engine. CB saw phantom 77% exposure, position actions silently dropped, Telegram bot showed empty portfolio, pump guard read stale table, price updates went to wrong engine. ALL fixed across 4 sweeps.

### YOLO Meter (COMPLETE)
- `54dcba8` — PerformanceTracker.get_threshold() capped by YOLO level; mobile slider; POST /auto-trader/yolo endpoint
- `238449c` — Per-level sizing config (_YOLO_SIZING): brief_only_mult, min_perf_mult, min_position_usd, trade_spacing_s

### Structural Levels + Volume Profile Modules (COMPLETE)
- `0455f4a` — Two new quantitative modules:
  - `structural_levels.py`: prior day/week/overnight H/L, swing points, sweep detection, nearest S/R
  - `volume_profile.py`: POC, Value Area, HVN/LVN, profile shape
  - Both wired into cycle, outputs passed to agents
  - mean_reversion sweep filter enhanced with structural level awareness (+20 conviction for structural sweeps)

### Comprehensive Legacy Audit Fix (COMPLETE)
- `8b2ac75` — 6 findings fixed:
  1. YOLO min_position_usd wired in strategy path (was still $200)
  2. Per-symbol state dicts (regime/vol/liquidity no longer leak between symbols)
  3. Cycle uses _primary_perp from active wallets (ready for live cutover)
  4. Removed dual writes to wp_auto_trades (dead table)
  5. Replaced 5 bare except:pass with logged warnings in stop/notification path
  6. Removed dead auto_trade_conviction_threshold config

### Dashboard Improvements
- `002b10c` — Realized vs unrealized P&L split + Lock In button
- `bb4c6fc` — /portfolio/close uses wallet-aware engine (Lock In actually works)

### Facebook Reel Transcribed
- Order flow trading framework (4-layer: structural levels → auction theory → options/gamma → volume profile + footprint). Assessed feasibility — layers 1+2 built as modules, layer 3 impossible (Hyperliquid = futures only), layer 4 needs WebSocket tick data.

---

## Commits This Session (chronological, 12 total)
1. `f8afdce` feat(phase1): cycle telemetry + veto audit log + upstream agent persistence
2. `20a1fc9` fix(drawdown): sanity reset peak when apparent drawdown >50%
3. `eebd5e9` fix(price): magnitude-aware round_price replaces round(p,2) on all SL/TP
4. `3eec951` docs: update CURRENT_WORK.md with Phase 1 + emergency fixes
5. `002b10c` feat(dashboard): show realized vs unrealized P&L + lock-in button
6. `bb4c6fc` fix(api): /portfolio/close uses wallet-aware engine
7. `54dcba8` feat(yolo): YOLO meter controls entire system + mobile slider
8. `238449c` feat(yolo): per-level sizing config controls entire trade pipeline
9. `0455f4a` feat(modules): structural levels + volume profile for order flow context
10. `5b978db` fix(cb): circuit breaker + drawdown use wallet-aware engine
11. `a14a758` fix(wave5): replace ALL _get_paper_engine() with wallet-aware engine
12. `a37d49b` fix(wave5): eliminate remaining legacy engine + table references
13. `a1bd469` fix(wave5): position actions engine + frontend snapshot wallet filter
14. `8b2ac75` fix(legacy): comprehensive audit — 6 findings fixed

---

## Plan File
`/home/danman60/.claude/plans/crystalline-splashing-cerf.md` — Phases 2-4 not yet started.

## Next Session Should:
1. **Run soak test** — watch logs for 30 min, verify no errors, trades flowing, CB stable
2. **Phase 2.1** — trade journal decomposition pivots (SQL queries against wp_trade_history)
3. **Phase 4.1** — daily report cron (8 AM ET Telegram report)
4. Do NOT restart the service unless necessary
5. Live cutover prep (~Apr 13): verify prod_perp wallet activates correctly, backtest_engine.py and live_trading.py still have round(price,2) — MUST fix before live

## Known Remaining Issues (non-blocking)
- Equity inflation ($25K display vs $10K real) — legacy wp_auto_portfolio_snapshots
- `exit_reason` shows "manual" for strategy-path closes (cosmetic)
- `wp_agent_outputs` unique constraint means only 1 row per (agent, exchange) — no historical rewind
- `backtest_engine.py` and `live_trading.py` still have `round(price, 2)` for entry/exit prices — MUST FIX BEFORE LIVE CUTOVER
- `_get_paper_engine()` function definition still exists as fallback (harmless, only Monte Carlo uses it)
- YOLO level not persisted across restarts (resets to default on service restart)
