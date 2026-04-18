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

## Multi-Wallet Evolution Protocol (MANDATORY)
This is a multi-wallet evolution system. Active wallets: `paper_perp` (v1 Full Send, YOLO 5), `paper_perp_v2` (v2 Conservative, YOLO 2), `paper_perp_v3` (v3 Human Heuristics — planned), `prod_perp` (live, paused until cutover). Each wallet runs the same market data through different configs to A/B-test strategies.

**Before modifying any trading-logic file** (`auto_trader.py`, `performance_tracker.py`, sizing, conviction, risk filters, regime logic): MUST confirm with the user which wallet(s) the change applies to. Use per-wallet feature flags in `wallet.config` to gate behavior changes. NEVER change trading logic globally in a way that affects all wallets unless explicitly authorized.

**On session start:** Query `wp_wallets` (via Supabase MCP or `GET /wallets/summary`) to surface active wallet list + their configs. Don't assume "paper_perp" is the only wallet.

**Naming convention for experiment wallets:** `paper_perp_v{N}` where N = generation. Each child wallet must set `parent_wallet_id`, `generation`, `display_name`, and `description` (1-paragraph thesis) on creation.

<!-- GitNexus rules: see master ~/projects/CLAUDE.md → "GitNexus Workflow" section. Per-project index name is the project folder name. -->
