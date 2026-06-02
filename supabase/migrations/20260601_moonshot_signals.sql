-- Moonshot Scalper forward-watch signal log (RESEARCH / OBSERVATION ONLY).
--
-- DO NOT APPLY without user approval. This table stores screener candidate
-- "shots" for forward observation. It is NOT wired into any trading path,
-- wallet, or strategy. No money, no orders. Written by
-- intel/wolfpack/research/moonshot_screener.py (currently it logs to a local
-- JSONL; this table is the eventual durable sink for the 2-week forward-watch).
--
-- Intentionally has no FK to wp_wallets — moonshot signals are venue-level
-- observations, not per-wallet trades.

CREATE TABLE IF NOT EXISTS wp_moonshot_signals (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  observed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  ticker          TEXT NOT NULL,

  -- buzz signal
  buzz_score      REAL NOT NULL DEFAULT 0,      -- [0,100]
  sources         JSONB NOT NULL DEFAULT '[]',  -- e.g. ["coingecko_trending","biz:3"]

  -- HL venue context (small-cap gating)
  hl_vol_24h      BIGINT,
  hl_oi_usd       BIGINT,
  hl_maxlev       INT,
  est_spread_bps  REAL,
  spread_gate_pass BOOLEAN,

  -- chart trigger (momentum_buckets)
  regime_hint     TEXT,                          -- trending|breakout|choppy|transitional
  momentum_score  REAL,                          -- [-1,1]
  conviction      REAL,                          -- [0,1]
  primary_trend   TEXT,

  -- hypothetical asymmetric small-bet plan (NEVER executed)
  hypo_entry      REAL,
  hypo_stop       REAL,                          -- -4%
  hypo_target     REAL,                          -- +8%

  is_shot         BOOLEAN NOT NULL DEFAULT FALSE, -- passed full screen gate

  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_moonshot_signals_observed_at ON wp_moonshot_signals (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_moonshot_signals_ticker ON wp_moonshot_signals (ticker);
CREATE INDEX IF NOT EXISTS idx_moonshot_signals_is_shot ON wp_moonshot_signals (is_shot) WHERE is_shot = TRUE;

COMMENT ON TABLE wp_moonshot_signals IS
  'Research forward-watch log for the moonshot scalper spike. Observation only — not wired to trading. See docs/research/2026-06-moonshot-scalper/.';
