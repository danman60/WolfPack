# Current Work - WolfPack

## Session Summary (2026-04-09) — Veto Latching Fix + Zero-Trade Watchdog

User reported "1h/4h/12h on the site are all the same" on the mobile Profit Report. Investigation confirmed: the periods were all showing $0 because **trading had been silent for 39 hours** despite a healthy service. Root cause was a veto latching loop, fixed this session. Also installed a persistent zero-trade watchdog since this was the 5th no-trade outage.

### Veto latching bug (commit `6abea8e`)

**File:** `intel/wolfpack/veto.py:213` — `_record_rejection()`

`VetoEngine` is a module-level singleton (`api.py:1037-1043`) — `_recent_rejections` dict persists across cycles. The -20 recent-rejection penalty (line 190) was dropping conviction below floor, triggering another rejection at line 197, which **refreshed the cooldown timer** instead of preserving it. All 7 watchlist symbols latched out forever.

Log evidence before fix:
```
[veto] Rejected LINK long: ['LINK rejected within last 2.0h: -20 conviction',
                            'adjusted conviction 35 < 55 after penalties']
```

Fix: guard against refreshing the timer when already in cooldown. 2h window now absolute from first rejection.

**Verified post-deploy:** DOGE long at conviction 55 now PASSES the veto. Pending regime counter reset from stuck 176/3 to fresh 4/3. Veto log pattern shifted from latching to legitimate `'direction is wait'`.

### Zero-trade watchdog (new)

**Script:** `/home/danman60/projects/sysadmin/zero_trade_watchdog.sh`
**Cron:** `*/15 0-17 * * *` (every 15 min during UTC trading hours)
**Alerting:** Telegram (same bot/chat as `health_ping_wolfpack.sh`)

Escalation:
| Silent for | Severity | Cadence |
|---|---|---|
| ≥3h | warn | once per 4h |
| ≥6h | alert | every 2h |
| ≥12h | critical | every 1h |
| ≥2h no new recs | warn | once per 4h |

Runs on SpyBalloon (independent of droplet). Queries Supabase REST directly via `SUPABASE_SERVICE_ROLE_KEY` in `~/.env.keys`. If droplet dies, watchdog still fires. State file: `/tmp/wolfpack-zero-trade-state`. Log: `/tmp/wolfpack-zero-trade.log`.

Smoke-tested: critical alert fires correctly, cooldown suppresses repeats, state persists, recovery message triggers on clear.

### NEW blocker discovered (not yet fixed)

**Position sizing multiplier chain is producing sub-$500 positions.** After veto fix, DOGE long passed veto but got `[auto-trader] DOGE long skipped: $218 < $500 minimum`.

Root cause chain in `intel/wolfpack/auto_trader.py:372-378`:
- `size_multiplier = 0.25` if Brief-only (no mechanical strategy alignment) — line 372
- `perf_mult = self._perf_tracker.get_size_multiplier(symbol, direction)` — further scales down based on historical performance per (symbol, direction)
- `estimated_usd = equity × (size_pct × size_multiplier × perf_mult / 100)` → $218 for DOGE

The system REQUIRES Brief+mechanical alignment for full-size trades. When The Quant's DeepSeek truncates (happening ~50% of the time) and fallback chain is exhausted (OpenRouter 402, Anthropic 400), mechanical signals may not fire reliably, leaving Brief solo at 0.25x size.

**Mitigation options (not chosen yet):**
1. ~~Top up OpenRouter or Anthropic credits~~ — RULED OUT. User directive: those are out of the fallback chain entirely (commit `37e0588`).
2. Lower the min_position_usd floor (e.g., $200) to let Brief-only trades through
3. Raise the Brief-only multiplier from 0.25 → 0.5
4. Fix DeepSeek truncation more aggressively (smaller max_tokens, simpler schemas)

### LLM fallback chain rewritten (commit `37e0588`)

**Old chain:** DeepSeek → Minimax(Tailscale) → Kimi → OpenRouter → Anthropic
**New chain:** DeepSeek → Minimax(Ollama Cloud) → GLM(Ollama Cloud) → Kimi(NIM) → stop

Key changes in `intel/wolfpack/agents/base.py::_call_llm_structured`:
- **Removed OpenRouter and Anthropic entirely.** The chain now returns a fallback result instead of burning paid API credits. Anthropic and OpenRouter API keys are retained in config for any non-fallback uses but are not in `_call_llm_structured`.
- **Fixed Minimax endpoint.** Was `http://100.75.112.14:11434/v1` (FIRMAMENT's Tailscale IP — unreachable from droplet). Now `https://ollama.com/v1` via `OLLAMA_API_KEY` from config. Verified working with curl from SpyBalloon.
- **Added GLM block** (`glm-5.1:cloud`) using same Ollama Cloud endpoint and key. Verified working (reasoning-heavy so slower, but OK at 2048 max_tokens).
- **Kimi via NIM** unchanged — already worked.
- Added `ollama_api_key` and `ollama_cloud_base_url` to `config.py`.
- Appended `OLLAMA_API_KEY` to droplet's `/root/WolfPack/intel/.env`.

Verified post-deploy: service restarted (PID 3956180 at 16:55:24 UTC), DeepSeek responding cleanly, zero calls to `openrouter.ai` or `api.anthropic.com` across new cycles.

### Backlog items (discovered, not addressed)

1. **Duplicate trade inserts:** 3 DOGE shorts at 23:13:01 UTC ±90ms, same prices, different pnl values (+$674, -$28, -$28). The close path fires multiple writes. Dedup RPC `get_deduplicated_pnl` masks from stats but raw data is wrong. Trace close_position path.
2. **`max_exposure_pct` schema mislabel:** `api.py:1861` persists `cb_output.total_exposure_pct` (current actual) into a column literally named `max_exposure_pct` (which should be the limit). Misleading. Rename column or use dedicated `current_exposure_pct` column.
3. **Regime pending counter** was stuck at `RANGING(176/3)` pre-restart — counter climbs but never commits. Likely per-symbol state; worth confirming the threshold logic.
4. **Per-direction rejection cooldown:** a LONG rejection currently blocks SHORT opportunities on same symbol. Split key into `(symbol, direction)`.
5. **Consider shorter cooldown:** 2h may still be too conservative with the fix. Tunable via `risk_controls.py` profile.
6. **`wp_agent_outputs` stale `created_at`:** row shows Apr 3 but upserts happen every cycle. Upsert preserves original `created_at` on conflict. Add `updated_at` column for freshness monitoring.

### Profitability context (pre-outage, Apr 5-8)

5-day net: **+$2,850** — edge is real:
- Shorts: 67% WR, 8.7:1 R:R, $3,016 profit
- Longs: 46% WR, 2.4:1 R:R, $475 profit
- Winners: mean_reversion short BTC (9/9), LINK short (+$740), DOGE/ARB shorts (+$1,288)
- Losers: mean_reversion long SOL/AVAX/LINK (all net negative)

**Once Brief+mechanical alignment resumes, the edge should restart automatically.** The watchdog will catch it within 3h if it doesn't.

---

## Previous Session (2026-04-07 → 2026-04-08)
Massive debugging + improvement session. Fixed LP rebalance churn ($9K paper loss), false panic regime detection blocking all trading, DeepSeek JSON truncation killing recommendation pipeline, and added multiple strategy filters (VWAP, displacement, liquidity sweep, pump guard). Also evaluated Kronos prediction model (42% accuracy, rejected). 30+ commits in 2 days.

## What Changed (key commits this session)
- `0afadfb` fix: false panic on normal crypto vol (ATR needs 3% absolute, not just 92nd percentile)
- `9d7fa2d` feat: VWAP filter — only long when price > VWAP
- `7df7fc6` fix: slim Brief prompt preventing DeepSeek truncation
- `230822b` fix: slim Quant prompt preventing DeepSeek truncation
- `39c647d` feat: fallback chain DeepSeek → Minimax → Kimi → OpenRouter → Claude
- `aae8eb2` fix: fallback triggers on truncated responses, not just exceptions
- `f51aa09` fix: 3 LP bugs (rotation exit min age, DB-persisted cooldown, USD price ratios)
- `682800c` feat: pump guard (max 3 shorts + 2% pump detection)
- `221ade8` feat: displacement filter on mean_reversion
- `7dda910` feat: liquidity sweep filter + Wolf of Wall Street TG digest

## Build Status
DEPLOYED — intel service running on droplet (159.89.115.95), frontend on Vercel.
Service healthy, regime now correctly detecting TRENDING (was falsely stuck on PANIC).

## Current State
- Perp: $10,058 (auto-trader bucket) / $28,561 (snapshot — DISAGREES, needs cleanup)
- Perp realized P&L: $2,864 (wp_trade_history, ground truth)
- LP: $15,081 (reset from $15K today after $9K bug loss, now healthy)
- 2 open perp positions: BTC long +$15, ETH long +$20
- 6 LP positions, $25 fees, $0.59 IL
- Regime: TRENDING UP (was falsely PANIC all day until last fix)
- Recommendations flowing again (BTC long conv 65, DOGE long conv 55)

## CRITICAL: Architecture Cleanup Needed
The #1 priority for next session. Multiple overlapping tracking systems:

### Current mess:
- `wp_trade_history` — trade P&L ($2,864 total) ← GROUND TRUTH
- `wp_auto_trades` — auto-trader's copy (0 closed trades, broken/unused)
- `wp_auto_portfolio_snapshots` — equity $28,561 / realized $3,675 (WRONG, doesn't match)
- `wp_portfolio_snapshots` — yet another portfolio tracker
- `PaperTradingEngine` — auto-trader's engine ($10K starting)
- LP has separate `PaperLPEngine` ($15K starting)

### What it should be:
- ONE perp wallet, ONE equity number, ONE trade table, ONE snapshot table
- LP stays separate (different engine)
- User sees: perp balance + LP balance = total
- Delete or consolidate: wp_auto_trades, wp_auto_portfolio_snapshots confusion
- The frontend portfolio page needs to show the REAL numbers

### Plan approach:
1. Audit all tables — which are actually used, which are stale
2. Pick the single source of truth for perp P&L (wp_trade_history)
3. Remove or redirect duplicate tracking
4. Update frontend to show consolidated view
5. Test that the auto-trader still works with simplified backend

## Known Issues
- Only BTC and DOGE generating recommendations — LINK/SOL/ARB/AVAX still not producing recs despite being on watchlist and cycle running. May need same Brief prompt slimming applied to Snoop/Sage agents.
- Ethereum mainnet pool addresses (0x88e6a0c2, 0x11b815ef, etc.) still appearing in LP monitor logs as "No data" — cosmetic but noisy.
- Minimax fallback times out from droplet (can't reach FIRMAMENT's Tailscale IP 100.75.112.14).
- OpenRouter out of credits. Anthropic out of credits. Only DeepSeek working as primary.
- DeepSeek still truncating some responses despite prompt slimming — not all agents fixed yet.
- Pipeline skill now has cost-comparison gate (added this session).

## Strategy Filters Stack (current)
1. Trading hours: 0-18 UTC
2. VWAP filter: longs blocked when price < VWAP
3. RANGING penalty: mean_reversion longs -10 conviction
4. Displacement filter: exhaustion candle +10 conv, strong push -15
5. Liquidity sweep filter: sweep confirmed +15 conv (70 vs 55)
6. Pump guard: max 3 shorts, block new shorts on 2%+ pump
7. Regime transition: closes wrong-regime positions on shift
8. Position sizing: $500-$7K bounds

## LP Bug Fixes (all deployed)
1. Rebalance cooldown: DB-persisted (was memory-only, reset on restart)
2. Rotation exit: requires 2hr hold + $1 fees minimum
3. Price ratio: uses USD prices (was hardcoded wrong decimals)
4. Ethereum pool purge: on restore + deleted from DB
5. Vol_shift threshold: 50% (was 20%)
6. Cooldown keyed on pool_address (was position_id)

## Regime Detection Fix
- `_classify_regime` now requires ATR > 3% of price for PANIC (absolute check)
- Previously: any 92nd percentile ATR spike = PANIC, even on normal 2% crypto day
- This was the root cause of zero trading all day (Apr 8)

## Next Steps (Priority Order)
1. **Architecture cleanup** — consolidate perp tracking to ONE wallet/table
2. **Fix remaining agent truncation** — Snoop and Sage may need same prompt slimming
3. **Monitor overnight** — let the fixed system run without deploys
4. **Validate $750/day potential** — need 5+ days of stable profitable trading
5. **Live cutover prep** — originally ~Apr 13, delayed by bug fixes
6. Top up OpenRouter/Anthropic credits for fallback chain

## Files Touched This Session
- intel/wolfpack/api.py (logging, VWAP wiring, regime transition)
- intel/wolfpack/auto_trader.py (VWAP filter, pump guard, long penalties, _is_pumping)
- intel/wolfpack/agents/base.py (fallback chain, _is_fallback_result, max_tokens, _call_cloud_structured)
- intel/wolfpack/agents/quant.py (slim context)
- intel/wolfpack/agents/brief.py (slim context)
- intel/wolfpack/modules/regime.py (false panic fix, absolute ATR check)
- intel/wolfpack/modules/lp_rebalance.py (DB-persisted cooldown)
- intel/wolfpack/modules/lp_monitor.py (USD price ratio method)
- intel/wolfpack/lp_auto_trader.py (rotation exit min age, USD price ratios)
- intel/wolfpack/strategies/mean_reversion.py (displacement + liquidity sweep filters)
- intel/wolfpack/notification_digest.py (4H P&L report, Wolf of Wall Street format)
- intel/wolfpack/config.py (guardrail values)
- intel/wolfpack/response_parser.py (truncation recovery)
