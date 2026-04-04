# Current Work - WolfPack

## Last Session Summary
Massive trading infrastructure session. Fixed intel service (DeepSeek outage), overhauled auto-trader (pyramiding, sizing, stops), built regime-routed strategy architecture with 3 new strategies, added performance self-adjustment, fee simulation, and notification digest. AutoBot equity went from $25,014 → $25,461 (+$447 realized PnL).

## What Changed (13 commits this session)
- `a4a5f6c` fix: force English in bot prompt (DeepSeek Chinese responses)
- `935c186` feat: auto-trader overhaul — pyramiding (3 per symbol), 15% base sizing, softer veto at YOLO 4+, snapshot persistence for SL/TP
- `d297816` feat: wire strategy signals + stop checking into intel cycle
- `1769ec5` fix: backtest fallback to direct exchange fetch when cache empty
- `5502717` fix: optimize DB writes — upsert agent/module outputs, fix CB constraint
- `ca84707` feat: regime-routed strategy architecture — multi-TF regime (1h+4h+daily), regime_router.py, Turtle/Donchian, Measured Move, Mean Reversion strategies, Anti-SRS filter on ORB, HTF trailing stops, Brief as conviction multiplier
- `b506f29` fix: suppress Telegram approval buttons when autobot enabled
- `2f2e440` fix: raise mean reversion threshold from 2.0 to 3.0 ATR (was overtrading)
- `a8006dc` feat: performance tracker + fee simulation — self-adjusting conviction/sizing based on rolling scorecard
- `27facd2` feat: notification digest — configurable individual/hourly/daily/disabled

## Build Status
NOT RUN — no frontend build. Backend deployed to droplet via git pull + systemctl restart. Service is active and running.

## Known Bugs & Issues
- `[training] Failed to append training data: name 'os' is not defined` — missing import in export_training_data.py on droplet
- Measured Move strategy produces zero signals on 5m candles — likely timestamp parsing bug in session open detection
- Turtle/Donchian produced zero signals on 4h over 30 days — needs longer evaluation period (by design)
- Mean reversion at 3.0 ATR still net negative (-0.74% BTC) — only viable with regime gating (RANGING only)
- Notification digest mode resets to "individual" on service restart — needs DB persistence
- All `wp_auto_trades` show `status=open` — trades never get marked as closed in this table

## What Works (Proven by Data)
- **EMA crossover**: +2.31% BTC, +3.25% ETH over 30 days, Sharpe 5+ — the only backtested strategy with proven edge
- **Brief agent shorts**: 36% WR but 3.5:1 R:R on BTC shorts = $2,068 profit (77% of total)
- **Pyramiding**: Successfully opened 3rd BTC position on first cycle after upgrade
- **Performance tracker**: Grades BTC longs as UNDERPERFORMING (raises threshold to 70), BTC shorts as STRONG (lowers to 45)
- **Fee simulation**: 5 bps deducted on open/close, total_fees tracked in portfolio

## Trade History Analysis (422 trades, March 13 — April 4)
- Gross profit: $9,385 | Gross loss: -$6,697 | Net: +$2,688
- Winners: 139 (33%) | Losers: 254 | Avg win: $67.51 | Avg loss: -$26.36
- Best: BTC short (+$2,068), ETH short (+$713), ETH long (+$241)
- Worst: BTC long (-$466) — 145 trades, 28% WR, net negative
- After estimated fees (~$700 taker): ~$1,988 net

## Research Phase
- 35 trading videos transcribed (Tom Hougaard, QuantJason, others) → `docs/transcripts/`
- Transcript analysis complete → `docs/research/transcript-analysis.md`
- 5 strategy specs written → `docs/research/strategy-specs/`
- Pipeline research task (R1-R7) was running but hit ollama timeouts — data-driven research still pending
- Trader Tom ORB strategy doc → `docs/plans/2026-04-02-trader-tom-orb-strategy.md`

## Architecture State
- **Regime Router**: Routes strategies by TRENDING/RANGING/VOLATILE using multi-TF regime (1h+4h+daily)
- **7 Strategies registered**: ema_crossover, turtle_donchian, regime_momentum, mean_reversion, measured_move, orb_session, vol_breakout
- **Performance Tracker**: Dynamic conviction thresholds + sizing multipliers per symbol/direction
- **Notification Digest**: Currently set to hourly mode, 240-minute interval
- **Brief Multiplier**: 1.0x when mechanical+Brief agree, 0.25x Brief-only

## AutoBot Status (last checked)
- Equity: $25,461 | Realized PnL: $460.96 | YOLO level 4
- 0 open positions (previous positions closed profitably)
- Fee tracking active (5 bps per side)

## Droplet Status
- Disk: 56% (11G free after journal vacuum + n8n-mcp stopped)
- RAM: 960MB total, ~600MB used, swapping 615MB
- n8n-mcp stopped and disabled (data preserved at /root/n8n_data_recovered/)

## Next Steps (priority order)
1. **Persist notification digest mode** to DB so it survives restarts
2. **Debug Measured Move zero signals** — check 5m candle timestamp parsing against session open detection
3. **Complete R1-R7 research** — agent accuracy analysis, funding carry backtest, EMA optimization, stat arb validation (pipeline task hit ollama timeouts, needs Claude or manual execution)
4. **Monitor autobot for 1 week** with current setup — collect real performance data before adding more strategies
5. **Fix training data export** — missing `import os` in export_training_data.py
6. **LLM provider fallback chain** — DeepSeek → Anthropic → alert (prevents repeat of 55-hour outage)
7. **Consider upgrading droplet** — 1GB RAM with swap is tight for the expanded workload

## Gotchas for Next Session
- Droplet SSH: `ssh droplet` (root@159.89.115.95)
- API auth: Bearer `1bee9d8d628c2d392da4c52d3e22bd1c93d3c7b5ba5be0833590594402a3b43b`
- Notification digest is set to hourly/240min but resets on restart
- Performance tracker refreshes every 5 min from wp_trade_history
- Regime detector already supports multi-TF — just pass dict of candle lists
- CB constraint fixed (ACTIVE now accepted) via Supabase SQL migration
- wp_agent_outputs and wp_module_outputs now upsert (single row per agent/module, not append)

## Files Touched This Session
- intel/wolfpack/api.py (cycle wiring, backtest fallback, notification suppression, digest flush, perf injection)
- intel/wolfpack/auto_trader.py (pyramiding, sizing, strategy allocations, regime routing, HTF trailing, perf tracker, digest)
- intel/wolfpack/paper_trading.py (pyramiding, snapshot persistence, fee simulation)
- intel/wolfpack/veto.py (soft stop_loss at YOLO 4+)
- intel/wolfpack/bot_prompt.py (English language instruction)
- intel/wolfpack/db.py (upsert agent/module outputs, CB fix, snapshot cleanup)
- intel/wolfpack/agents/brief.py (performance summary injection)
- intel/wolfpack/strategies/__init__.py (register 3 new strategies)
- intel/wolfpack/strategies/regime_router.py (NEW — regime→strategy dispatcher)
- intel/wolfpack/strategies/turtle_donchian.py (NEW — Donchian breakout)
- intel/wolfpack/strategies/measured_move.py (NEW — opening range measured move)
- intel/wolfpack/strategies/mean_reversion.py (NEW — regime-gated mean reversion)
- intel/wolfpack/strategies/orb_session.py (Anti-SRS overnight range filter)
- intel/wolfpack/performance_tracker.py (NEW — rolling scorecard, dynamic thresholds)
- intel/wolfpack/notification_digest.py (NEW — batched notification system)
- intel/wolfpack/modules/sizing.py (unchanged but analyzed)
- docs/plans/2026-04-02-trader-tom-orb-strategy.md (NEW — Trader Tom research)
- docs/research/transcript-analysis.md (NEW — 39 transcript analysis)
- docs/research/strategy-specs/*.md (NEW — 5 strategy specs)
- app/src/app/auto-bot/page.tsx (notification settings UI)
