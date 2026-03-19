-- Kraken exchange support + prediction performance tracking
-- Migration: 2026-03-19

CREATE TABLE IF NOT EXISTS wp_prediction_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID REFERENCES wp_trade_recommendations(id),
    agent_name TEXT NOT NULL,
    exchange_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    predicted_direction TEXT NOT NULL,
    predicted_conviction INTEGER,
    predicted_at TIMESTAMPTZ NOT NULL,
    price_at_prediction REAL,
    price_after REAL,
    check_interval_hours INTEGER DEFAULT 24,
    outcome TEXT,  -- 'correct', 'incorrect', 'neutral'
    pnl_pct REAL,
    scored_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_wp_prediction_performance_agent ON wp_prediction_performance(agent_name);
CREATE INDEX IF NOT EXISTS idx_wp_prediction_performance_exchange ON wp_prediction_performance(exchange_id);
CREATE INDEX IF NOT EXISTS idx_wp_prediction_performance_scored ON wp_prediction_performance(scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_wp_prediction_performance_symbol ON wp_prediction_performance(symbol);

-- Enable RLS
ALTER TABLE wp_prediction_performance ENABLE ROW LEVEL SECURITY;

-- Allow read access (same pattern as other wp_ tables)
CREATE POLICY "Allow read access to prediction performance"
    ON wp_prediction_performance FOR SELECT
    USING (true);

-- Allow insert/update from service role
CREATE POLICY "Allow service role insert on prediction performance"
    ON wp_prediction_performance FOR INSERT
    WITH CHECK (true);

CREATE POLICY "Allow service role update on prediction performance"
    ON wp_prediction_performance FOR UPDATE
    USING (true);
