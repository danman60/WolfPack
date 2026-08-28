# Alpha Reset — stop predicting, start getting paid

**Date:** 2026-08-27
**Status:** PLAN — Phase 0 started, Phases 1-3 await user direction
**Supersedes strategy of:** all 13 phases of `docs/research/2026-05-backtest-sweep/` and the 2026-06 turtle work

---

## The diagnosis, restated

WolfPack has run 13+ backtest phases over ~12 months and produced exactly one surviving
edge (funding-z BTC, n=75, +0.492%/trade, ~2.8 fires/month). Everything else died. The
prior sessions attributed this to a crowded venue. That is only half true. The other half:

**Every phase searched the same thin dataset.** All 13 phases ran on `candleSnapshot`
OHLCV — capped at 5000 bars, 6 fields, no positioning data. That is roughly 210k
datapoints across the whole program.

Hyperliquid publishes `s3://hyperliquid-archive/asset_ctxs/` — **1-minute** `funding`,
`open_interest`, `premium`, `oracle_px`, `mark_px`, `mid_px`, `impact_bid_px`,
`impact_ask_px` for **232 coins back to 2023-05-20**. Verified 2026-08-27: 1,440
rows/day/coin, 10 MB/day compressed for the entire universe, ~11.8 GB and **~$1.06 in AWS
egress for the full 3-year history**.

For BTC alone that is ~1.7M rows × 12 fields versus the 5,000 4h bars every prior phase
used. Roughly 340× the observations per symbol, and the six extra columns are all
*flow and positioning* rather than price shape.

The repo has been searching the one dataset every other retail bot also searches, and
ignoring the one sitting in a public bucket.

## The strategic reframe

There are three ways to make money in a market:

1. **Predict direction.** Hardest, most crowded, lowest prior. WolfPack has attempted
   only this, for 12 months, and netted ~zero.
2. **Harvest a risk premium (carry).** Get paid for holding a risk others want to shed.
   Structurally durable because the payer is motivated by something other than alpha.
3. **Provide liquidity (fee/spread capture).** Get paid for immediacy. An
   inventory-management business, not a forecasting business.

Note that WolfPack's *only* survivor — funding-z — is a degenerate form of (2). It
survived precisely because it is not a prediction. That is the signal to follow.

Also note that the Polymarket operator that prompted this review (~$220k net over 138
days, 87% maker) is running (3), not (1). And WolfPack already contains ~2,900 LOC of
(3) — the Uniswap V3 auto-LP system — dormant since 2026-04-15.

**Thesis: abandon (1) as the primary program. Pursue (2) and (3).**

---

## Phase 0 — Dataset (STARTED 2026-08-27)

- [x] Verify archive access, schema, cost. Confirmed.
- [ ] Pull `asset_ctxs` 2023-05-20 → 2026-08-01 (~1,170 files, 11.8 GB, ~$1). RUNNING.
- [ ] Consolidate to per-coin Parquet, 1-min index, UTC.
- [ ] Pull free CDN `liquidity_by_coin` (`median_slippage_{0,1000,3000,10000}`,
      `median_liquidity`) for **real per-symbol execution cost**. Note the CDN series
      ends 2026-04-03 — backfill only, not current.
- [ ] Decide whether L2 book history (`market_data/`, ~16 MB/day/coin, 2023-04-15→) is
      needed. Defer until a hypothesis actually requires it.

**Why first:** every downstream gate needs real costs and real flow. Cheap, reversible,
no code touched.

## Phase 1 — Fix the gates BEFORE the next search

Each item maps to a defect found on 2026-08-27. Do not run another search until done.

- [ ] **One module.** `intel/wolfpack/research/edge_gates.py`. The 4 gates currently
      exist as 4 copy-pasted implementations with silent drift
      (`run_phase4_edge_provenance.py:191`, `run_phase6_funding_edge.py:174`,
      `run_phase9_leg23_signals.py:184`, `run_fundingz_revalidation.py:173`).
      **Gate 4 threshold drifted 0.75 → 0.50; the only surviving edge was validated
      against the looser one.** Pick semantics deliberately and import everywhere.
- [ ] **Kill the horizon-selection leak.** Gate 1 picks `h` from `[1,4,12,24]` by max
      t-stat then tests that t-stat at 2.0 as if it were a single test
      (`run_phase4_edge_provenance.py:158,357-362`). Either pre-register `h` from the
      hypothesis, or require t > 2.5.
- [ ] **Real costs, per symbol, from Phase 0 slippage data.** `COST_PCT = 0.001`
      (`:39`) is 3-4× too low for small caps — the repo's own notes say 30-40bps.
      Edges "passed" that were inside the spread.
- [ ] **Add Gate 5: signal → strategy.** Two candidates passed the gates and then lost
      money as strategies (Phase 4→5 capitulation flush; Phase 6→7 funding-z). The gates
      measure mean forward return; strategies add stops, TPs, overlap rules and costs,
      and stops convert positive-mean/left-skewed distributions into negative-mean ones.
      **This gap was diagnosed in Phase 5 and never fixed.** Gate 5 must run the actual
      trade construction and require it to still pass.
- [ ] **Perturb every fitted parameter in Gate 4.** `Z_WINDOW = 180` is fitted and never
      perturbed (`run_fundingz_revalidation.py:32,216-224`); only the z-threshold is.
      `SL/TP/MAX_HOLD` (`:34`) are Phase 7 best-params reused unchanged.
- [ ] **Block bootstrap everywhere.** The headline funding-z numbers ("MC prob-profit
      98.6%, MC p5 +9.3%") came from a plain IID resample
      (`run_fundingz_revalidation.py:318`), not `MonteCarloEngine`'s block bootstrap.
      IID destroys autocorrelation and overstates prob-profit. The turtle figures quoted
      beside them in the scoreboard *did* use block bootstrap — **the two are not
      comparable.** Re-run funding-z through `modules/monte_carlo.py:41`.
- [ ] **Gate 3 honesty.** Docstring claims "beats HODL of same window" is required; the
      code computes and ignores it (`:254,:257`). Enforce or delete the claim.
- [ ] **Pre-registration log.** Every hypothesis + params + thresholds written to
      `docs/research/HYPOTHESIS_LOG.md` *before* running, including the ones that die.
      This makes the search space countable.
- [ ] **Program-wide multiple-comparison correction.** With a countable log, apply
      Benjamini-Hochberg FDR across all hypotheses ever tested, and report **Deflated
      Sharpe Ratio** (Bailey & López de Prado) which adjusts for number of trials and
      non-normality. Industry standard for exactly this failure mode. Phase 3's "2 of
      168 cells passed" is *below* the ~8 you'd expect from chance at 5% — the program
      has never accounted for this globally.

## Phase 2 — Three tracks, by prior

### Track A — Carry harvest (HIGHEST PRIOR)

The repo tested funding as a **predictor**. The better trade is funding as a **coupon**.

Delta-neutral: short perp on Hyperliquid, long spot elsewhere, collect funding when it is
positive and extreme; reverse when negative. This is not a directional bet — the P&L is
the funding stream minus basis drift minus costs minus execution risk. Fully testable
from Phase 0 data (`funding` + `premium` + real costs), with 3 years and 232 coins
instead of n=75.

Hyperliquid is permissionless — no Ontario geoblock. The existing directional funding-z
becomes a special case of the same family.

Key questions: does net carry survive costs and rebalance friction? Which coins? What
does the tail look like when funding flips against an open position?

### Track B — Positioning / flow signals (MEDIUM PRIOR)

The genuinely under-searched space, now unlocked by Phase 0:

- OI-delta × price-delta quadrants (new longs / short squeeze / long liquidation / new
  shorts — four distinct forward distributions, routinely conflated)
- `premium` z-score as aggressive-flow pressure (1-min, not the hourly funding proxy)
- `impact_bid_px`/`impact_ask_px` spread as a liquidity-stress measure
- OI concentration and OI/volume ratio as crowding measures
- Per-user funding payments from `misc_events_by_block` (`user`, `coin`, `funding_amount`,
  `szi`) — account-level positioning, pairs with the existing `whale_tracker.py`

All must clear the Phase 1 gates including Gate 5 and the FDR correction.

### Track C — LP fee capture revival (BUILT, DORMANT)

~2,900 LOC already exists and is still wired into the live tick loop (`api.py:3180`):
`lp_range_calculator`, `lp_fee_manager`, `lp_rebalance`, `lp_monitor`, `lp_pool_scanner`,
`lp_paper_engine`, `lp_live_engine`, plus an 842-line UI page and a migration. It survived
two real loss incidents with a genuine root-cause postmortem (`afdb9eb`, the $12k IL wipe
from a decimals bug) and shipped six safeguards.

Known rot to fix before reviving:
- `pool_screening._il_penalty()` takes no arguments and hardcodes `r = 1.1` — always
  returns exactly `-15`. The IL term contributes zero discrimination.
- The entire `/pools/*` API surface still queries decommissioned Graph endpoints with an
  empty key (`api.py:3617-3628, 3801-3812`). Commit `667021a` migrated the *bot* to
  RPC + GeckoTerminal and never fixed the API/UI path.
- Confirm whether `lp_auto_enabled` is on in the running service (unverified).

This is structurally the same business as the Polymarket market maker — passive fee
capture with inventory management, no directional call — and it is permissionless.

## Phase 3 — Deployment discipline

- New wallet `paper_perp_v4`, mechanical-only, per the Multi-Wallet Evolution Protocol in
  `CLAUDE.md`. Set `parent_wallet_id`, `generation`, `display_name`, thesis paragraph.
- **Zero LLM calls in the trade path.** The repo's own record: LLM-discretionary lost on
  every wallet. Keep the agents for reporting if wanted; nothing in the decision path.
  This also removes the DeepSeek burn that paused the droplet on 2026-06-07.
- Forward-test ≥3 months before capital. Rare-firing edges reach small n fast.

---

## What this plan explicitly does NOT do

- No more OHLCV price-pattern searches. Phases 1-13 settled that question.
- No Polymarket build. Ontario blocks order placement at the API layer (measured:
  `{"blocked":true,"region":"ON"}`), the strategy is maker-side and unbacktestable in this
  repo (no fill model, no queue model, no stored book), and the taker fee at the money is
  3.5% of capital — 35× the cost assumption every WolfPack edge was validated against.
  An edge of funding-z's magnitude (+0.49%/trade) loses to that fee by 7×.
- No new LLM agents.

## Open questions for the user

1. Track priority — A (carry) first, or revive C (LP) in parallel since it is already built?
2. Is `lp_auto_enabled` currently on, and is there live capital in any LP position?
3. Capital available and max acceptable drawdown — sizing and Kelly fraction depend on it.
4. Is a delta-neutral carry trade acceptable given it needs spot inventory on a second
   venue, or should Track A stay perp-only (directional funding-z, hardened)?
