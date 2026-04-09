-- Phase 1: Cycle telemetry + veto audit log + watchdog state
-- Additive-only: no changes to existing tables.
-- Plan: /home/danman60/.claude/plans/crystalline-splashing-cerf.md (Phase 1)

-- ── wp_cycle_metrics: one row per intelligence cycle ──
CREATE TABLE IF NOT EXISTS wp_cycle_metrics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id uuid NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    duration_ms int,
    symbols_processed int DEFAULT 0,
    agent_outputs_stored jsonb DEFAULT '{}'::jsonb,
    recs_produced int DEFAULT 0,
    recs_veto_rejected int DEFAULT 0,
    recs_veto_adjusted int DEFAULT 0,
    recs_passed int DEFAULT 0,
    strategies_activated jsonb DEFAULT '{}'::jsonb,
    sizing_blocked_count int DEFAULT 0,
    sizing_blocked_reasons jsonb DEFAULT '[]'::jsonb,
    positions_opened int DEFAULT 0,
    positions_closed int DEFAULT 0,
    cb_state text,
    cb_allow_new_entry boolean,
    regime_state_per_symbol jsonb DEFAULT '{}'::jsonb,
    regime_changed_symbols text[] DEFAULT ARRAY[]::text[],
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS wp_cycle_metrics_started_at_idx
    ON wp_cycle_metrics (started_at DESC);

-- ── wp_veto_log: per-recommendation veto audit trail ──
CREATE TABLE IF NOT EXISTS wp_veto_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id uuid,
    symbol text,
    direction text,
    raw_conviction int,
    adjusted_conviction int,
    penalties jsonb DEFAULT '{}'::jsonb,
    action text,  -- pass | adjust | reject
    reject_reason text[] DEFAULT ARRAY[]::text[],
    cooldown_expires_at timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS wp_veto_log_symbol_created_at_idx
    ON wp_veto_log (symbol, created_at DESC);

CREATE INDEX IF NOT EXISTS wp_veto_log_action_idx
    ON wp_veto_log (action);

-- ── wp_watchdog_state: persistent state for watchdog monitors ──
-- PK is monitor_name (not uuid) per plan — one row per named monitor.
CREATE TABLE IF NOT EXISTS wp_watchdog_state (
    monitor_name text PRIMARY KEY,
    state jsonb DEFAULT '{}'::jsonb,
    updated_at timestamptz DEFAULT now()
);
