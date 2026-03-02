# WolfPack Project Configuration

## Project Context
- Personal crypto trading & intelligence platform
- Monorepo: app/ (Next.js 15) + intel/ (Python FastAPI) + supabase/ (migrations)
- Exchanges: Hyperliquid + dYdX perpetual futures + Uniswap V3 LP
- Exchange toggle allows runtime switching between Hyperliquid and dYdX

## Architecture
- Frontend: Next.js 15, React 19, Tailwind v4, wagmi, viem, recharts
- Backend: Python FastAPI intelligence service
- Database: Supabase (PostgreSQL)
- LLM providers: Claude, DeepSeek, OpenRouter

## Intelligence System
- 4 LLM agents: Quant, Snoop, Sage, Brief
- 8 quantitative modules: regime, liquidity, funding, correlation, volatility, circuit_breaker, execution, backtest
- Agents consume module outputs + raw data, produce structured analysis
- The Brief synthesizes all agents into trade recommendations

## Key Patterns
- Exchange adapter pattern: both frontend (TypeScript) and backend (Python) implement unified interfaces
- ExchangeProvider context for React — useExchange() hook for active exchange
- Python exchange adapters in wolfpack/exchanges/ — factory via get_exchange()
- Agent outputs stored in Supabase agent_outputs table
- Trade recommendations require manual approval before execution

## Development
- Frontend: cd app && npm run dev
- Intel service: cd intel && uvicorn wolfpack.api:app --reload
- DB migrations: supabase/migrations/
