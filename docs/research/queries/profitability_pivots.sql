-- WolfPack Profitability Pivot Queries
-- Phase 2.1 Research — 2026-04-11
-- Table: wp_trade_history (184 closed trades, 2026-03-13 to 2026-04-11)

---------------------------------------------------------------
-- 0. Schema Discovery
---------------------------------------------------------------
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'wp_trade_history'
ORDER BY ordinal_position;

---------------------------------------------------------------
-- 1. By (Symbol, Direction)
---------------------------------------------------------------
SELECT symbol, direction,
  COUNT(*) as trades,
  ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct,
  ROUND(AVG(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE NULL END)::numeric
        / NULLIF(ABS(AVG(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE NULL END)::numeric), 0), 2) as reward_risk,
  ROUND(SUM(pnl_usd)::numeric, 2) as net_pnl,
  ROUND(AVG(hold_duration_seconds)::numeric / 3600, 1) as avg_hold_hours,
  ROUND(AVG(max_favorable_excursion)::numeric, 2) as avg_mfe,
  ROUND(AVG(max_adverse_excursion)::numeric, 2) as avg_mae,
  ROUND(SUM(COALESCE(funding_cost_usd, 0))::numeric, 2) as total_funding,
  ROUND(AVG(COALESCE(entry_slippage_bps, 0) + COALESCE(exit_slippage_bps, 0))::numeric, 1) as avg_slippage_bps
FROM wp_trade_history
WHERE closed_at IS NOT NULL
GROUP BY symbol, direction
ORDER BY net_pnl DESC;

---------------------------------------------------------------
-- 2. By Strategy
---------------------------------------------------------------
SELECT strategy,
  COUNT(*) as trades,
  ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct,
  ROUND(AVG(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE NULL END)::numeric
        / NULLIF(ABS(AVG(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE NULL END)::numeric), 0), 2) as reward_risk,
  ROUND(SUM(pnl_usd)::numeric, 2) as net_pnl,
  ROUND(AVG(hold_duration_seconds)::numeric / 3600, 1) as avg_hold_hours,
  ROUND(AVG(max_favorable_excursion)::numeric, 2) as avg_mfe,
  ROUND(AVG(max_adverse_excursion)::numeric, 2) as avg_mae,
  ROUND(SUM(COALESCE(funding_cost_usd, 0))::numeric, 2) as total_funding
FROM wp_trade_history
WHERE closed_at IS NOT NULL
GROUP BY strategy
ORDER BY net_pnl DESC;

---------------------------------------------------------------
-- 3. By Regime at Entry
---------------------------------------------------------------
SELECT regime_at_entry,
  COUNT(*) as trades,
  ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct,
  ROUND(AVG(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE NULL END)::numeric
        / NULLIF(ABS(AVG(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE NULL END)::numeric), 0), 2) as reward_risk,
  ROUND(SUM(pnl_usd)::numeric, 2) as net_pnl,
  ROUND(AVG(hold_duration_seconds)::numeric / 3600, 1) as avg_hold_hours,
  ROUND(AVG(max_favorable_excursion)::numeric, 2) as avg_mfe,
  ROUND(AVG(max_adverse_excursion)::numeric, 2) as avg_mae
FROM wp_trade_history
WHERE closed_at IS NOT NULL
GROUP BY regime_at_entry
ORDER BY net_pnl DESC;

---------------------------------------------------------------
-- 4. By Conviction Bucket
---------------------------------------------------------------
SELECT
  CASE
    WHEN conviction_at_entry >= 80 THEN '80+'
    WHEN conviction_at_entry >= 70 THEN '70-79'
    WHEN conviction_at_entry >= 60 THEN '60-69'
    WHEN conviction_at_entry >= 50 THEN '50-59'
    ELSE '<50'
  END as conviction_bucket,
  COUNT(*) as trades,
  ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct,
  ROUND(AVG(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE NULL END)::numeric
        / NULLIF(ABS(AVG(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE NULL END)::numeric), 0), 2) as reward_risk,
  ROUND(SUM(pnl_usd)::numeric, 2) as net_pnl,
  ROUND(AVG(hold_duration_seconds)::numeric / 3600, 1) as avg_hold_hours
FROM wp_trade_history
WHERE closed_at IS NOT NULL
GROUP BY conviction_bucket
ORDER BY conviction_bucket;

---------------------------------------------------------------
-- 5. By Time of Day (ET)
---------------------------------------------------------------
SELECT
  EXTRACT(HOUR FROM opened_at AT TIME ZONE 'America/New_York')::int as hour_et,
  COUNT(*) as trades,
  ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct,
  ROUND(SUM(pnl_usd)::numeric, 2) as net_pnl,
  ROUND(AVG(pnl_usd)::numeric, 2) as avg_pnl
FROM wp_trade_history
WHERE closed_at IS NOT NULL
GROUP BY hour_et
ORDER BY hour_et;

---------------------------------------------------------------
-- 6. MFE/MAE Distribution
---------------------------------------------------------------
SELECT
  CASE WHEN pnl_usd > 0 THEN 'winner' ELSE 'loser' END as outcome,
  COUNT(*) as trades,
  ROUND(AVG(max_favorable_excursion)::numeric, 2) as avg_mfe,
  ROUND(AVG(max_adverse_excursion)::numeric, 2) as avg_mae,
  ROUND(AVG(pnl_usd)::numeric, 2) as avg_pnl,
  ROUND(AVG(max_favorable_excursion - pnl_usd)::numeric, 2) as avg_mfe_left_on_table,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY max_favorable_excursion)::numeric, 2) as median_mfe,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY max_adverse_excursion)::numeric, 2) as median_mae
FROM wp_trade_history
WHERE closed_at IS NOT NULL
GROUP BY outcome;

---------------------------------------------------------------
-- 7. Fee Drag
---------------------------------------------------------------
SELECT
  ROUND(SUM(pnl_usd)::numeric, 2) as net_pnl,
  ROUND(SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END)::numeric, 2) as gross_wins,
  ROUND(SUM(CASE WHEN pnl_usd < 0 THEN ABS(pnl_usd) ELSE 0 END)::numeric, 2) as gross_losses,
  ROUND(SUM(COALESCE(funding_cost_usd, 0))::numeric, 2) as total_funding,
  ROUND(AVG(COALESCE(entry_slippage_bps, 0))::numeric, 1) as avg_entry_slippage_bps,
  ROUND(AVG(COALESCE(exit_slippage_bps, 0))::numeric, 1) as avg_exit_slippage_bps,
  ROUND(SUM(size_usd * (COALESCE(entry_slippage_bps, 0) + COALESCE(exit_slippage_bps, 0)) / 10000)::numeric, 2) as est_slippage_cost_usd,
  COUNT(*) as total_trades,
  ROUND(SUM(size_usd)::numeric, 2) as total_volume
FROM wp_trade_history
WHERE closed_at IS NOT NULL;

---------------------------------------------------------------
-- 8. By Source (Brief-only vs others)
---------------------------------------------------------------
SELECT source,
  COUNT(*) as trades,
  ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct,
  ROUND(AVG(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE NULL END)::numeric
        / NULLIF(ABS(AVG(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE NULL END)::numeric), 0), 2) as reward_risk,
  ROUND(SUM(pnl_usd)::numeric, 2) as net_pnl,
  ROUND(AVG(hold_duration_seconds)::numeric / 3600, 1) as avg_hold_hours
FROM wp_trade_history
WHERE closed_at IS NOT NULL
GROUP BY source
ORDER BY net_pnl DESC;

---------------------------------------------------------------
-- Supplementary: Overall Stats
---------------------------------------------------------------
SELECT
  COUNT(*) as total_trades,
  MIN(opened_at) as first_trade,
  MAX(closed_at) as last_trade,
  ROUND(SUM(pnl_usd)::numeric, 2) as net_pnl,
  ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct,
  COUNT(DISTINCT symbol) as symbols_traded,
  COUNT(DISTINCT strategy) as strategies_used
FROM wp_trade_history
WHERE closed_at IS NOT NULL;

---------------------------------------------------------------
-- Supplementary: Exit Reason Breakdown
---------------------------------------------------------------
SELECT exit_reason, COUNT(*) as trades,
  ROUND(SUM(pnl_usd)::numeric, 2) as net_pnl,
  ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct
FROM wp_trade_history
WHERE closed_at IS NOT NULL
GROUP BY exit_reason
ORDER BY trades DESC;
