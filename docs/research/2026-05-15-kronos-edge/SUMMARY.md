# Kronos edge research — summary

**Date:** 2026-05-15 EDT
**Scope:** 7 hypotheses tested on BTC/ETH/LINK 1h+4h perps. 90d in-sample → 30d OOS → full-history reality check.
**Bottom line:** Zero strategies produced defensible multi-year edge after costs. Two looked good on 90 days, both collapsed on the full backtest. Fine-tune (in progress) is the last open door.

---

## What was tested

| # | Idea | Result on 90d | Result OOS / multi-year |
|---|---|---|---|
| 1 | Direct Kronos strategy (sign of 24h pred) | Sharpe 2-3 on 1h, dead on 4h | **Lost on 2/3 OOS**; not robust |
| 2 | Predict-vs-realize divergence | Weak mean-reversion bias at p95+ surprise | Small magnitudes; not standalone |
| 3 | Probability-of-touch (Monte Carlo) | _in progress (~20 min)_ | _pending_ |
| 4 | Tokenizer perplexity anomaly | Long winrate 47-56% across all quintiles | Vol clustering only; no alpha |
| 5 | Multi-TF coherence (1h × 4h agree) | Mixed; BTC inverted (disagree wins) | Noise (n=16-45) |
| 6 | Fine-tune Kronos on perp history | _queued (3-6h GPU)_ | _pending_ |
| 7 | Bollinger MR (classical / vol-norm / Kronos-gated) | Sharpe 6-9, beat HODL on 2/3 OOS | **−99% over 9yr**; bull-market killer |

---

## The 90-day mirage

These looked real and exciting:

```
ETH Bollinger vol-norm, 30d OOS: +32.03% vs HODL −1.75% (beat HODL by 33.78%)
BTC Bollinger vol-norm, 30d OOS: +11.26% vs HODL +8.04%
LINK Kronos direct,     full 90d: +40.18% vs HODL +12.84%, Sharpe 3.45
BTC Kronos direct,      full 90d: +20.54% vs HODL +14.38%, Sharpe 2.77
```

## The multi-year reality

Same winning Bollinger config applied to 7-9 years of 1h history:

```
BTC vol-norm L=100 thr=2.5 H=24:  −99.999% total vs HODL +1898%  (716 trades)
ETH vol-norm L=100 thr=2.5 H=24:  −99.999% total vs HODL +608%   (710 trades)
LINK vol-norm L=100 thr=2.5 H=24: −97.27%  total vs HODL +2112%  (593 trades)
```

Year-by-year, the strategy was positive in 4 of 25 symbol-years — and **three of those four positive years are 2026 YTD**, the same regime our 90d test happened to sample. The strategy works only in a specific recent chop pattern. Every bull-market year is a wipeout.

Param-sweep across full history × 54 configs × 3 symbols → zero configs beat HODL. Best Sharpe on full history is roughly −0.31. No knob recovers it.

## Regime-segmented (does ANY slice work?)

BTC: zero positive (regime × direction) buckets.
ETH: 1 positive — BEAR shorts +29.75% Sharpe 8.84 over 20 trades (small sample, possible chance).
LINK: 3 positive — BULL longs Sharpe 3.04 (n=30), BEAR shorts Sharpe 2.12 (n=23), SIDEWAYS longs Sharpe 1.70 (n=75). All small samples; across 27 buckets you'd expect ~1-2 false positives by chance.

Nothing here is a defensible production rule.

## What Kronos itself can / can't do

- **Inference is fast and reliable**: 0.45s per 24-candle forecast on RTX 3060 with 136 MB VRAM. The infra works.
- **Shape coherence is real**: forecasts visibly track recent regime; no NaN, no nonsense.
- **Direction agreement on individual windows is sometimes high (22/24 = 92% on the original sanity check)** — but this **does not translate to edge** when traded systematically across many windows. High per-window direction accuracy and zero strategy alpha can coexist when most predicted moves are small and the system is whipsawed on the few large ones.
- **Out-of-the-box, Kronos has no edge that survives costs on BTC/ETH/LINK 1h.**

## What killed each strategy specifically

- **Idea #1 (direct Kronos)**: cost-induced bleed. Kronos's predicted-direction win rate is ~50-55% — barely enough to overcome 17 bps per round trip × 60-70 trades per 90 days.
- **Idea #7 (Bollinger MR)**: directional asymmetry of crypto. Shorts during bull markets are catastrophic; the MR signal entries get steamrolled by trends. Vol-norm sizing makes the wipeout worse, not better, because it *increases* size during low-vol periods that often precede explosive moves.
- **Idea #2 / #4 / #5**: signals exist but their magnitudes don't clear costs.

## What's still open

1. **Idea #3 — probability-of-touch** (running). Won't give a strategy directly, but could improve stop-placement / sizing for OTHER strategies if Kronos's predicted high/low calibrate to realized.
2. **Idea #6 — fine-tuned Kronos** (queued). Base Kronos was trained on 45 exchanges of mixed data — mostly equities. Fine-tuning on 8 years of perp history *might* fix the cost-overhead problem if it produces sharper directional confidence. Realistic expectation: maybe 5-10% win-rate improvement, which is the difference between losing slightly and breaking even.
3. **Funding-rate harvest (Phase 6/8 from prior work)**. Not Kronos-related, but **the only signal in your 13-phase research history that produced statistically meaningful edge** (Sharpe 4.56 on BTC in BEAR regime). It was never built into a wallet. This is the real revisit candidate.
4. **Combine fine-tuned Kronos as an entry filter on top of funding-rate harvest**. Kronos confirms direction, funding-rate provides the alpha. Path to test only if Idea #6 produces directional improvement.

## Recommended next moves

After Idea #3 + #6 land:

A. **If fine-tune doesn't materially change Kronos behavior**: stop pursuing Kronos-as-strategy. Use it as Sage agent context only (the original install plan), or shelve entirely.

B. **Pivot back to funding-rate harvest** (Phase 6/8 result). Build a paper_perp_v4 with funding-z-low → long as the primary signal, optionally using Kronos to gate entries (e.g., only enter if Kronos doesn't predict a big down move). This is the highest-prior path you have on real edge.

C. **Do not deploy Bollinger MR to a wallet.** Not in any form. The 90d window was a regime artifact.

D. **Do not deploy Kronos direct to a wallet.** OOS collapsed.

## The honest verdict

Three days of intensive testing replicated the lesson from your 13-phase backtest sweep: **OHLCV alone does not contain reliable edge in crypto perps over multi-year horizons.** The funding-rate signal you found previously is still the only real candidate. Kronos is a competent forecasting tool but, as a foundation model trained on broad data, it cannot manufacture alpha that the underlying price series doesn't carry.

What it *can* do (after fine-tune verification): become a high-quality input to a richer signal stack (regime detection, divergence flags, sizing inputs). Not a standalone strategy.

---

_Status of in-flight jobs: Idea #3 ~80% complete; Idea #6 fine-tune queued (will start when Idea #3 frees GPU). Final results + production recommendation will overwrite this file._
