-- WolfPack 4-Wallet Architecture Consolidation
-- Phase: Wave 1 of 6 — DATABASE ONLY
-- Purpose: Consolidate scattered wallet identity into exactly 4 wallets:
--   paper_perp, prod_perp, paper_lp, prod_lp
-- 
-- This migration:
-- 1. Creates wp_wallets registry table
-- 2. Adds wallet_id to existing tables
-- 3. Formalizes ad-hoc tables
-- 4. Enriches wp_trade_history and wp_portfolio_snapshots
-- 5. Creates cutover/promotion tables
-- 6. Backfills wallet_id on existing data
-- 7. Creates indexes
-- 8. Adds updated_at trigger to wp_wallets

-- =============================================================================
-- 1. CREATE wp_wallets REGISTRY TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS wp_wallets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    wallet_mode TEXT NOT NULL CHECK (wallet_mode IN ('paper', 'production')),
    wallet_type TEXT NOT NULL CHECK (wallet_type IN ('perp', 'lp')),
    starting_equity NUMERIC NOT NULL,
    current_equity NUMERIC NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'cutover_pending')),
    config JSONB NOT NULL DEFAULT '{}',
    cutover_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Seed 4 wallets
INSERT INTO wp_wallets (name, wallet_mode, wallet_type, starting_equity, current_equity, status)
VALUES 
    ('paper_perp', 'paper', 'perp', 10000, 10000, 'active'),
    ('prod_perp', 'production', 'perp', 1000, 1000, 'paused'),
    ('paper_lp', 'paper', 'lp', 25000, 25000, 'active'),
    ('prod_lp', 'production', 'lp', 0, 0, 'paused')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- 2. ADD wallet_id TO EXISTING TABLES
-- =============================================================================

-- wp_portfolio_snapshots
ALTER TABLE wp_portfolio_snapshots 
    ADD COLUMN IF NOT EXISTS wallet_id UUID REFERENCES wp_wallets(id);

-- wp_lp_snapshots
ALTER TABLE wp_lp_snapshots 
    ADD COLUMN IF NOT EXISTS wallet_id UUID REFERENCES wp_wallets(id);

-- wp_lp_events
ALTER TABLE wp_lp_events 
    ADD COLUMN IF NOT EXISTS wallet_id UUID REFERENCES wp_wallets(id);

-- wp_equity_highwater
ALTER TABLE wp_equity_highwater 
    ADD COLUMN IF NOT EXISTS wallet_id UUID REFERENCES wp_wallets(id);

-- wp_circuit_breaker_state
ALTER TABLE wp_circuit_breaker_state 
    ADD COLUMN IF NOT EXISTS wallet_id UUID REFERENCES wp_wallets(id);

-- =============================================================================
-- 3. FORMALIZE AD-HOC TABLES
-- =============================================================================

-- wp_auto_trades: Tracks live/paper trades from recommendations
CREATE TABLE IF NOT EXISTS wp_auto_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id TEXT,
    wallet_id UUID REFERENCES wp_wallets(id),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    entry_price REAL NOT NULL,
    size_usd REAL NOT NULL,
    size_pct REAL NOT NULL,
    conviction INTEGER NOT NULL CHECK (conviction BETWEEN 0 AND 100),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'cancelled')),
    strategy TEXT,
    source TEXT CHECK (source IN ('manual', 'live', 'backtest')),
    pnl_usd REAL,
    stop_loss REAL,
    take_profit REAL,
    opened_at TIMESTAMPTZ DEFAULT now(),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- wp_auto_portfolio_snapshots: Periodic portfolio state (pre-consolidation)
CREATE TABLE IF NOT EXISTS wp_auto_portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID REFERENCES wp_wallets(id),
    equity REAL NOT NULL,
    free_collateral REAL,
    unrealized_pnl REAL,
    realized_pnl REAL,
    positions JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- wp_trade_history: Closed trades with full P&L attribution
CREATE TABLE IF NOT EXISTS wp_trade_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id TEXT UNIQUE,
    wallet_id UUID REFERENCES wp_wallets(id),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    entry_price REAL NOT NULL,
    exit_price REAL,
    size_usd REAL NOT NULL,
    pnl_usd REAL,
    source TEXT CHECK (source IN ('manual', 'live', 'backtest')),
    strategy TEXT,
    opened_at TIMESTAMPTZ DEFAULT now(),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- wp_position_actions: Log of position management actions
CREATE TABLE IF NOT EXISTS wp_position_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID REFERENCES wp_wallets(id),
    action TEXT NOT NULL,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
    acted_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- wp_backtest_runs: Backtest execution tracking
CREATE TABLE IF NOT EXISTS wp_backtest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID REFERENCES wp_wallets(id),
    config JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    progress_pct INTEGER DEFAULT 0,
    metrics JSONB,
    equity_curve JSONB,
    monthly_returns JSONB,
    trade_count INTEGER,
    duration_seconds INTEGER,
    error TEXT,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- wp_backtest_trades: Individual trades from backtest runs
CREATE TABLE IF NOT EXISTS wp_backtest_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES wp_backtest_runs(id),
    wallet_id UUID REFERENCES wp_wallets(id),
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    entry_price REAL NOT NULL,
    exit_price REAL,
    size_usd REAL NOT NULL,
    pnl REAL,
    pnl_pct REAL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- wp_candle_cache: Cached OHLCV data for backtesting
CREATE TABLE IF NOT EXISTS wp_candle_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT wp_candle_cache_unique UNIQUE (exchange_id, symbol, interval, timestamp)
);

-- wp_watchlist: User-curated symbol watchlist
CREATE TABLE IF NOT EXISTS wp_watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    exchange_id TEXT NOT NULL,
    notes TEXT,
    wallet_id UUID REFERENCES wp_wallets(id),
    added_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT wp_watchlist_symbol_exchange UNIQUE (symbol, exchange_id)
);

-- =============================================================================
-- 4. ENRICH wp_trade_history WITH ADDITIONAL COLUMNS
-- =============================================================================

-- Exit attribution
ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS exit_reason TEXT 
    CHECK (exit_reason IN ('stop_loss', 'take_profit', 'trailing_stop', 'manual', 'regime_shift', 'emergency'));

-- Hold duration tracking
ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS hold_duration_seconds INTEGER;

-- Slippage tracking
ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS entry_slippage_bps REAL;

ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS exit_slippage_bps REAL;

-- Funding cost for perp positions
ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS funding_cost_usd REAL;

-- Regime tracking
ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS regime_at_entry TEXT;

ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS regime_at_exit TEXT;

-- Conviction tracking
ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS conviction_at_entry INTEGER;

-- Max favorable/adverse excursion (intraday tracking)
ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS max_favorable_excursion REAL;

ALTER TABLE wp_trade_history 
    ADD COLUMN IF NOT EXISTS max_adverse_excursion REAL;

-- =============================================================================
-- 5. ENRICH wp_portfolio_snapshots WITH ADDITIONAL COLUMNS
-- =============================================================================

-- Open position count
ALTER TABLE wp_portfolio_snapshots 
    ADD COLUMN IF NOT EXISTS open_position_count INTEGER;

-- Total exposure
ALTER TABLE wp_portfolio_snapshots 
    ADD COLUMN IF NOT EXISTS total_exposure_usd REAL;

-- Regime state at snapshot time
ALTER TABLE wp_portfolio_snapshots 
    ADD COLUMN IF NOT EXISTS regime_state TEXT;

-- =============================================================================
-- 6. CREATE CUTOVER/PROMOTION TABLES
-- =============================================================================

-- wp_cutover_checklist: Track promotion conditions from paper to prod
CREATE TABLE IF NOT EXISTS wp_cutover_checklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID REFERENCES wp_wallets(id),
    phase TEXT NOT NULL,
    check_name TEXT NOT NULL,
    passed BOOLEAN DEFAULT false,
    value JSONB,
    checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- wp_strategy_configs: Strategy configuration per wallet with promotion tracking
CREATE TABLE IF NOT EXISTS wp_strategy_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID REFERENCES wp_wallets(id),
    strategy_name TEXT NOT NULL,
    enabled BOOLEAN DEFAULT true,
    params JSONB NOT NULL DEFAULT '{}',
    promoted_from_wallet_id UUID REFERENCES wp_wallets(id),
    promoted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT wp_strategy_configs_wallet_strategy UNIQUE (wallet_id, strategy_name)
);

-- =============================================================================
-- 7. BACKFILL wallet_id ON EXISTING DATA
-- =============================================================================

-- Get wallet IDs for backfill
DO $$
DECLARE
    v_paper_perp UUID;
    v_prod_perp UUID;
    v_paper_lp UUID;
    v_prod_lp UUID;
BEGIN
    SELECT id INTO v_paper_perp FROM wp_wallets WHERE name = 'paper_perp';
    SELECT id INTO v_prod_perp FROM wp_wallets WHERE name = 'prod_perp';
    SELECT id INTO v_paper_lp FROM wp_wallets WHERE name = 'paper_lp';
    SELECT id INTO v_prod_lp FROM wp_wallets WHERE name = 'prod_lp';

    -- Backfill wp_portfolio_snapshots: all existing -> paper_perp
    UPDATE wp_portfolio_snapshots 
    SET wallet_id = v_paper_perp 
    WHERE wallet_id IS NULL;

    -- Backfill wp_trade_history: manual or null source -> paper_perp, live -> prod_perp
    UPDATE wp_trade_history 
    SET wallet_id = CASE 
        WHEN source = 'live' THEN v_prod_perp
        ELSE v_paper_perp
    END
    WHERE wallet_id IS NULL;

    -- Backfill wp_lp_snapshots: all existing -> paper_lp
    UPDATE wp_lp_snapshots 
    SET wallet_id = v_paper_lp 
    WHERE wallet_id IS NULL;

    -- Backfill wp_lp_events: all existing -> paper_lp
    UPDATE wp_lp_events 
    SET wallet_id = v_paper_lp 
    WHERE wallet_id IS NULL;

    -- Backfill wp_equity_highwater: all existing -> paper_perp
    UPDATE wp_equity_highwater 
    SET wallet_id = v_paper_perp 
    WHERE wallet_id IS NULL;

    -- Backfill wp_circuit_breaker_state: all existing -> paper_perp
    UPDATE wp_circuit_breaker_state 
    SET wallet_id = v_paper_perp 
    WHERE wallet_id IS NULL;
END $$;

-- =============================================================================
-- 8. CREATE INDEXES
-- =============================================================================

-- Index on wp_wallets for mode+type lookups
CREATE INDEX IF NOT EXISTS idx_wp_wallets_mode_type ON wp_wallets (wallet_mode, wallet_type);

-- Index on wp_portfolio_snapshots for wallet+time queries
CREATE INDEX IF NOT EXISTS idx_wp_portfolio_wallet ON wp_portfolio_snapshots (wallet_id, created_at DESC);

-- Index on wp_trade_history for wallet+close time queries
CREATE INDEX IF NOT EXISTS idx_wp_trade_history_wallet ON wp_trade_history (wallet_id, closed_at DESC);

-- Index on wp_lp_snapshots for wallet+time queries
CREATE INDEX IF NOT EXISTS idx_wp_lp_snapshots_wallet ON wp_lp_snapshots (wallet_id, created_at DESC);

-- Index on wp_strategy_configs for wallet lookups
CREATE INDEX IF NOT EXISTS idx_wp_strategy_configs_wallet ON wp_strategy_configs (wallet_id);

-- Index on wp_cutover_checklist for wallet lookups
CREATE INDEX IF NOT EXISTS idx_wp_cutover_wallet ON wp_cutover_checklist (wallet_id);

-- Additional useful indexes on new tables
CREATE INDEX IF NOT EXISTS idx_wp_auto_trades_wallet ON wp_auto_trades (wallet_id, status);
CREATE INDEX IF NOT EXISTS idx_wp_auto_trades_symbol ON wp_auto_trades (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wp_trade_history_symbol ON wp_trade_history (symbol, closed_at DESC);
CREATE INDEX IF NOT EXISTS idx_wp_backtest_runs_wallet ON wp_backtest_runs (wallet_id, status);
CREATE INDEX IF NOT EXISTS idx_wp_backtest_trades_run ON wp_backtest_trades (run_id);
CREATE INDEX IF NOT EXISTS idx_wp_candle_cache_exchange ON wp_candle_cache (exchange_id, symbol, interval, timestamp);
CREATE INDEX IF NOT EXISTS idx_wp_watchlist_exchange ON wp_watchlist (exchange_id);

-- =============================================================================
-- 9. ADD updated_at TRIGGER TO wp_wallets
-- =============================================================================

CREATE TRIGGER wp_wallets_updated_at
    BEFORE UPDATE ON wp_wallets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- END OF MIGRATION
-- =============================================================================
