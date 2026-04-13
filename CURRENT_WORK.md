# Current Work - WolfPack

## STATUS — 2026-04-13 — Regime-adaptive strategy framework complete

Every mechanical strategy is now regime-adaptive. 6-regime taxonomy live with TRANSITION handling. All 3 wallets share the same regime-aware strategy layer — flavors (v1/v2/v3) live in risk profile / YOLO / heuristic drives, not in regime logic.

**Core directive from the user:** the autobot must be profitable in ANY market regime, not just trending weeks. Every strategy auto-tunes to the current regime and auto-switches when transitions are detected.

## Active wallets (post-reset, all at $25,000 baseline)

| Wallet | Gen | YOLO | Features | Starting |
|--------|-----|------|----------|----------|
| `paper_perp` (v1 Full Send) | 1 | 5 | Brief + veto + TOXIC blocking + regime-aware tracker | $25k @ 2026-04-12 22:01 UTC |
| `paper_perp_v2` (v2 Conservative) | 2 | 2 | v1 + higher conviction floor, mandatory SL, smaller positions | $25k @ 2026-04-12 22:01 UTC |
| `paper_perp_v3` (v3 Human Heuristics) | 3 | 2 | v2 + hunger/satisfaction/fear/curiosity drives | $25k @ 2026-04-12 22:26 UTC |

## What shipped this session (2026-04-13 morning)

### Regime-Adaptive Strategy Framework — 6 regimes, every strategy tuned

**Motivation:** v1 peaked at $4,720 in 7 days (Apr 6–Apr 12) during TRENDING-dominant conditions, then flattened to near-zero when the regime shifted to RANGING chop. Root cause: `mean_reversion`'s default 3.0 ATR threshold was mathematically inert in normal chop (it was tuned for extreme capitulation fades), and trending strategies like ema_crossover / turtle_donchian kept whipsawing on false crosses inside the range. No strategy actually traded the chop.

**Canonical regime taxonomy:**
| Specific | Family | Detection trigger | Strategies allowed |
|---|---|---|---|
| `TRENDING_UP` | TRENDING | regime=trending_up + agreement≥0.75 | ema_crossover(long), turtle_donchian(long), orb_session |
| `TRENDING_DOWN` | TRENDING | regime=trending_down + agreement≥0.75 | ema_crossover(short), turtle_donchian(short), orb_session |
| `RANGING_LOW_VOL` | RANGING | choppy + vol∈{low,normal} | mean_reversion, band_fade (tight params) |
| `RANGING_HIGH_VOL` | RANGING | choppy + vol=elevated | mean_reversion, band_fade (wider params) |
| `VOLATILE` | VOLATILE | panic OR vol=extreme | none — tighten stops to 1.5% |
| `TRANSITION` | TRANSITION | pending≠current AND debounce<3 | none — tighten stops to 2.0%, wait |

**New strategy:** `band_fade` (`intel/wolfpack/strategies/band_fade.py`) — pure RANGING play. Fires on Bollinger Band touches confirmed by RSI(14) overbought/oversold. Targets the middle band (SMA) for TP with tight stops beyond the outer band. HIGH_VOL/LOW_VOL sub-regime presets for band stdev + RSI thresholds.

**Regime adaptation per strategy:**
- `mean_reversion` — `REGIME_PRESETS` dict maps sub-regimes to `{mean_period, threshold_atr_mult, stop_atr_mult, size_pct}`. RANGING_LOW_VOL uses 1.2 ATR threshold (was 3.0 globally — killer bug). RANGING_HIGH_VOL uses 2.0. TRENDING keeps 3.0 for contrarian fades.
- `band_fade` — `_REGIME_PRESETS` dict: RANGING_LOW_VOL uses 2.0σ BB + RSI 35/65 / 0.6 ATR stop; RANGING_HIGH_VOL uses 2.5σ + RSI 30/70 / 0.9 ATR stop. Disabled everywhere else.
- `ema_crossover` — directional gate: TRENDING_UP allows longs only, TRENDING_DOWN allows shorts only. Disabled in RANGING/VOLATILE/TRANSITION. Conviction bumped to 75 when cross aligns with trend.
- `turtle_donchian` — same gating. Close signals still fire regardless of regime (structural exit for existing positions stays regime-agnostic).
- `orb_session, measured_move, regime_momentum, vol_breakout` — untouched in this pass (future work).

**TRANSITION handling** (new in `auto_trader.process_strategy_signals`): distinct from VOLATILE. When router detects pending regime changing mid-debounce, tightens any trailing stop wider than 2.0% by factor 0.7 (floor 2.0%) and blocks new entries until debounce confirms. Existing positions are preserved — it's a "wait and see" posture.

**Router emits both family and specific:**
```python
{
  "allowed": [...],
  "macro_regime": "RANGING",            # parent family (back-compat)
  "specific_regime": "RANGING_LOW_VOL", # sub-type for granular tuning
  "transition": False,
  "reason": "...",
  "debounce": "pending=RANGING_LOW_VOL(3/3)"
}
```

**Commits (2026-04-13):**
1. `db6ec79` `feat(strategies): mean_reversion regime-adaptive parameters`
2. `7e17617` `feat(strategies): band_fade — Bollinger+RSI range fader, wired into router`
3. `f6d8248` `feat(regimes): 6-regime taxonomy + regime-adaptive strategies + TRANSITION state`
4. `74027cd` `feat(api): /regime/state observability + regime taxonomy doc`
5. `44becd6` `fix(api): update get_regime_state callers to new field names`

**Also shipped** (earlier 2026-04-13 morning): heuristic math bug fix (`5997acd`) — drive contributions now centered on baseline so v3's hunger actually dominates. Live verification: `[heuristics] DOGE short floor 50 -> 44 (-6)` is firing as designed.

**Live verification post-deploy:**
- `[auto-trader] Regime routing: RANGING_LOW_VOL (family=RANGING) -- regime=choppy, agreement=0.50, vol=normal` ✓
- `[auto-trader] Regime routing: TRENDING_DOWN (family=TRENDING) -- regime=trending_down, agreement=1.00` ✓ (DOGE hit this)
- `[auto-trader] Regime routing: RANGING_HIGH_VOL (family=RANGING) -- regime=choppy, agreement=0.50, vol=elevated` ✓
- Heuristic conv_mod = -6 and size_mod = 1.12 both applying to live trades
- `GET /regime/state?symbol=BTC` returns current + pending + transition flag
- **Known:** only 3 cycles observed since restart — too early to measure strategy signal frequency. Let it run 1+ hour for mean_reversion / band_fade fire rate.

**Taxonomy doc:** `docs/regime-strategy-map.md` — single source of truth for which strategies fire in which regimes and their regime-specific params. Read this before adding a new strategy.

---

## What shipped yesterday (2026-04-12)

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
