-- Add strategy column to wp_auto_trades if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'wp_auto_trades' AND column_name = 'strategy'
    ) THEN
        ALTER TABLE wp_auto_trades ADD COLUMN strategy TEXT;
    END IF;
END $$;

-- Conviction calibration view
-- Buckets conviction into ranges and shows avg P&L per bucket
CREATE OR REPLACE VIEW wp_conviction_calibration AS
SELECT
    bucket,
    COUNT(*) AS total_trades,
    COUNT(CASE WHEN t.pnl_usd > 0 THEN 1 END) AS winners,
    COUNT(CASE WHEN t.pnl_usd <= 0 THEN 1 END) AS losers,
    ROUND(AVG(t.pnl_usd)::numeric, 2) AS avg_pnl_usd,
    ROUND(SUM(t.pnl_usd)::numeric, 2) AS total_pnl_usd,
    ROUND(
        (COUNT(CASE WHEN t.pnl_usd > 0 THEN 1 END)::numeric / NULLIF(COUNT(*), 0) * 100),
        1
    ) AS win_rate_pct,
    ROUND(AVG(r.conviction)::numeric, 1) AS avg_conviction,
    t.strategy
FROM (
    SELECT
        *,
        CASE
            WHEN conviction >= 90 THEN '90-100'
            WHEN conviction >= 80 THEN '80-89'
            WHEN conviction >= 70 THEN '70-79'
            WHEN conviction >= 60 THEN '60-69'
            WHEN conviction >= 50 THEN '50-59'
            ELSE 'below-50'
        END AS bucket
    FROM wp_auto_trades
    WHERE status = 'closed' AND pnl_usd IS NOT NULL
) t
LEFT JOIN wp_trade_recommendations r ON t.recommendation_id::text = r.id::text
GROUP BY bucket, t.strategy
ORDER BY bucket DESC, t.strategy;
