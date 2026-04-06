# Current Work - WolfPack

## Last Session Summary (2026-04-06)
Massive session: unified hourly digest, dynamic strategy allocation, LP persistence, background tick loop, mobile profit report, LP Autobot dashboard, full mobile polish, and complete live money cutover infrastructure.

## What Changed (8 commits this session)
- `6a580c9` feat: LP live engine on Arbitrum + live mode UI banner
- `f3e95b7` feat: live perp execution bridge — paper→live toggle for real money
- `990b0c1` fix: LP equity inflation on snapshot restore
- `8c0995d` fix: profit report buttons no longer snap/reload page
- `0eeeac6` feat: mobile profit report + LP dashboard + mobile polish
- `cfaccc6` fix: production-readiness — LP persistence, background tick loop, startup restore
- `c0ee82f` feat: include LP portfolio data in profit reports
- `c389931` feat: unified hourly digest + dynamic strategy allocation + IL hedging

## Build Status
DEPLOYED — intel service running on droplet (159.89.115.95), frontend on Vercel

## Live Cutover Infrastructure (COMPLETE)
- LiveTradingEngine: wraps HyperliquidTrader with PaperTradingEngine interface
- LiveLPEngine: wraps web3.py Uniswap V3 calls on Arbitrum
- Emergency kill switch: POST /emergency-kill
- Safety: $100 equity floor, 5-min trade spacing, mode enforcement
- UI: Live trading banner, mode indicator in status

## Cutover Checklist (When Ready ~2026-04-13)
1. Set HYPERLIQUID_PRIVATE_KEY in droplet .env
2. pip install web3>=7.0.0 on droplet
3. Set LP_WALLET_PRIVATE_KEY in droplet .env
4. Fund Hyperliquid account (~$500 for perps)
5. Fund Arbitrum wallet (~$500 for LP + gas)
6. POST /strategy/mode?mode=live
7. Set LP_PAPER_MODE=false in .env
8. Monitor first few trades closely

## Known Issues
- Profit report contaminated by crypto price appreciation vs actual trading alpha
- web3 not yet installed on droplet (only needed for live LP)
- Pool scanner may need tuning for Arbitrum pool discovery

## Next Steps (Priority Order)
1. Fix profit reporting — separate trading alpha from market beta
2. Monitor paper trading performance for 1 week
3. Test live cutover with small amount before full commitment
4. Install web3 on droplet when LP cutover is near
5. Tune Arbitrum pool scanner parameters
