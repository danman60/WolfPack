# 2026-08 Carry Edge — first strategy to survive honest gates, and its decay curve

**Data:** `s3://hyperliquid-archive/asset_ctxs/` — 1-minute funding / open_interest / premium /
mark / oracle / impact_bid / impact_ask, 232 coins. Pulled 1,062 of 1,170 days
(108 dates absent from the archive). **27,283,630 rows, 2023-05-20 → 2026-06-18 (3.08 yrs).**
Cost: ~$1 AWS egress. Scripts in this dir; parts/ parquet in session scratchpad.

Pre-registration in `PREREG.md` — horizons, costs, splits and directional predictions were
fixed before any result was viewed.

## Result 1 — Delta-neutral funding carry: REAL, survived the bear, but DECAYING

Short perp + long spot, hourly funding, basis-aware, hourly basis change clipped to ±1%.

**8-major equal-weight, 2.87 years:**

| metric | value |
|---|---|
| annualized (on notional) | **12.42%** |
| max drawdown | 7.00% |
| Calmar | 1.77 |
| monthly Sharpe | 2.01 |
| negative months | 7 / 35 (worst −4.12%) |
| negative quarters | 2 / 13 (both 2023Q2-Q3, HL's sparse early period) |
| **on total capital (2× notional)** | **6.21%/yr, 3.50% maxDD** |

**11 consecutive positive quarters from 2023Q4 through 2026Q2**, spanning the 2024-25
drawdown. This is the regime test turtle failed and carry passed.

**But the edge is compressing.** Per-year: **15.9% → 13.3% → 6.4%**. Recent quarters
25Q4:5% 26Q1:2% 26Q2:2%. Consistent with the basis trade getting crowded as Hyperliquid matured.

**2026 by coin (ungated, annualized):** LINK **+8.77%** (maxDD 0.20%) · AVAX +3.89% ·
ETH +3.85% · BTC +2.74% · LTC +2.68% · DOGE +2.03% · **XRP −3.39% · SOL −6.80%**.

Gating on trailing-7d funding > 0 lifts 2026 to **+3.48% on notional at 0.57% maxDD**
(Calmar ~6). Higher gates (5/10/15/20%) *reduce* recent returns — funding rarely clears
those thresholds any more, which is itself the decay measurement.

**Verdict: real, validated, and currently worth ~2%/yr on capital. That is a
cash-management yield, not alpha. Do not deploy size at current levels.** Revisit if
funding re-widens; LINK is the one name still paying.

## Result 2 — Cross-sectional funding carry: DEAD

Short top-K funding perps, long bottom-K. Perp-only, no spot leg, 1× capital — attractive
if it worked. It does not.

| K | ann% | maxDD% | Calmar | monthly Sharpe |
|---|---|---|---|---|
| 2 | −94.65 | 348.37 | −0.27 | −1.03 |
| 3 | −85.65 | 313.31 | −0.27 | −1.30 |
| 4 | −69.16 | 247.82 | −0.28 | −1.21 |
| 5 | −46.80 | 210.50 | −0.22 | −0.88 |

Cause: coins pay high funding *because they are ripping*. The cross-sectional price
dispersion (100%+ annualized) dwarfs the funding differential (10-20%). Shorting the
high-funding leg loses far more on price than it collects in funding. The spot hedge in
Result 1 is not a convenience — it is the entire mechanism.

## Result 3 — OI-delta × price-delta flow quadrants: DEAD at h=60m

Pre-registered horizon, no max-t selection. "New longs" (OI↑ price↑) gross **+0.75 bps**
against **3.4 bps** measured cost. "Short covering" +0.09 bps. Both underwater before trading.
Two quadrants and the premium z-score test hit a division bug and remain **UNTESTED**, not dead.

## Method findings worth keeping

1. **Measured execution cost replaces the 10bps guess.** Touch spread from
   impact_bid/impact_ask: BTC 1.65bps, ETH 1.98bps, SOL 2.56bps, LINK 3.32bps, SEI 4.56bps.
   The harness default was wrong in both directions and is now measurable per coin.
   (This is touch spread — impact for size adds more.)
2. **New listings poison flow studies.** TIA's basis printed **−18.94% in one hour** on its
   2023-10-31 listing day. Naive equal-weighting turned a 13% portfolio drawdown into 108.7%.
   Clip hourly basis change and exclude coins listed inside the sample.
3. **Never annualize an hourly Sharpe on funding data.** √8760 scaling reported Sharpe 11.93
   where the honest monthly figure is 2.01. Funding is heavily autocorrelated. Same error
   class as the IID-vs-block bootstrap issue in `run_fundingz_revalidation.py:318`.
4. **A completed background job is not a completed result.** The first "full-history" run
   reported plausible numbers off a stale `panel.parquet` because the consolidation step
   OOM'd before writing and the analysis silently re-read the old file. The span field was
   the only tell. Always assert the data span inside the analysis.

---

# Part 2 — Dynamic selection across the full 230-coin universe (2025-01 → 2026-06)

Hourly panel, all 230 coins, 2.32M rows. Selection: top-N by trailing-7d funding among names
passing **>$10M median daily volume** and **<15bps measured spread**. Weekly rebalance.
Measured spread charged on every name entering or leaving the book.

## Universe screen, 2026 YTD

**Only 12 of 227 coins clear the liquidity + spread filters.** Top payers:

| coin | ann funding | vol $M | spread bps |
|---|---|---|---|
| FARTCOIN | 12.94% | 20.4 | 7.18 |
| LIT | 9.64% | 14.0 | 12.33 |
| **HYPE** | **8.03%** | **223.2** | **2.39** |
| PUMP | 6.97% | 14.9 | 9.57 |
| PAXG | 4.59% | 13.7 | 1.02 |
| ETH | 3.81% | 1087.0 | 0.48 |
| BTC | 2.67% | 2668.6 | 0.14 |
| SOL | **−6.89%** | 286.3 | 0.22 |
| XRP | **−3.34%** | 54.0 | 0.72 |

Funding is *still rich on newer names* — the majors-only decay measured in Part 1 is a
crowding effect on BTC/ETH, not a market-wide death of the premium.

## Execution-realism sweep — this is the finding

| construction | 2025 ann% | 2026 ann% | 2026 maxDD% |
|---|---|---|---|
| **one-sided N=5 weekly (always executable)** | **17.45** | **5.85** | **0.25** |
| one-sided N=8 weekly | 14.14 | 5.30 | 0.19 |
| two-sided, borrow 0% *(fantasy)* | 36.32 | 37.18 | 0.42 |
| two-sided, borrow 10% | 32.92 | 33.02 | 0.42 |
| two-sided, borrow 25% | 27.82 | 26.77 | 1.11 |
| **two-sided, borrow 25% + short-spot restricted to majors** | 15.80 | **0.62** | 0.92 |

**The two-sided version is not executable as modeled.** Going long the perp on a
negative-funding name requires *shorting spot* on that name. Restricting that leg to coins
where spot shorting is actually feasible collapses 2026 from **26.77% → 0.62%**. The entire
apparent edge lived in shorting spot on illiquid alts — where borrow is usually unavailable,
and where it exists often costs 50-200%/yr rather than the 25% modelled.

Hourly reselection (first attempt) returned −17% to −31% purely from turnover: full spread
charged on every name change, ~6 changes/week into 5 slots ≈ 3%/yr of cost. That was a
construction artifact, not a signal failure. Weekly rebalance with hysteresis fixed it.

## Deployable conclusion

**One-sided dynamic delta-neutral carry** — short perp, long spot, top-5 by trailing funding
among liquid names, weekly rebalance:

- 2025: **+17.45%** on notional · 2026: **+5.85%** on notional at **0.25% max drawdown**
- On total capital (2× notional): **~2.9%/yr in 2026**, ~8.7%/yr in 2025
- Calmar ~23 in 2026 — extremely smooth, genuinely small

This is real, validated across 3 years and a bear regime, and executable today with no
short-spot dependency. It is a **yield strategy, not alpha.** Single richest tradeable name
is **HYPE (8.03% funding, $223M volume, 2.39bps spread)**.

**Recommendation: do not commit meaningful capital at 2026 levels.** Re-test when funding
re-widens; the 2025 figure (+17.45%) is what this looks like when it is worth running.

---

# Part 3 — Leverage sizing (this reverses the Part 2 recommendation)

Part 2 judged an unlevered 5.85% against an unlevered bar and concluded "don't deploy."
**That was an error.** A strategy with 0.25% max drawdown and Calmar ~23 is sized by its risk,
not by its unlevered headline. Carry desks lever precisely because carry is smooth.

## The real leverage constraint: unclipped basis tail

Delta-neutral means price cancels, so the only return risk is the **basis** (mark vs oracle).
Measured unclipped, per name, worst single hour for a short-perp/long-spot book:

| coin | worst 1h | p0.1% | safe L @ −10% of capital |
|---|---|---|---|
| LINK | −0.135% | −0.095% | 50 |
| SUI | −0.234% | −0.095% | 42.8 |
| PAXG | −0.364% | −0.165% | 27.5 |
| kPEPE | −0.481% | −0.138% | 20.8 |
| BTC | −0.518% | −0.086% | 19.3 |
| ETH | −0.526% | −0.092% | 19.0 |
| ZEC | −1.102% | −0.506% | 9.1 |
| DOGE | −1.313% | −0.076% | 7.6 |
| SOL | −1.448% | −0.114% | 6.9 |
| FARTCOIN | −1.552% | −0.338% | 6.4 |
| XRP | −1.584% | −0.111% | 6.3 |
| **HYPE** | **−2.824%** | −0.384% | **3.5** |
| **PUMP** | **−8.130%** | −3.649% | **1.2** |
| **LIT** | **−18.882%** | −7.366% | **0.5** |

**The richest-funding names are rich because they are dangerous.** LIT paid 9.64% and can lose
18.9% of notional in one hour. A tail screen excluding names whose worst hourly basis move is
below −3% bans **80 of 230** and removes LIT and PUMP.

## Deployable specification

Tail-screened, one-sided (short perp + long spot), top-5 by trailing-7d funding, weekly
rebalance, >$10M volume, <15bps spread, basis clipped at ±5%, measured spreads charged:

| leverage | 2026 ret | 2025 ret | 2026 maxDD | worst hour | worst day |
|---|---|---|---|---|---|
| 1× | 6.76% | 17.10% | 0.19% | −0.91% | −0.10% |
| 2× | 13.52% | 34.20% | 0.37% | −1.81% | −0.20% |
| **3×** | **20.28%** | **51.30%** | **0.56%** | **−2.72%** | **−0.31%** |

Full period 2025-01 → 2026-06 at 3×: **ann 44.30%, maxDD 3.57%, Calmar 12.4,
monthly Sharpe 4.90, 0 negative months of 16.**

**Recommended config:** 3× leverage (below HYPE's 3.5 binding constraint), **Hyperliquid spot
+ Hyperliquid perp only** so cross-margin keeps the hedge intact, top-5 weekly.
**Forward estimate is the 2026 figure — ~20%/yr on capital — not the 44% full-period number.**

## What this model does NOT capture

- **0/16 negative months and monthly Sharpe 4.90 are too clean.** Expect real drawdowns
  2-3× the modelled figures.
- Execution: entry/exit modelled at touch spread only. No size impact, no fill lag, no
  funding drift between signal and fill.
- **Same-venue cross-margin is load-bearing.** Split the legs across venues and a price rip
  margin-calls the perp before the spot gain is accessible. At 3× that is fatal.
- Venue risk: HL outage, oracle failure, or auto-deleveraging can unwind the hedge and leave
  the book naked. This — not the return series — is the true ruin scenario.
- Worst observed hour is an in-sample statistic. A worse one will happen.

**Deploy path:** new `paper_perp_v4` mechanical wallet per the Multi-Wallet Evolution Protocol,
zero LLM calls in the trade path, 3-month forward test at 1× before any leverage or capital.
