# Operational finding — your perf-tracker already knows the answer

**Date:** 2026-05-15 EDT
**Source:** live DROPLET `/perf-tracker/scorecard` + `/wallets/summary`
**TL;DR:** The data on your live system points to a specific, narrow paper_perp_v4 configuration that should be tested before any more research. No new code required — just config.

---

## What the live perf-tracker says (across all current paper trading)

Across **all symbols × directions × regimes**, your existing PerformanceTracker has graded each bucket. Here's the edge map (edge = avg net PnL per trade in USD):

### STRONG (deploy):

| symbol | dir | trades | wr | net | edge |
|---|---|---|---|---|---|
| **DOGE** | **short** | 41 | 36.6% | **+$530.80** | **+$12.95** |

### MARGINAL+ (worth allowing):

| direction × regime | trades | wr | net | edge |
|---|---|---|---|---|
| **short × TRENDING_UP** | 6 | 67% | +$99.34 | +$16.56 |
| **short × RANGING_HIGH_VOL** | 4 | 75% | +$33.84 | +$8.46 |
| ETH short (pair) | 50 | 42% | +$95.37 | +$1.91 |
| LINK short (pair) | 50 | 38% | +$124.08 | +$2.48 |

### TOXIC (kill):

| bucket | trades | wr | net | edge |
|---|---|---|---|---|
| **short × TRENDING_DOWN** | 50 | **16%** | **−$948.68** | **−$18.97** |
| long × RANGING_HIGH_VOL | 1 | 0% | −$23.06 | −$23.06 |
| short × RANGING_LOW_VOL | 8 | 0% | −$187.17 | −$23.40 |

### UNDERPERFORMING (flat or slow bleed):

Every single LONG bucket at pair level is negative. Across the entire current basket, longs have lost money systematically.

---

## What this tells us about your wallets

`paper_perp` (v1 Full Send) on the live DROPLET:
- **1000 trades** since 2026-04-24 reset
- **29% win rate**
- **+$435 net** ($25,000 → $25,435 — essentially flat after 1000 trades)
- Wallet hypothesis explicitly states: _"Router+brief_close OFF, liberal YOLO 5 — can we recover pre-04-13 +$4k edge?"_

**Conclusion: that hypothesis has been tested for 3 weeks with 1000 trades and the answer is NO.** Router-OFF + YOLO-5 does not recover the Apr 6-10 edge. The result is barely-positive flat performance.

The reason it's not catastrophic despite 29% WR: avg-win-to-avg-loss ratio is ~2.5:1, so the winning shorts (DOGE especially) just barely cover the toxic short-TRENDING_DOWN bucket and the losing longs.

---

## The proposed paper_perp_v4 config

Pure config change. No new code. Drops the explicit losers from the trading flow.

```yaml
name: paper_perp_v4
display_name: "v4 Short-Only Router-Gated"
description: |
  Test hypothesis from perf-tracker data: SHORTS work on this basket, longs do not.
  Router-ON correctly blocks the catastrophic short-TRENDING_DOWN bucket while
  preserving the marginal-positive short-TRENDING_UP and short-RANGING_HIGH_VOL buckets.
  Counterpart experiment to v1's "router-OFF" failed hypothesis.

parent_wallet_id: paper_perp_v1  # same starting capital, same fee model
generation: 4
config:
  # The big switch — was off, turn it on
  regime_router_enabled: true
  use_regime_v2: true             # research-backed half-life/Hurst/lag-1 ensemble

  # Short-only: data is unambiguous on this basket
  allow_long: false
  allow_short: true

  # Sizing (conservative — A/B against v1)
  base_pct: 6.0
  max_positions: 3
  max_positions_per_symbol: 1
  yolo_level: 3                   # tighter than v1's 5

  # Quality filters
  conviction_floor: 60            # higher than v1's 0 (v1 had no floor)
  require_stop_loss: true
  min_position_usd: 200
  trade_spacing_s: 180            # avoid burst-fires

  # Symbol whitelist: only symbols with positive short-pair grade
  symbol_whitelist: [DOGE, ETH, LINK]

  # Perf-tracker gate — only fire if the (symbol, dir, regime) triple has at least MARGINAL grade
  min_perf_grade: MARGINAL
  min_perf_mult: 1.0

  # Brief synthesizer behavior
  disable_brief_close: false      # let Brief close losing trades
  protect_mechanical_positions: false

  starting_equity: 25000.0
  experiment_role: "H4_router_on_shorts_only"
  hypothesis: "Router-ON + short-only + DOGE/ETH/LINK whitelist + min_grade=MARGINAL recovers edge"
```

### Why this should work given the data

1. **Router blocks short-TRENDING_DOWN.** That bucket has lost −$948 over 50 trades. With router on, that bucket's strategies are still allowed (mean_reversion, ema_crossover, turtle_donchian) but routed differently. Combined with `min_perf_grade=MARGINAL`, the TOXIC short-TRENDING_DOWN triples for ETH/LINK/etc are automatically gated off because their grade is below threshold.

2. **Allows short-TRENDING_UP and short-RANGING_HIGH_VOL** which both have positive edge.

3. **Drops longs entirely.** No long bucket on this basket has positive grade.

4. **DOGE/ETH/LINK whitelist:** DOGE shorts are STRONG (+$530, edge +$12.95), ETH/LINK shorts are MARGINAL positive. AVAX, SOL, ARB, BTC shorts are all UNDERPERFORMING or TOXIC at pair level.

5. **conviction_floor=60** filters out the lower-quality entries that contribute most to the 29% WR drag.

6. **use_regime_v2=true** uses the Hurst / half-life / autocorr ensemble instead of the ATR-percentile classifier that the mean_reversion.py author flagged as wrongly labeling drifts as RANGING_LOW_VOL.

---

## Risk model

Worst case for paper_perp_v4: even if perf-tracker grades are stale and the chosen buckets turn out to be no better than v1, it loses at the rate of v1 (~ flat with 29% WR over 1000 trades). The lower YOLO + min_position_usd + short-only constraints limit blast radius vs v1.

Best case: clean +$12.95/trade edge from DOGE shorts + +$8-17/trade on the short-TRENDING_UP and short-RANGING_HIGH_VOL buckets = potentially $5-15/day on $25K capital, depending on how often those regimes appear.

---

## Vs everything we tested today

The Kronos research (7 ideas, ~3 hours of GPU + analysis time) produced:
- 1 useful execution input (Idea #3 prob-of-touch for stop placement)
- 6 dead ends

The perf-tracker check (5 minutes of API calls) produced:
- 1 fully-specified strategy hypothesis backed by 1000 live trades of evidence
- A clean kill list (longs, short-TRENDING_DOWN)
- A clean keep list (DOGE shorts, short-TRENDING_UP, short-RANGING_HIGH_VOL)

The right next move is paper_perp_v4 with this config, NOT more Kronos research.

---

## What I will NOT do without explicit OK

- Create paper_perp_v4 in the live DB
- Modify any wallet's config on DROPLET
- Restart any service
- Deploy any code

What I will do once you say go:
1. Drop a SQL/MCP migration to create the v4 row with the config above.
2. Optionally rebuild Sage prompts to consume Kronos prob-of-touch for stop placement.
3. Surface a watch-list of metrics to monitor on v4 in the first 48 hours.

---

## Open question for the user

The perf-tracker shows the **mean_reversion** strategy at 3.0 ATR was the historical Apr 6-10 +$3,372 goldmine, and the `mean_reversion.py` file confirms shorts-only in TRENDING regimes. Should paper_perp_v4 be:

**A.** Run with ALL strategies allowed under router (config above) — let the router naturally route via `_ALLOWED_BY_REGIME`.

**B.** Constrain further to ONLY mean_reversion + the existing winners — explicit `strategy_whitelist: [mean_reversion]` — most narrow test.

**C.** Some hybrid (e.g., allow mean_reversion + ema_crossover but block range_breakout / band_fade until they prove out).

I'd recommend **B** as the cleanest single-variable test of "does the Apr 6-10 strategy reproduce with router-on and short-only?" — but say which.
