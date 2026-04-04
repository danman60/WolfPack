# NoFx Pattern Integration Plan

## Overview
Cherry-pick the best architectural patterns from NoFx into WolfPack. Ordered by ROI — each phase is independently valuable and builds toward the next.

---

## Phase 1: Peak Equity Tracking & Drawdown Monitor
**Files:** `intel/wolfpack/drawdown_monitor.py` (new), `intel/wolfpack/api.py`, `supabase/migrations/`
**Why first:** The `peak_equity` column already exists in `wp_circuit_breaker_state` but is never maintained. This is a safety gap — our 10% drawdown hard limit in circuit_breaker.py relies on externally-provided `current_drawdown_pct` with no auto-tracking. NoFx runs a dedicated goroutine for this; we need the Python equivalent.

### Tasks
1. **Migration: `wp_equity_highwater` table**
   - Columns: `id`, `exchange_id`, `peak_equity`, `peak_timestamp`, `current_equity`, `current_drawdown_pct`, `updated_at`
   - Also per-position peak tracking: add `peak_unrealized_pnl` column to paper_trading position dict

2. **`drawdown_monitor.py` module**
   - `update_peaks(portfolio_state)` — called every tick cycle
     - Compare current equity to stored peak; update if new high
     - Compute `current_drawdown_pct = (peak - current) / peak * 100`
     - Per-position: track peak unrealized P/L, compute position-level drawdown
   - `check_emergency_exits(positions)` — NoFx pattern: if position was profitable (>5%) but drew down 40% from peak → emergency close signal
   - Returns list of `{symbol, action: "emergency_close", reason}` for the auto_trader

3. **Wire into tick loop**
   - After market data fetch, before agent runs: `drawdown_monitor.update_peaks()`
   - Feed `current_drawdown_pct` from monitor (not externally) into volatility.py and circuit_breaker.py
   - After Brief recommendations: merge emergency_close signals from drawdown_monitor

### Acceptance
- Peak equity persists across restarts
- Drawdown percentage auto-computed, no manual input
- Emergency close triggers on positions that gave back >40% of peak profit

---

## Phase 2: Data Staleness Detection
**Files:** `intel/wolfpack/data_freshness.py` (new), `intel/wolfpack/modules/`, `intel/wolfpack/api.py`
**Why:** Current staleness check is a single 120s threshold in circuit_breaker. NoFx detects price freezes (consecutive identical prices) and skips stale symbols. We need per-symbol, per-source freshness.

### Tasks
1. **`data_freshness.py` module**
   - `FreshnessTracker` class with per-symbol, per-source timestamps
   - Sources: `candles`, `funding`, `orderbook`, `whale_trades`
   - `record_update(symbol, source, timestamp)` — called after each data fetch
   - `check_freshness(symbol)` → returns `{is_fresh: bool, stale_sources: [], age_seconds: {}}`
   - **Price freeze detection**: if last N candle closes are identical (within 0.01%), flag as frozen
   - Configurable thresholds per source (candles: 600s, funding: 1800s, orderbook: 60s)

2. **Wire into pipeline**
   - Each data fetch call records freshness
   - Before running agents for a symbol: check freshness
   - If stale: skip symbol this cycle, log warning, include in health endpoint
   - Feed freshness status to circuit_breaker (replace hardcoded 120s check)

3. **Health endpoint enhancement**
   - `/health` returns per-symbol freshness map
   - Frontend can show stale data indicators per symbol

### Acceptance
- Price freeze detected and symbol skipped automatically
- Per-source staleness thresholds (not one global number)
- Health endpoint shows per-symbol freshness

---

## Phase 3: Risk Control Formalization
**Files:** `intel/wolfpack/risk_controls.py` (new), refactor from circuit_breaker.py + sizing.py + veto.py
**Why:** Our risk controls work but are scattered across 3 files with no clear hard/soft distinction. NoFx's pattern: code-enforced limits that can NEVER be bypassed vs AI-guided suggestions. Formalizing this prevents future bugs where someone accidentally makes a hard limit overridable.

### Tasks
1. **`risk_controls.py` — unified risk policy**
   ```python
   class RiskPolicy:
       # HARD LIMITS — code-enforced, never overridden
       hard = HardLimits(
           max_positions=5,
           max_position_size_pct=25,
           max_margin_usage_pct=90,
           max_drawdown_pct=10,
           daily_pnl_floor_pct=-3,
           min_position_size_usd=50,
       )
       # SOFT LIMITS — AI-guided, conviction penalties
       soft = SoftLimits(
           leverage_cap_btc=5,
           leverage_cap_alt=3,
           min_conviction=55,
           min_risk_reward=2.0,
           max_trades_per_day=4,
       )
   ```

2. **Enforcement layer**
   - `enforce_hard(recommendation) → (pass, fail_reason)` — binary, no override
   - `apply_soft(recommendation) → adjusted_recommendation` — conviction penalties, size adjustments
   - Called in sequence: hard check first (reject if fail), then soft adjustments

3. **Refactor existing code**
   - circuit_breaker.py: extract hard limits into RiskPolicy.hard
   - sizing.py: extract MAX_SIZE_PCT, bounds into RiskPolicy
   - veto.py: map hard_rejects to RiskPolicy.hard, soft_penalties to RiskPolicy.soft
   - Keep circuit_breaker state machine (ACTIVE/SUSPENDED/EMERGENCY) — it's good
   - The 3 files become thinner, delegating limit values to RiskPolicy

4. **DB-configurable (optional)**
   - Store RiskPolicy overrides in `wp_risk_policy` table
   - YOLO profiles (cautious → full_send) become named RiskPolicy presets
   - Default policy loaded from code, overrides from DB

### Acceptance
- Single source of truth for all risk limits
- Hard limits cannot be bypassed by any code path
- YOLO profiles are named presets of RiskPolicy
- Existing behavior unchanged (refactor, not rewrite)

---

## Phase 4: Configurable Prompt Sections
**Files:** `intel/wolfpack/agents/*.py`, `supabase/migrations/`, `intel/wolfpack/prompt_builder.py` (new)
**Why:** All agent prompts are hardcoded Python strings. NoFx makes 8 prompt sections editable per strategy, enabling A/B testing and tuning without deploys. Given our agents produce trade recommendations that directly affect money, being able to tune prompts without code changes is high-value.

### Tasks
1. **Migration: `wp_prompt_templates` table**
   - Columns: `id`, `agent_name`, `section`, `content`, `is_active`, `version`, `created_at`
   - Sections: `role`, `input_format`, `output_schema`, `constraints`, `reasoning_instructions`, `examples`
   - Seed with current hardcoded prompts as version 1

2. **`prompt_builder.py`**
   - `build_system_prompt(agent_name) → str`
   - Loads sections from DB (with fallback to hardcoded defaults)
   - Assembles in order: role → constraints → input_format → reasoning → output_schema → examples
   - `estimate_tokens(agent_name) → int` — approximate token count before calling LLM

3. **Refactor agents**
   - Each agent's `system_prompt` property calls `prompt_builder.build_system_prompt(self.name)`
   - Hardcoded prompts become the default fallback (not deleted)
   - No behavioral change unless DB overrides exist

4. **Frontend (future, not this PR)**
   - Prompt editor page for tuning sections
   - Version history with diff view

### Acceptance
- Prompts loaded from DB with code fallback
- Token estimation available before LLM calls
- Zero behavioral change with default data

---

## Phase 5: Consecutive Failure Tracking & Safe Mode
**Files:** `intel/wolfpack/failure_tracker.py` (new), `intel/wolfpack/api.py`
**Why:** If the LLM provider goes down or returns garbage N times in a row, we should automatically enter a protective mode. NoFx activates "safe mode" (no new positions, protect existing) after 3 consecutive AI failures. Our circuit_breaker doesn't currently track AI-specific failures.

### Tasks
1. **`failure_tracker.py`**
   - `FailureTracker` class
   - `record_success(agent_name)` — resets counter
   - `record_failure(agent_name, error)` — increments counter
   - `is_safe_mode() → bool` — True if any agent has 3+ consecutive failures
   - `get_status() → {agent_name: {consecutive_failures, last_error, last_success}}`

2. **Wire into agent execution**
   - Wrap each agent call: on success → record_success, on exception → record_failure
   - If safe_mode active: skip Brief recommendations (no new trades), still process position_actions (exits OK)
   - Log prominently when entering/exiting safe mode

3. **Auto-recovery**
   - Safe mode clears when the failing agent succeeds once
   - Health endpoint includes failure tracker status

### Acceptance
- 3 consecutive LLM failures → no new positions opened
- Existing positions still managed (exits, stop adjustments)
- Auto-recovers on next successful agent run

---

## Phase 6: Chain-of-Thought Extraction Resilience
**Files:** `intel/wolfpack/agents/base.py`, `intel/wolfpack/response_parser.py` (new)
**Why:** NoFx's multi-fallback CoT extraction handles malformed JSON, stray Unicode, and missing tags gracefully. Our agents expect clean JSON; any parsing failure wastes an entire LLM call. Adding resilience here saves money and prevents missed trading opportunities.

### Tasks
1. **`response_parser.py`**
   - `extract_json(raw_response) → (parsed_dict, reasoning_text)`
   - Priority chain:
     1. Try `<reasoning>` tag extraction → JSON after tag
     2. Try markdown code fence extraction (```json...```)
     3. Try first `{` to last `}` extraction
     4. Try fixing common issues: smart quotes → ASCII, invisible chars, trailing commas
     5. Return `(None, raw_text)` on total failure
   - `validate_schema(parsed, expected_schema) → (valid_dict, errors)`

2. **Wire into agent base class**
   - Replace direct `json.loads()` calls with `response_parser.extract_json()`
   - Log reasoning text alongside decisions (for debugging)
   - On parse failure: record to failure_tracker (Phase 5), return None gracefully

### Acceptance
- Smart quotes, invisible chars, missing code fences handled automatically
- Reasoning text captured and stored
- Parse failures logged with raw response for debugging

---

## Phase 7: LLM Token Usage Telemetry
**Files:** `supabase/migrations/`, `intel/wolfpack/token_tracker.py` (new), `intel/wolfpack/agents/base.py`
**Why:** We run 4 agents per cycle, 12 cycles/hour. No visibility into token costs per agent or per symbol. NoFx tracks provider, model, prompt/completion tokens per call. Essential for optimizing costs and detecting runaway prompts.

### Tasks
1. **Migration: `wp_token_usage` table**
   - Columns: `id`, `agent_name`, `model`, `provider`, `prompt_tokens`, `completion_tokens`, `estimated_cost_usd`, `symbol`, `created_at`

2. **`token_tracker.py`**
   - `record_usage(agent_name, model, prompt_tokens, completion_tokens, symbol)`
   - `get_daily_summary() → {total_tokens, total_cost, by_agent: {}, by_model: {}}`
   - `get_hourly_burn_rate() → float` — tokens per hour, rolling 4h window

3. **Wire into agent calls**
   - Extract token counts from LLM response metadata (Anthropic, DeepSeek, OpenRouter all return this)
   - Call `token_tracker.record_usage()` after each agent call

4. **API endpoint**
   - `GET /api/token-usage?period=24h` — returns summary
   - Frontend widget showing daily cost and per-agent breakdown

### Acceptance
- Token usage logged per agent call
- Daily/hourly cost summaries available via API
- Alerts if daily cost exceeds threshold (configurable)

---

## Implementation Order & Dependencies

```
Phase 1 (Peak Equity)     ←── standalone, highest safety value
Phase 2 (Staleness)       ←── standalone, prevents bad trades
Phase 3 (Risk Controls)   ←── standalone, cleaner architecture
Phase 5 (Failure Tracker) ←── standalone, pairs well with Phase 1-2
Phase 4 (Prompts)         ←── standalone, enables experimentation
Phase 6 (CoT Parsing)     ←── benefits from Phase 5 (failure recording)
Phase 7 (Token Telemetry) ←── benefits from Phase 4 (prompt estimation)
```

Phases 1, 2, 3, 5 can be done in parallel (no dependencies).
Phases 4, 6, 7 are sequential refinements.

## Estimated Scope
- Each phase: 1-2 files new, 1-3 files modified
- No breaking changes — all additive with fallback to current behavior
- Total: ~7 new modules, ~5 migrations, ~10 file modifications
