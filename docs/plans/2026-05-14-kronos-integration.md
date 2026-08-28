# Kronos Integration — Design (no code yet)

**Date:** 2026-05-14 EDT (2026-05-15 UTC) — install session
**Status:** Design only. No WolfPack code changes until user signs off on host/wallet/scope choices.
**Author:** Claude (Opus 4.7) — install session SPYBALLOON / WolfPack-Kronos

---

## TL;DR

Install Kronos on **SPYBALLOON** (RTX 3060 12GB, idle, 136 MB VRAM peak for Kronos-small). DROPLET stays the *caller* — a thin HTTP wrapper hits a local SPYBALLOON FastAPI endpoint over Tailscale (`100.x.x.x:8090`) and feeds the forecast into the **Sage** agent's context block (and optionally into a Brief-level veto). Kronos never triggers trades. **Edge unproven** — the integration's first job is to A/B against `paper_perp_v1/v2/v3` via a new `paper_perp_v4` wallet ("Kronos-augmented Sage") before any capital allocation decision is made.

---

## Why this exists

WolfPack has a documented one-sided test history:
- 13 backtest phases (`docs/research/2026-05-backtest-sweep/`) on the existing OHLCV strategy stack → 1 real edge (funding-z low → long on BTC/DOGE), zero edge in pure-candle space.
- The Sage agent's current "forecast" is pure LLM narrative — no quantitative prior.
- Paper wallets v1/v2/v3 lost money for ~12 consecutive days.

Kronos is a candidate quantitative prior for Sage. It is **not** a fix for the regime-router or the simulator bug in Phase 12/13. It is a sensor; DeepSeek is still the decision-maker.

**Prior on this working:** low-to-moderate. Pure-OHLCV forecasting models have a long history of looking great in-sample and failing to beat HODL after costs. AAAI 2026 acceptance is for the architecture, not for a verified edge claim on crypto perps. Treat as a longshot worth testing because installation is cheap and the failure mode is informative.

---

## Sanity-check result (2026-05-14 22:20 EDT)

Holdout test on the last 24 hours of BTC/USDT 1h candles, Kronos-small + Kronos-Tokenizer-base, lookback 480, sample_count=1:

| Metric | Value |
|---|---|
| Device | `cuda:0` (RTX 3060) |
| Model load time | 2.1 s |
| Predict time (24 candles) | **0.45 s** |
| Peak VRAM | **136 MB** |
| Close MAPE | 0.94% |
| Close RMSE | $860 (~1.07% of price) |
| Direction agreement (per-hour vs anchor) | 22/24 = 91.7% |
| 24h cumulative move predict vs actual | +1.32% vs +2.41%, sign matched |

This is **one window, n=1** — not evidence of edge. It establishes only:
1. Inference is fast enough for any reasonable cadence (sub-second per symbol on RTX 3060).
2. VRAM is trivial — we can run several Kronos models in parallel without contention.
3. The output is shape-coherent (no NaN, no nonsense values, no obvious detachment from input regime).

Artifacts: `~/projects/Kronos/samples/btc-1h-forecast-20260515T022012Z.{csv,png}` plus matching `*-actual-*.csv`.

---

## Architecture

```
                              ┌────────────────────────────────────────────────────┐
                              │ SPYBALLOON (RTX 3060 12GB, Ubuntu 24.04, idle GPU) │
                              │                                                    │
                              │   ~/projects/Kronos/                               │
                              │     venv/      (torch 2.12.0+cu130, CUDA 13)       │
                              │     model/     (KronosPredictor)                   │
                              │     server.py  (FastAPI, new — to be written)      │
                              │                                                    │
                              │   HF_HOME=/mnt/firmament/hf-cache (534 MB total)   │
                              │     models--NeoQuasar--Kronos-Tokenizer-base       │
                              │     models--NeoQuasar--Kronos-Tokenizer-2k         │
                              │     models--NeoQuasar--Kronos-mini   ( 16 MB)      │
                              │     models--NeoQuasar--Kronos-small  ( 95 MB)      │
                              │     models--NeoQuasar--Kronos-base   (391 MB)      │
                              │                                                    │
                              │   listens on Tailscale IP only:                    │
                              │     POST 100.x.x.x:8090/forecast                   │
                              └─────────────────────────┬──────────────────────────┘
                                                        │
                                          Tailscale (private mesh)
                                                        │
   ┌────────────────────────────────────────────────────┴───────────────────────────┐
   │ DROPLET (DigitalOcean, 1 vCPU / 1 GB / 24 GB — ~98% disk, no GPU)              │
   │                                                                                │
   │   ~/projects/WolfPack/intel/wolfpack/                                          │
   │     modules/kronos_forecast.py     ← NEW thin client                           │
   │     agents/sage.py                 ← consumer: forecast block in prompt        │
   │     agents/brief.py                ← optional: forecast-as-veto                │
   │                                                                                │
   │   tick_loop._run_full_cycle() invokes:                                         │
   │     1. Quant (existing)                                                        │
   │     2. Snoop (existing)                                                        │
   │     3. Sage (existing) — now with Kronos forecast in its context block         │
   │     4. Brief (existing) — synthesizes; uses Kronos as veto if confidence high  │
   └────────────────────────────────────────────────────────────────────────────────┘
```

**Critical:** Kronos-base (102M params, 391 MB) does not fit DROPLET (1 GB RAM, ~98% disk full). Kronos host MUST be SPYBALLOON or FIRMAMENT. SPYBALLOON is the recommended choice because its 3060 is idle while FIRMAMENT's 4090 is GPU-pinned by Topaz Video AI rendering.

---

## API surface

### Server side (new `~/projects/Kronos/server.py`)

```
POST /forecast
Content-Type: application/json
Authorization: Bearer <KRONOS_API_TOKEN>  # shared secret in WolfPack .env

{
  "symbol": "BTC/USDT",
  "interval": "1h",
  "lookback_candles": 480,
  "horizon_candles": 24,
  "sample_count": 4,           # average multiple paths for stability
  "model": "Kronos-small",     # or "Kronos-base"
  "history": [                 # caller provides the OHLCV — server does NOT fetch
    {"ts": "2026-05-14T01:00:00Z", "o": 80000, "h": 80100, "l": 79950, "c": 80050, "v": 123.4, "a": 9876543},
    ...
  ]
}

→ 200 OK
{
  "model": "Kronos-small",
  "horizon_candles": 24,
  "device": "cuda:0",
  "latency_ms": 460,
  "generated_at": "2026-05-14T22:30:00Z",
  "forecast": [
    {"ts": "2026-05-14T02:00:00Z", "o": 80055, "h": 80120, "l": 79980, "c": 80075, "v": 120.1, "a": 9610000},
    ...
  ],
  "summary": {
    "horizon_return_pct": 1.32,
    "horizon_high_pct":  2.10,
    "horizon_low_pct":  -0.95,
    "ending_direction": "up"
  }
}
```

### Client side (new `intel/wolfpack/modules/kronos_forecast.py`)

```python
class KronosForecastClient:
    def __init__(self, base_url: str, token: str, timeout_s: float = 5.0):
        ...
    def forecast(self, symbol, interval, lookback_df, horizon=24, model="Kronos-small") -> dict | None:
        """Returns dict or None on any failure (timeout, 5xx, schema mismatch).
        Caller MUST handle None — no fail-loud, no exceptions surfaced to tick_loop."""
```

**Fallback policy:** when the client returns None (Tailscale down, SPYBALLOON off, server crashed, schema drift), Sage proceeds **exactly as today** — no Kronos block in the prompt, no degraded behavior, no logged trade decision change. The forecast is *additive* context, never a precondition for action.

---

## Where Kronos slots into the agent flow

**Path A — Sage augmentation (default, low-risk):**
The Sage agent's existing prompt has a `signals` block. Add a Kronos sub-section:

```
Kronos forecast (model=Kronos-small, lookback=480 1h candles, horizon=24h):
  predicted_path_summary:
    24h_return:      +1.32%
    24h_high:        +2.10% above current
    24h_low:         -0.95% below current
    ending_direction: up
  shape_note: forecast is monotonically grinding higher with no large swings.
  caveat: model is OHLCV-only — it does not see funding rate, OI, social, whale flow.
  freshness_s: 47
```

Sage uses this as one signal among many. Its existing scenario-matrix output remains unchanged in schema; the forecast just informs the scenarios.

**Path B — Brief veto (deferred):**
Only after Path A produces measurable improvement. Add a hard rule in Brief: "If Kronos's high-confidence ending direction conflicts with the proposed trade direction *and* Kronos's 24h move is >2σ from zero, downgrade conviction by 30 or flip to wait." Out of scope for v1.

**Path C — Standalone Quant module (deferred):**
Treat Kronos predictions as a derived signal source — e.g., "predict-vs-realize divergence" as a regime-shift indicator (the realized path diverging from the model prior is itself informative). Out of scope for v1.

---

## Where Kronos does NOT slot in (yet)

- **NOT in `auto_trader.py`** — no path from forecast directly to order.
- **NOT in `live_trading.py`** — same.
- **NOT in `performance_tracker.py`** — Kronos is a sensor, not a trade-performance metric.
- **NOT replacing the funding-rate signal** (Phase 6/8 finding). Kronos cannot see funding.

---

## Multi-wallet test plan (REQUIRED before any capital allocation)

Per the multi-wallet evolution protocol in `~/projects/WolfPack/CLAUDE.md`:

Spawn `paper_perp_v4`:
- `display_name`: "Kronos-augmented Sage"
- `parent_wallet_id`: `paper_perp_v2` (closest behavioural baseline — Conservative config)
- `generation`: 4
- `description`: "Identical config to v2 except Sage agent receives Kronos forecast block. Tests whether quantitative OHLCV prior adds edge over pure-LLM narrative."
- All other knobs identical to v2 (regime_router_enabled=false, same risk caps, same watchlist).

Run alongside v1/v2/v3 on the same market data. **No live capital cutover unless v4 beats v2 by a statistically meaningful margin over ≥4 weeks AND the Phase 12/13 simulator bug is fixed.**

---

## Open questions for the user (do not guess)

1. **Host:** SPYBALLOON (recommended) or FIRMAMENT? My read: SPYBALLOON. Confirm.
2. **Cadence:** Should DROPLET call Kronos *every* `_run_full_cycle()` (currently 4 hr per the recent perf change → 6 calls/day × 3 symbols = 18 calls/day, trivial), or only on Sage's request, or only when the Brief flags a candidate trade? My read: every cycle — it's cheap and Sage's block is always useful context.
3. **Model:** Kronos-small for everything (fast, 95 MB), or Kronos-base for headline assets (slower, 391 MB, presumably more accurate)? My read: Kronos-small for v1 — establish the harness before tuning.
4. **Symbol scope:** Just the current watchlist (BTC/ETH/LINK) or also DOGE/ARB/AVAX from the backtest universe? My read: stick to the current watchlist.
5. **Wallet:** Confirm `paper_perp_v4` is the right vehicle (vs. branching from `paper_perp_v1` Full Send, or running Kronos in shadow-mode on all 3 existing wallets without a new wallet).
6. **License:** Kronos is MIT — no license drama. WolfPack is personal/closed; no obligations triggered. Confirm understood.

---

## What this design explicitly does NOT do

- Does **not** modify any WolfPack code.
- Does **not** wire Kronos into trade execution.
- Does **not** assume Kronos provides edge.
- Does **not** require any DROPLET restart, deployment, or production-side change.
- Does **not** spawn the v4 wallet — that requires explicit user OK and DB migration.

Implementation order, once user signs off:
1. `~/projects/Kronos/server.py` (FastAPI, on SPYBALLOON) — local-only, no DROPLET deploy.
2. Smoke test from DROPLET → SPYBALLOON over Tailscale.
3. `intel/wolfpack/modules/kronos_forecast.py` (client + dataclasses + None fallback).
4. Sage prompt change (small, isolated diff — single new context block, gated behind `wallet.config.kronos_enabled` flag).
5. Spawn `paper_perp_v4` with `kronos_enabled=true`, all other wallets remain `kronos_enabled=false`.
6. Run 4 weeks. Compare per-wallet P&L. Decide.

---

## Cost / risk envelope

- Compute: ~0.5 s × 18 cycles/day = 9 GPU-seconds/day on SPYBALLOON. Zero marginal cost.
- Tokens: zero — Kronos is local, no LLM API calls in the forecast path.
- Data: Binance public klines API for the forecast's input candle history (no auth, no rate-limit risk at our volume); OR re-use whatever the existing `candle_cache.py` already maintains. **Prefer re-use** — fewer moving parts.
- Risk to existing system: low. Kronos client returns None on any failure; Sage's prompt has the Kronos block omitted; nothing else changes.
- Risk of false confidence: **moderate.** If Sage starts deferring to Kronos because the forecast looks confident on a backtest-cherry-picked window, conviction quality could degrade. Mitigation: gate behind a single wallet, A/B against unaugmented Sage, and instrument forecast-vs-realized in `prediction_scorer.py`-style storage from day one.
