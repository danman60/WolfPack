# Current Work - WolfPack

## STATUS — 2026-04-12 — Phase 2 + Phase 3 complete

Multi-wallet evolution system is LIVE with 3 trading wallets + human heuristics active.

## Active wallets (post-reset, all at $25,000 baseline)

| Wallet | Gen | YOLO | Features | Starting |
|--------|-----|------|----------|----------|
| `paper_perp` (v1 Full Send) | 1 | 5 | Brief + veto + TOXIC blocking + regime-aware tracker | $25k @ 2026-04-12 22:01 UTC |
| `paper_perp_v2` (v2 Conservative) | 2 | 2 | v1 + higher conviction floor, mandatory SL, smaller positions | $25k @ 2026-04-12 22:01 UTC |
| `paper_perp_v3` (v3 Human Heuristics) | 3 | 2 | v2 + hunger/satisfaction/fear/curiosity drives | $25k @ 2026-04-12 22:26 UTC |

## What shipped this session

### Phase 2 — multi-wallet UI + infra polish
- **Wallet reset** (`e217067` chain): v1 + v2 closed all positions, both forced to exactly $25,000 with fresh snapshots, trade history preserved so PerformanceTracker keeps its learned grades
- **CLAUDE.md multi-wallet protocol** (`7bbc7b2`): mandatory "confirm which wallet" rule before touching trading-logic files, documents active wallet list
- **Mobile landing enhancement** (`dc0a7a3`): evolution wallet cards now show position count, % return from starting_equity (green/red), 80-char thesis tagline, tap-through to /evolution detail
- **Evolution dashboard normalized chart** (`717637d`): new NormalizedEquityChart recharts LineChart plotting % return from reset timestamp, client-side-filtered to post-reset snapshots, emerald v1 / amber v2, "Waiting for cycle data…" placeholder
- **WalletCard metadata** (`8b0ca24`): Gen N purple badge, parent lineage row ("↑ v1 Full Send"), "Created Nd ago" relative timestamp
- **Wallet metadata backfill**: paper_perp.generation=1, paper_perp_v2.generation=2, both starting_equity=25000

### Phase 3 — v3 Human Heuristics
- **Migration** (`27b1925`): `wp_wallet_state` + `wp_wallet_state_history` tables applied via supabase-CCandSS MCP
- **HeuristicState class** (`4d12694`): `intel/wolfpack/heuristics.py` — dataclass with decay, on_target_progress, on_trade_close, on_unfamiliar_setup, conviction_modifier, size_modifier, exploration_budget, snapshot/load/save. 25 unit tests at `intel/tests/test_heuristics.py`, all passing.
- **/heuristics/state endpoint** (`3cc2688`): observability — current state + history rows + computed modifiers
- **v3 wallet created** (direct DB insert after POST /wallets): cloned v2 Conservative config + `heuristics_enabled: true`, `daily_pnl_target: 300`
- **AutoTrader wiring** (`e217067`): `_apply_wallet_config` loads HeuristicState on init, `_refresh_heuristics()` runs per-cycle (decay + poll closed trades + update target progress + persist), conviction_modifier adjusts floor, size_modifier scales positions, curiosity caps exploration sizing for tier=none setups
- **Brief template** (`e217067`): conditional `heuristic_state` section ready — dormant until per-wallet Brief invocation (Brief is currently shared across wallets)

## Verified live
- v3 heuristic refresh firing every cycle: `[heuristics] v3 refreshed: daily_pnl=$+0.00/$300 H=0.80 S=0.20 F=0.50 C=0.52 conv_mod=+0 size_mod=1.08`
- Curiosity exploration-sizing firing on unfamiliar setups: `[heuristics] DOGE short explore-sizing mult=0.28 (budget=0.26)`
- v1/v2 completely untouched — no heuristic logs for them

## Known items
- `POST /wallets` doesn't respect `clone_from` for `generation`/`version` — hardcodes 0/1. Worked around by direct DB UPDATE. Worth fixing in a future wallet-API cleanup.
- `wp_trade_history` has 3 phantom AVAX short rows from the v3-init close loop (+$207 each × 3) — minor perturbation to global tracker, not worth cleaning.
- `MIN_DIR_REGIME=9` currently doesn't block `short RANGING` because the rolling-50 window dropped one trade; the pattern is still TOXIC at 8t but below the activation threshold. Will re-trip on the next RANGING short loss.

## Next (blocked — future phases)
- Phase 4 (task #18): v4 wallet with SOTA Learned Agency (intrinsic rewards, forward model, meta-learned risk). Gated by v3 having 7+ days of live data for A/B.
- Phase 5 (task #19): v5 combinatorial breeding of best traits from v2-v4.

## Live cutover reminder
Tomorrow (~2026-04-13): `prod_perp` goes live with $1k real capital via MetaMask + Hyperliquid. Currently `status=paused`.
