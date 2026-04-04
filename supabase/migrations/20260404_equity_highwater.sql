-- Peak equity tracking & drawdown monitor
-- Phase 1 of NoFx pattern integration

CREATE TABLE IF NOT EXISTS wp_equity_highwater (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id text NOT NULL,
    peak_equity numeric NOT NULL,
    peak_timestamp timestamptz NOT NULL,
    current_equity numeric,
    current_drawdown_pct numeric,
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT wp_equity_highwater_exchange_id_key UNIQUE (exchange_id)
);

-- Index for quick lookups by exchange
CREATE INDEX IF NOT EXISTS idx_equity_highwater_exchange ON wp_equity_highwater (exchange_id);
