# Current Work - WolfPack

## Last Session Summary
Massive session: researched NoFx trading platform for architectural patterns, implemented 7 new safety/resilience modules, built full LP Autobot (5 phases), fixed multiple bugs (Telegram spam, DeepSeek 400s, backtest data contamination, lookahead bug), added ORB FVG filter, and analyzed strategy performance.

## What Changed (15 commits this session)
- `516ade5` fix: strategy allocations + timeframe routing — mean_rev 25%, ORB/measured_move get 5m candles
- `d1c4913` fix: prevent same-cycle TP/SL triggers (lookahead bug)
- `ac03183` feat: LP pool rotation engine — autonomous yield hunting + capital rotation
- `667021a` fix: replace dead subgraph with RPC + GeckoTerminal hybrid
- `882513e` fix: persist LP watched pools via config env var
- `66ca971` feat: LP rebalance engine — debounced OOR + IL triggers with cooldown
- `455dd4d` feat: LP fee manager — auto-harvest with compound/sweep decisions
- `b47f5cf` feat: LP range calculator + auto-open paper positions
- `d95590c` feat: LP AutoTrader orchestrator + API endpoints
- `181e55b` feat: ORB strategy — FVG displacement filter + retest engulfing confirmation
- `bc2d116` feat: LP Autobot Phase 1 - Paper Engine + Monitor + Migration
- `cb25376` feat: regime debounce — require 3 consecutive ticks before macro shift
- `dad18a3` fix: backtest trades polluting live trade history + dedup bot profit tool
- `7ea4cc4` feat: add get_profit tool to Telegram bot
- `92982a0` feat: NoFx pattern integration — 7 modules for safety, resilience, observability

## Build Status
DEPLOYED — intel service running on droplet (159.89.115.95)

## Perp Autobot Performance
- Clean 24h: +$1,033 (after lookahead fix)
- Mean reversion dominant: $1,220 total, 62.5% WR, 5.6:1 R:R
- Strategy allocations updated: mean_rev 25%, regime_momentum 5%
- ORB/turtle/measured_move now receive correct candle timeframes

## LP Autobot (NEW)
- $15K paper equity, 6 positions, 10 scanner candidates
- Fees: $10.90, IL: $1.03, net: +$9.87
- RPC + GeckoTerminal hybrid (free, no API keys)
- Pool rotation engine scans top pools every 3h

## Known Issues
- Telegram notifications still too frequent — need to check what's bypassing digest
- `[training] Failed to append training data: name 'os' is not defined`
- `wp_position_actions` duplicate key errors on auto-executed actions
- Pipeline tmux launch failures (zombie windows) — sent to sysadmin INBOX

## Next Steps (Priority Order)
1. Fix remaining Telegram notification spam
2. Strategy-level auto-allocation (shift allocation toward winners)
3. Monitor newly-enabled strategies (ORB, turtle, measured_move)
4. Add more trading symbols (SOL, AVAX, DOGE, ARB)
5. LP Phase 5: IL hedging via perp autobot
