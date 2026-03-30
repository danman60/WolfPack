# Current Work - WolfPack

## Last Session Summary
Fixed multiple critical bugs in the Telegram bot's LLM chat handler (400 errors, deadlock, Future serialization), fixed auto-trader equity/snapshot issues, added training data export pipeline for LLM distillation, and standardized portfolio naming across the system (Actual/Paper/AutoBot).

## What Changed
- `f3b942e` fix: auto-trader respects configured equity when snapshot is stale (auto_trader.py)
- `4fa8352` feat: automated training data export for LLM distillation (export_training_data.py + api.py integration)
- `b3672f3` fix: bot 400 errors — tool message format and DeepSeek model name (llm_client.py)
- `c208dec` fix: bot tool executor returning Future instead of value (bot_tools.py)
- `924ddeb` fix: bot deadlock — sync requests to self on single-worker uvicorn (bot_tools.py async conversion)
- `11c7862` feat: consistent portfolio naming — Actual/Paper/AutoBot (api.py, auto_trader.py, bot_prompt.py, bot_tools.py)
- `1854199` fix: auto-trader snapshot serialization — datetime not JSON serializable (auto_trader.py)
- [uncommitted] .gitignore, AGENTS.md, CLAUDE.md, telegram_bot.py, bot_memory.py, bot_permissions.py

## Build Status
NOT RUN — no frontend build this session. Backend deployed to droplet via git pull + systemctl restart.

## Known Bugs & Issues
- Auto-trader only executes 1 trade per symbol (paper engine blocks duplicates at paper_trading.py:73-77)
- Health check endpoint (/health/deep) shows "never run" after restart — in-memory state only
- Circuit breaker state check constraint error in DB: "ACTIVE" rejected by wp_circuit_breaker_state_state_check
- Conviction threshold 55 (YOLO level 4) means many recs at exactly 55 are borderline

## Incomplete Work
- Training data export: backfill done (324 examples), real-time append integrated but not yet verified post-deploy
- Distillation pipeline: export script done, fine-tuning step not built yet (Unsloth/PEFT on FIRMAMENT)
- NVIDIA cufolio portfolio optimization: researched (github.com/NVIDIA-AI-Blueprints/quantitative-portfolio-optimization), not integrated
- KX distillation pipeline: researched (github.com/KxSystems/nvidia-kx-samples), architecture informed our export script

## Tests
- No automated tests run this session
- Bot manually tested via Telegram — "Portfolio?" returns correct data with Paper/AutoBot labels

## Next Steps (priority order)
1. Verify training data appending on each cycle: `ssh droplet "ls -la /root/WolfPack/intel/training_data/"`
2. Build LoRA fine-tuning script for distilling Brief agent to small model on FIRMAMENT
3. Fix circuit breaker DB check constraint (ACTIVE value rejected)
4. Consider merging Paper + AutoBot into single portfolio or unified view
5. Add Hyperliquid private key for live trading when ready

## Gotchas for Next Session
- Droplet SSH: `ssh droplet` (key: id_ed25519_spyballoon, root@159.89.115.95)
- Bot files (bot_memory.py, bot_permissions.py, bot_prompt.py, bot_tools.py, llm_client.py) were untracked on droplet — had to `rm` before `git pull`
- Bot memory at `~/.wolfpack-bot/bot_memory.json` on droplet — cleared this session. Stale tool_calls cause 400s.
- systemd service `wolfpack-intel` is now enabled with Restart=always
- Auto-trader equity was stuck at $5K, fixed to $25K. Snapshot restore logic patched.
- Three portfolios: Actual (Hyperliquid read-only), Paper ($10K manual), AutoBot ($25K autonomous YOLO 4)

## Files Touched This Session
- intel/wolfpack/auto_trader.py (equity restore, snapshot serialization, type field)
- intel/wolfpack/export_training_data.py (NEW — training data export pipeline)
- intel/wolfpack/llm_client.py (tool message format, DeepSeek model name)
- intel/wolfpack/bot_tools.py (async conversion, tool descriptions)
- intel/wolfpack/bot_prompt.py (system prompt with portfolio types)
- intel/wolfpack/api.py (training data integration, portfolio type fields)
