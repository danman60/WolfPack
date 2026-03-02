# WolfPack

Personal crypto trading & intelligence platform.

## Architecture

```
app/          Next.js 15 frontend (Vercel)
intel/        Python intelligence service (Railway/Fly)
supabase/     Database migrations & types
```

## Exchanges

- **Hyperliquid** — Perpetual futures
- **dYdX** — Perpetual futures
- **Uniswap V3** — Liquidity pool management

## Intelligence Agents

| Agent | Role |
|-------|------|
| The Quant | Technical analysis, regime detection, quantitative signals |
| The Snoop | Social sentiment, news, narrative tracking |
| The Sage | Forecasting, correlation analysis, weekly outlook |
| The Brief | Synthesis, trade recommendations, portfolio decisions |

## Quick Start

```bash
# Frontend
cd app && npm install && npm run dev

# Intel service
cd intel && pip install -e . && uvicorn wolfpack.api:app --reload
```
