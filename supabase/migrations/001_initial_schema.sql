-- WolfPack Initial Schema (wp_ prefix)
-- Multi-exchange crypto intelligence & trading platform
-- Deployed to CCandSS Supabase project

-- Exchange configuration per user session
CREATE TABLE IF NOT EXISTS wp_exchange_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id TEXT NOT NULL CHECK (exchange_id IN ('hyperliquid', 'dydx')),
    wallet_address TEXT,
    api_key_encrypted TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Intelligence agent outputs
CREATE TABLE IF NOT EXISTS wp_agent_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL CHECK (agent_name IN ('quant', 'snoop', 'sage', 'brief')),
    exchange_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    signals JSONB NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_wp_agent_outputs_agent ON wp_agent_outputs (agent_name, created_at DESC);
CREATE INDEX idx_wp_agent_outputs_exchange ON wp_agent_outputs (exchange_id, created_at DESC);

-- Quantitative module outputs
CREATE TABLE IF NOT EXISTS wp_module_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_name TEXT NOT NULL,
    exchange_id TEXT NOT NULL,
    symbol TEXT,
    output JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_wp_module_outputs_module ON wp_module_outputs (module_name, created_at DESC);

-- Trade recommendations (from The Brief agent)
CREATE TABLE IF NOT EXISTS wp_trade_recommendations (
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
    agent_output_id UUID REFERENCES wp_agent_outputs(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_wp_recommendations_status ON wp_trade_recommendations (status, created_at DESC);

-- Portfolio snapshots (periodic equity tracking)
CREATE TABLE IF NOT EXISTS wp_portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id TEXT NOT NULL,
    equity REAL NOT NULL,
    free_collateral REAL,
    unrealized_pnl REAL,
    realized_pnl REAL,
    positions JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_wp_portfolio_exchange ON wp_portfolio_snapshots (exchange_id, created_at DESC);

-- LP pool positions (Uniswap V3)
CREATE TABLE IF NOT EXISTS wp_lp_positions (
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

CREATE INDEX idx_wp_lp_wallet ON wp_lp_positions (wallet_address, status);

-- Circuit breaker state
CREATE TABLE IF NOT EXISTS wp_circuit_breaker_state (
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

CREATE TRIGGER wp_exchange_configs_updated_at
    BEFORE UPDATE ON wp_exchange_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER wp_lp_positions_updated_at
    BEFORE UPDATE ON wp_lp_positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
