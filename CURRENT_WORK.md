# Current Work - WolfPack

## Active Task
Phase 5 complete — Telegram bot, auto-trading, pool screening, intelligence improvements.

## Recent Changes (This Session)
- Few-shot calibration examples added to all 4 agents (Quant, Snoop, Sage, Brief)
- BriefVeto class: post-Brief filtering with hard veto + soft conviction adjustments
- Deep health check: GET /health/deep (data freshness, API keys, CB state, last run)
- Backtest graduation criteria: GraduationCriteria dataclass + GET /backtest/runs/{id}/graduation
- Telegram bot: two-way with /status, /intel, /portfolio, inline Approve/Reject buttons
- Auto-trader: separate $5K paper bucket, conviction threshold 75, hooks into intel cycle
- Pool screening: PoolParty scoring algorithm ported, GET /pools/screen, Score column in frontend
- Supabase migration: wp_auto_trades + wp_auto_portfolio_snapshots tables

## Files Changed
- `intel/wolfpack/agents/quant.py` — few-shot examples
- `intel/wolfpack/agents/snoop.py` — few-shot examples
- `intel/wolfpack/agents/sage.py` — few-shot examples
- `intel/wolfpack/agents/brief.py` — few-shot examples
- `intel/wolfpack/veto.py` — NEW, BriefVeto class
- `intel/wolfpack/telegram_bot.py` — NEW, WolfPackBot class
- `intel/wolfpack/auto_trader.py` — NEW, AutoTrader class
- `intel/wolfpack/modules/pool_screening.py` — NEW, pool scoring
- `intel/wolfpack/modules/backtest.py` — graduation criteria
- `intel/wolfpack/api.py` — deep health, graduation endpoint, telegram lifespan, veto wiring, auto-trader endpoints, pool screening endpoint
- `intel/wolfpack/notifications.py` — inline button support via bot singleton
- `intel/wolfpack/config.py` — auto_trade_*, subgraph_api_key settings
- `intel/pyproject.toml` — python-telegram-bot dependency
- `app/src/app/pools/page.tsx` — Score column with color-coded recommendation badge
- `app/src/lib/hooks/usePools.ts` — usePoolScreening hook
- `app/src/app/page.tsx` — auto-trader equity stat card
- `app/src/lib/hooks/useIntelligence.ts` — useAutoTraderStatus, useToggleAutoTrader hooks

## Next Steps
1. Deploy to VPS: `cd /root/WolfPack && git pull && pip install python-telegram-bot && kill uvicorn && restart`
2. Set TELEGRAM_BOT_TOKEN in VPS .env (user has token from BotFather)
3. Test: /status command in Telegram, run intel, verify inline buttons
4. Test auto-trader: POST /auto-trader/toggle, run intel with high-conviction rec
5. Test pool screening: GET /pools/screen (needs SUBGRAPH_API_KEY)
6. Register for Reown project ID (WalletConnect)
