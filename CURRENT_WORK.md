# Current Work - WolfPack

## ACTIVE — 2026-04-11 22:15 UTC — Multi-wallet evolution system live

**Droplet intel service:** Running latest commit, 2 active perp wallets.
**CB:** ACTIVE.
**Wallets:**
- paper_perp (v1 Full Send) — YOLO 5, aggressive shorts-first, $25.6K equity, 8 positions
- paper_perp_v2 (v2 Conservative) — YOLO 2, conviction_floor 50, $10K starting, new

---

## Session Summary (2026-04-11 08:18 → 22:15 — ~14 hours)

### Soak Test + Bug Fixes
- Soak test found 2 bugs: `engine` not defined in regime transition + drawdown tracking
- Fixed: wallet-aware engine refs in both paths
- Fixed: `round(price, 2)` replaced with `round_price()` across ALL trading paths (api.py, backtest_engine.py, live_trading.py, orb_session.py, mean_reversion.py) — critical for live cutover
- YOLO level persistence: new `wp_runtime_config` table, auto-restore on startup

### Profitability Research (Phase 2.1)
- Full trade journal decomposition: 184 trades, $3,959 net P&L
- Key finding: mean_reversion = 97% of profits, shorts dominate ($3,441 vs $518)
- SOL longs TOXIC (-$200), BTC longs dead weight ($1 on 25 trades)
- 97% of trade metadata NULL (regime_at_entry, conviction_at_entry) — blocks validation
- Report: `docs/research/2026-04-profitability-audit.md`

### Daily Report Cron (Phase 4.1)
- Script: `~/projects/sysadmin/wolfpack_daily_report.sh`
- Cron: 8 AM ET daily, sends Telegram + saves markdown archive
- Tested: 15 trades, 66.7% WR, +$465 for Apr 10

### YOLO Level Calibration
- VWAP filter: hard block at 1-2, soft penalty at 3-4, bypassed at 5
- Pump guard: max shorts scales 2/3/4/5/7 per YOLO level
- Max positions: 8 at level 4, 12 at level 5

### TOXIC Combo Blocking
- PerformanceTracker: TOXIC grade → threshold 999 (hard block)
- UNDERPERFORMING: threshold raised above base (was capped by bug)
- SOL long, LINK long, AVAX long blocked by data

### Overnight Full Send Config
- Level 5 sizing: brief_only_mult 1.0, min_perf_mult 0.85, 30s spacing
- Brief prompt at L5: pushes shorts with historical edge data, forbids "wait"
- full_send: base_pct 25%, 40 trades/day max

### Multi-Wallet Evolution System (Phases A-E)
- DB: wp_wallets extended with display_name, description, version, parent_wallet_id, generation, fitness_score
- Backend: per-wallet config loading from JSONB, per-wallet YOLO persistence, build_policy_from_config()
- API: 5 new endpoints (create, clone, summary, metrics, config patch)
- Frontend: /evolution dashboard with wallet cards, comparison table, config editor, create/clone dialogs
- 2 wallets running: v1 Full Send + v2 Conservative

---

## Commits This Session (11 total)
1. `e10794b` fix: wallet-aware engine in cycle + round_price across all trading paths
2. `79d838a` feat: persist YOLO level across service restarts
3. `38cc936` fix: calibrate YOLO levels — filters scale with aggressiveness
4. `5b3ce55` fix: block TOXIC combos + cap position stacking
5. `ede293b` feat: overnight Full Send config — target $500+
6. `b706c7e` feat: multi-wallet evolution system — Phase A+B
7. `be71ea5` feat: multi-wallet evolution — Phase C+D (API + dashboard)
8. Phase E commit pending deploy

---

## Next Session Should:
1. Check overnight P&L — did v1 Full Send hit $500 target?
2. Compare v1 vs v2 performance on /evolution dashboard
3. Fix metadata tagging (regime_at_entry, conviction_at_entry NULL on 97% of trades)
4. Phase 3 power tweaks informed by profitability audit
5. Live cutover prep (~Apr 13): verify prod_perp wallet activates correctly
6. ML layer: constitutional drives or credibility-weighted agents as v3 wallet

## Known Remaining Issues
- 97% trade metadata NULL (regime_at_entry, conviction_at_entry, strategy) — highest priority
- Equity inflation ($25K display vs $10K real) — legacy wp_auto_portfolio_snapshots
- exit_reason shows "manual" for strategy-path closes (cosmetic)
- Quant JSON parse failures on LINK (DeepSeek truncation)
