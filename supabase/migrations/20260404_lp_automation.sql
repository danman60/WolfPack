-- LP Automation Phase 1 — Paper engine + monitor + events
-- Extends wp_lp_positions with automation tracking columns and adds snapshot/event tables

-- Extend wp_lp_positions with automation columns
ALTER TABLE wp_lp_positions ADD COLUMN IF NOT EXISTS entry_price_ratio REAL;
ALTER TABLE wp_lp_positions ADD COLUMN IF NOT EXISTS il_pct REAL DEFAULT 0;
ALTER TABLE wp_lp_positions ADD COLUMN IF NOT EXISTS out_of_range_ticks INTEGER DEFAULT 0;
ALTER TABLE wp_lp_positions ADD COLUMN IF NOT EXISTS last_fee_harvest_at TIMESTAMPTZ;
ALTER TABLE wp_lp_positions ADD COLUMN IF NOT EXISTS total_fees_token0 REAL DEFAULT 0;
ALTER TABLE wp_lp_positions ADD COLUMN IF NOT EXISTS total_fees_token1 REAL DEFAULT 0;
ALTER TABLE wp_lp_positions ADD COLUMN IF NOT EXISTS rebalance_count INTEGER DEFAULT 0;
ALTER TABLE wp_lp_positions ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'paper' CHECK (source IN ('manual', 'auto', 'paper'));

-- LP portfolio snapshots (mirrors wp_auto_portfolio_snapshots)
CREATE TABLE IF NOT EXISTS wp_lp_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    total_value_usd REAL NOT NULL,
    total_fees_usd REAL NOT NULL,
    total_il_usd REAL NOT NULL,
    positions JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wp_lp_snapshots_created ON wp_lp_snapshots (created_at DESC);

-- LP events log (rebalance, harvest, range change, alerts)
CREATE TABLE IF NOT EXISTS wp_lp_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID,
    event_type TEXT NOT NULL CHECK (event_type IN ('out_of_range', 'back_in_range', 'rebalance', 'fee_harvest', 'range_change', 'opened', 'closed', 'il_warning')),
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wp_lp_events_position ON wp_lp_events (position_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wp_lp_events_type ON wp_lp_events (event_type, created_at DESC);

-- Add updated_at trigger for wp_lp_snapshots if not exists
DO $$ BEGIN
    CREATE TRIGGER wp_lp_snapshots_updated_at
        BEFORE UPDATE ON wp_lp_snapshots
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
