# Current Work - WolfPack

## Last Session Summary (2026-04-06 → 2026-04-07)
Massive session: unified hourly digest, dynamic strategy allocation, LP persistence, background tick loop, mobile profit report with alpha/benchmark, LP Autobot dashboard, full mobile polish, complete live money cutover infrastructure (LiveTradingEngine + LiveLPEngine), realistic paper trading friction model, 7-point production hardening, and deep 10-improvement analysis.

## What Changed (14 commits this session)
- `e35e8a7` fix: 7-point production hardening for live money readiness
- `c8cf787` fix: harden against silent cycle failures
- `8483232` feat: realistic market friction in paper trading engine
- `1c21022` fix: benchmark query uses ISO timestamp
- `5613e65` fix: add logger to bot_tools for benchmark debugging
- `0ffb23a` fix: benchmark uses requests fallback when httpx unavailable
- `5a8067c` feat: benchmark-adjusted P&L — show alpha vs buy-and-hold
- `6a580c9` feat: LP live engine on Arbitrum + live mode UI banner
- `f3e95b7` feat: live perp execution bridge — paper→live toggle
- `990b0c1` fix: LP equity inflation on snapshot restore
- `8c0995d` fix: profit report buttons no longer snap/reload page
- `0eeeac6` feat: mobile profit report + LP dashboard + mobile polish
- `cfaccc6` fix: production-readiness — LP persistence, background tick loop
- `c389931` feat: unified hourly digest + dynamic strategy allocation + IL hedging

## Build Status
DEPLOYED — intel service running on droplet (159.89.115.95), frontend on Vercel

## Live Cutover Infrastructure (COMPLETE)
- LiveTradingEngine: wraps HyperliquidTrader with PaperTradingEngine interface
- LiveLPEngine: wraps web3.py Uniswap V3 calls on Arbitrum
- Emergency kill switch: POST /emergency-kill
- Safety: $100 equity floor, 5-min trade spacing, mode enforcement
- Position reconciliation: compares internal vs exchange each cycle
- Stop order placement: SL/TP now placed on exchange (was dead code, fixed)
- Concurrent cycle lock: asyncio.Lock prevents overlapping cycles
- Auth on all write endpoints
- External health ping cron on SpyBalloon
- Systemd: Restart=always, MemoryMax=1G

## Cutover Checklist (When Ready ~2026-04-13)
1. Set HYPERLIQUID_PRIVATE_KEY in droplet .env
2. pip install web3>=7.0.0 on droplet
3. Set LP_WALLET_PRIVATE_KEY in droplet .env
4. Fund Hyperliquid account (~$500 for perps)
5. Fund Arbitrum wallet (~$500 for LP + gas)
6. POST /strategy/mode?mode=live
7. Set LP_PAPER_MODE=false in .env
8. Monitor first few trades closely

## Paper Trading Friction Model (NEW)
- Entry/exit slippage: 3-12 bps (symbol-specific)
- Stop-loss slippage: 15 bps extra
- Funding rate: 0.005%/hr deducted per tick
- Fill delay: 300s guard before stop checks

## 10 Improvements Pitch (docs/plans/2026-04-06-10-improvements.md)
Data-driven analysis of 122 trades. Key findings:
- Shorts 27.8x more profitable than longs
- Mean reversion = 97.2% of all profit
- Hours 0-9 UTC = 90.7% of profit
- $3-5K position size = 68.5% of profit
- Regime momentum strategy is noise (46 trades, $21 total)

### Priority improvements:
1. Trading hours restriction (0-12 UTC only)
2. Short-only mode in ranging regime
3. Kill regime_momentum strategy
4. Target $3-5K position sizing
5. LLM fallback chain (DeepSeek → OpenRouter → Claude)
6. Recommendation-to-trade attribution
7. Equity curve on dashboard
8. Circuit breaker status badge
9. Persistent notification buffer
10. Response caching

## Regime Transition Engine (PLANNED, NOT BUILT)
- Auto-close wrong-regime positions on confirmed shift
- Tighten stops during transition
- Activate vol_breakout at 5%
- 2-tick cooldown on new entries after regime change

## Known Issues
- LP pool monitor hardcoded to Ethereum mainnet addresses (needs Arbitrum pools)
- web3 not installed on droplet (only needed for live LP)
- 342 recommendations with only 3 executed (pipeline bottleneck)
- No LLM fallback (DeepSeek only)

## Next Steps (Priority Order)
1. Execute the 10 improvements (user reviewing pitch)
2. Build regime transition engine
3. Monitor paper trading for 1 week with friction model
4. Test live cutover with small amount
