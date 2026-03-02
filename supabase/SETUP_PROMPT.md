# Supabase Schema Setup — WolfPack

## Context

You are setting up the database schema for **WolfPack**, a personal crypto trading & intelligence platform. This is a fresh Supabase project that needs the initial schema created.

The platform has:
- **Multi-exchange support** (Hyperliquid + dYdX perpetual futures)
- **4 LLM intelligence agents** (Quant, Snoop, Sage, Brief) that produce analysis
- **8 quantitative modules** that feed signals into agents
- **Trade recommendations** with approve/reject workflow
- **LP pool tracking** for Uniswap V3 positions
- **Circuit breaker safety system**

## Instructions

1. Run the SQL migration below using `supabase:execute_sql` (or the SQL editor)
2. Verify all 7 tables were created
3. Verify all indexes were created
4. Return the Supabase project URL and anon key so I can configure the app

## SQL Migration

```sql
-- WolfPack Initial Schema
-- Multi-exchange crypto intelligence & trading platform

-- Exchange configuration per user session
CREATE TABLE IF NOT EXISTS exchange_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id TEXT NOT NULL CHECK (exchange_id IN ('hyperliquid', 'dydx')),
    wallet_address TEXT,
    api_key_encrypted TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Intelligence agent outputs
CREATE TABLE IF NOT EXISTS agent_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL CHECK (agent_name IN ('quant', 'snoop', 'sage', 'brief')),
    exchange_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    signals JSONB NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_outputs_agent ON agent_outputs (agent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_outputs_exchange ON agent_outputs (exchange_id, created_at DESC);

-- Quantitative module outputs
CREATE TABLE IF NOT EXISTS module_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_name TEXT NOT NULL,
    exchange_id TEXT NOT NULL,
    symbol TEXT,
    output JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_module_outputs_module ON module_outputs (module_name, created_at DESC);

-- Trade recommendations (from The Brief agent)
CREATE TABLE IF NOT EXISTS trade_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    conviction INTEGER NOT NULL CHECK (conviction BETWEEN 0 AND 100),
    entry_price REAL,
    stop_loss REAL,
    take_profit REAL,
    size_pct REAL,
    rationale TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'expired')),
    agent_output_id UUID REFERENCES agent_outputs(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_recommendations_status ON trade_recommendations (status, created_at DESC);

-- Portfolio snapshots (periodic equity tracking)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id TEXT NOT NULL,
    equity REAL NOT NULL,
    free_collateral REAL,
    unrealized_pnl REAL,
    realized_pnl REAL,
    positions JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_portfolio_exchange ON portfolio_snapshots (exchange_id, created_at DESC);

-- LP pool positions (Uniswap V3)
CREATE TABLE IF NOT EXISTS lp_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id TEXT NOT NULL UNIQUE,
    pool_address TEXT NOT NULL,
    token0 TEXT NOT NULL,
    token1 TEXT NOT NULL,
    fee_tier INTEGER NOT NULL,
    tick_lower INTEGER NOT NULL,
    tick_upper INTEGER NOT NULL,
    liquidity TEXT NOT NULL,
    initial_value_usd REAL,
    current_value_usd REAL,
    fees_earned_usd REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed', 'out_of_range')),
    wallet_address TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lp_wallet ON lp_positions (wallet_address, status);

-- Circuit breaker state
CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state TEXT NOT NULL CHECK (state IN ('green', 'yellow', 'red')),
    triggers JSONB NOT NULL DEFAULT '[]',
    max_exposure_pct REAL NOT NULL,
    peak_equity REAL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER exchange_configs_updated_at
    BEFORE UPDATE ON exchange_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER lp_positions_updated_at
    BEFORE UPDATE ON lp_positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

## Verification

After running, confirm these 7 tables exist:
- `exchange_configs`
- `agent_outputs`
- `module_outputs`
- `trade_recommendations`
- `portfolio_snapshots`
- `lp_positions`
- `circuit_breaker_state`

And these indexes:
- `idx_agent_outputs_agent`
- `idx_agent_outputs_exchange`
- `idx_module_outputs_module`
- `idx_recommendations_status`
- `idx_portfolio_exchange`
- `idx_lp_wallet`

Run this verification query:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

## After Setup

Return the following so I can configure the apps:
1. **Supabase Project URL** (e.g., `https://xxxxx.supabase.co`)
2. **Anon Key** (public, safe for frontend)
3. **Service Role Key** (for the Python backend — keep secret)

These go into:
- `app/.env` → `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `intel/.env` → `SUPABASE_URL` and `SUPABASE_KEY` (service role)
