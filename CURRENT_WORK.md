# Current Work - WolfPack

## Last Session Summary (2026-04-07 → 2026-04-08)
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
