-- Phase 3: Human Heuristics wallet state machine
-- Adds per-wallet emotional drives (hunger/satisfaction/fear/curiosity) that
-- modulate conviction floors and sizing for v3 (`paper_perp_v3`).
--
-- v1 (paper_perp) and v2 (paper_perp_v2) receive default rows but remain
-- untouched at runtime — heuristic modulation is gated on
-- `wallet.config.heuristics_enabled`.

CREATE TABLE IF NOT EXISTS wp_wallet_state (
  wallet_id UUID PRIMARY KEY REFERENCES wp_wallets(id) ON DELETE CASCADE,
  hunger REAL NOT NULL DEFAULT 0.5,
  satisfaction REAL NOT NULL DEFAULT 0.5,
  fear REAL NOT NULL DEFAULT 0.5,
  curiosity REAL NOT NULL DEFAULT 0.5,
  loss_streak INT NOT NULL DEFAULT 0,
  win_streak INT NOT NULL DEFAULT 0,
  daily_pnl_target REAL NOT NULL DEFAULT 0,
  last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS wp_wallet_state_history (
  id BIGSERIAL PRIMARY KEY,
  wallet_id UUID NOT NULL REFERENCES wp_wallets(id) ON DELETE CASCADE,
  hunger REAL NOT NULL,
  satisfaction REAL NOT NULL,
  fear REAL NOT NULL,
  curiosity REAL NOT NULL,
  loss_streak INT NOT NULL,
  win_streak INT NOT NULL,
  daily_pnl REAL NOT NULL,
  equity REAL NOT NULL,
  event TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wallet_state_history_wallet_created
  ON wp_wallet_state_history(wallet_id, created_at DESC);
