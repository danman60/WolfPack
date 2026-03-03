# Current Work - WolfPack

## Active Task
Intelligence quality fixes — completed all 8 file changes.

## Recent Changes (This Session)
- **config.py** — Added `deepseek_model` and `deepseek_reasoner_model` settings
- **api.py:815** — Pass liquidity, volatility, funding, correlation to Brief agent
- **api.py:855** — Raise conviction filter from 40 to 55
- **base.py** — Added `model_override` property, dynamic model selection, `_call_deepseek_reasoner` method for R1, markdown code-fence stripping in `_parse_llm_json`
- **quant.py** — Override `model_override` to use deepseek-reasoner (R1), anti-markdown prompt
- **brief.py** — Add handlers for liquidity/volatility/funding/correlation data, hard gates in system prompt (liquidity/funding/vol), anti-markdown prompt
- **snoop.py** — Anti-markdown prompt instruction
- **sage.py** — Anti-markdown prompt instruction
- **.env.example** — Added DEEPSEEK_MODEL and DEEPSEEK_REASONER_MODEL

## Next Steps
1. Deploy to VPS: git push, ssh, git pull, restart uvicorn
2. Run intelligence from frontend, verify quality improvements
3. Check Supabase for clean JSON and conviction >= 55 filter
