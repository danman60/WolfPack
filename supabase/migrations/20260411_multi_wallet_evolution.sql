-- Multi-wallet evolution system: metadata + PBT lineage tracking
ALTER TABLE wp_wallets ADD COLUMN IF NOT EXISTS display_name TEXT;
ALTER TABLE wp_wallets ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE wp_wallets ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE wp_wallets ADD COLUMN IF NOT EXISTS parent_wallet_id UUID REFERENCES wp_wallets(id);
ALTER TABLE wp_wallets ADD COLUMN IF NOT EXISTS generation INTEGER NOT NULL DEFAULT 0;
ALTER TABLE wp_wallets ADD COLUMN IF NOT EXISTS fitness_score REAL;
ALTER TABLE wp_wallets ADD COLUMN IF NOT EXISTS fitness_updated_at TIMESTAMPTZ;

-- Backfill existing wallets with display names
UPDATE wp_wallets SET display_name = 'v1 Full Send', description = 'Baseline paper trading wallet — Brief + veto + YOLO system with TOXIC blocking and performance-weighted sizing', version = 1 WHERE name = 'paper_perp';
UPDATE wp_wallets SET display_name = 'Production Perp', description = 'Live money perpetual trading (inactive until cutover)' WHERE name = 'prod_perp';
UPDATE wp_wallets SET display_name = 'Paper LP', description = 'Paper Uniswap V3 LP positions' WHERE name = 'paper_lp';
UPDATE wp_wallets SET display_name = 'Production LP', description = 'Live Uniswap V3 LP positions (inactive)' WHERE name = 'prod_lp';

-- Backfill paper_perp config with current Full Send settings
UPDATE wp_wallets SET config = '{
  "yolo_level": 5,
  "conviction_floor": 25,
  "brief_only_mult": 1.00,
  "min_perf_mult": 0.85,
  "min_position_usd": 50,
  "trade_spacing_s": 30,
  "base_pct": 25.0,
  "max_position_size_pct": 25.0,
  "max_positions": 12,
  "max_trades_per_day": 40,
  "penalty_multiplier": 0.0,
  "rejection_cooldown_hours": 0.0,
  "require_stop_loss": false,
  "max_positions_per_symbol": 3
}'::jsonb WHERE name = 'paper_perp';

-- Seed v2 conservative wallet for A/B comparison
INSERT INTO wp_wallets (id, name, wallet_mode, wallet_type, starting_equity, current_equity, status, display_name, description, version, config, parent_wallet_id)
SELECT
  gen_random_uuid(),
  'paper_perp_v2',
  'paper',
  'perp',
  10000,
  10000,
  'active',
  'v2 Conservative',
  'Conservative strategy — higher conviction floor, mandatory stop losses, smaller positions. Tests whether selectivity beats volume.',
  2,
  '{"yolo_level": 2, "conviction_floor": 50, "brief_only_mult": 0.25, "min_perf_mult": 0.15, "min_position_usd": 200, "trade_spacing_s": 300, "base_pct": 10.0, "max_position_size_pct": 15.0, "max_positions": 5, "max_trades_per_day": 4, "penalty_multiplier": 1.0, "rejection_cooldown_hours": 1.0, "require_stop_loss": true, "max_positions_per_symbol": 1}'::jsonb,
  (SELECT id FROM wp_wallets WHERE name = 'paper_perp')
WHERE NOT EXISTS (SELECT 1 FROM wp_wallets WHERE name = 'paper_perp_v2');
