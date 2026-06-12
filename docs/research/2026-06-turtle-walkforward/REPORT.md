# Turtle/Donchian Walk-Forward Validation — BTC/ETH, 4h + 1d

**Date:** 2026-06-12. **Run:** `run_walkforward.py` -> `walkforward_results.json` (`run.log` has full output, 77.8s).
**Harness:** identical to `docs/research/2026-06-turtle-regime/` — real `BacktestEngine` + real `TurtleDonchianStrategy` + per-bar ADX/SMA200 regime-gated wrapper + real `MonteCarloEngine`. RESEARCH ONLY — no live code, wallet config, or strategies/ touched.
**Data:** Hyperliquid `candleSnapshot` direct (intel API on droplet refused connections on :8000 at run time; same upstream source). 4h: 5001 candles 2024-02-29 -> 2026-06-12 (BTC+ETH). 1d: 2124 candles 2020-08-19 -> 2026-06-12 (BTC+ETH). No short-history truncation.
**Costs:** default 10bps (5 commission + 5 slippage, same as prior sweep); stress 15bps. **Grid:** p in {20..55 step 5} x {nofilter, gated}. Selection: IS expectancy, PF tiebreak, n>=10.

## VERDICT (PASS = OOS exp > 0 AND OOS PF > 1.2 AND no parameter-neighborhood cliff)

| symbol | interval | IS-best (frozen) | OOS exp $/tr | OOS PF | OOS ret% | OOS n | neighborhood | VERDICT |
|---|---|---|---|---|---|---|---|---|
| BTC | 4h | p45_gated | **-63.0** | **0.30** | -2.4 | 10 | all 4 neighbors negative (PF 0.29-0.31) | **FAIL** |
| ETH | 4h | p30_gated | **-22.2** | **0.81** | -2.2 | 15 | all 4 neighbors negative (PF 0.67-0.94) | **FAIL** |
| BTC | 1d | p20_nofilter | +66.4 | 1.44 | +1.3 | **6** | smooth, all positive (p10 +116 / p25 +96 / p30 +334) | **PASS on criteria — INCONCLUSIVE (n=6, MC unrunnable)** |
| ETH | 1d | p20_nofilter | +153.4 | 2.36 | +2.2 | **4** | **cliff**: p25 +1.6 (PF 1.01), p30 -57.5 (PF 0.62) | **FAIL** |

**Does the prior single-window result hold OOS? NO (BTC), MOSTLY NO (ETH).**
- BTC prior best cell (p40_gated, +3.5% / PF 1.61 single-window) run frozen on the OOS window: **-$53.5/tr, PF 0.31, -2.7%, n=11.** Dead.
- ETH prior best cell (p30_nofilter, +12.9% / PF 2.03 single-window) run frozen on OOS: **+$78.4/tr, PF 1.70, +2.9%, n=9.** Survives weakly, BUT: (a) IS optimization would NOT have selected it — it picked p30_gated, which lost -$22/tr OOS; (b) nofilter neighborhood cliffs at p35 (-$23.0, PF 0.80) and p40 (-$7.3, PF 0.94); (c) n=9 < 10, Monte Carlo unrunnable. The prior +12.9% was carried by the IS bull window.
- The MC-flagged regime-luck risk (negative 5th percentile on every best cell) is **CONFIRMED**.

## 1a. Anchored 60/40, 4h (IS 2024-02-29 -> 2025-07-13, OOS 2025-07-13 -> 2026-06-12)

### BTC 4h — IS grid (3000 bars)

| cell | n | exp $/tr | PF | ret% | | cell | n | exp $/tr | PF | ret% |
|---|---|---|---|---|---|---|---|---|---|---|
| p20_nofilter | 19 | +97.4 | 2.51 | +6.8 | | p20_gated | 17 | +116.9 | 2.80 | +7.5 |
| p25_nofilter | 19 | +91.1 | 2.29 | +6.5 | | p25_gated | 17 | +109.8 | 2.53 | +7.2 |
| p30_nofilter | 17 | +114.4 | 2.71 | +7.5 | | p30_gated | 15 | +138.8 | 3.05 | +8.2 |
| p35_nofilter | 16 | +115.9 | 2.52 | +7.0 | | p35_gated | 14 | +152.6 | 3.25 | +7.8 |
| p40_nofilter | 16 | +110.1 | 2.45 | +6.7 | | p40_gated | 14 | +146.0 | 3.16 | +7.5 |
| p45_nofilter | 14 | +147.8 | 2.89 | +8.0 | | **p45_gated** | 13 | **+174.9** | **3.51** | +8.5 |
| p50_nofilter | 16 | +117.2 | 2.70 | +6.7 | | p50_gated | 14 | +146.0 | 3.16 | +7.5 |
| p55_nofilter | 16 | +100.8 | 2.58 | +5.5 | | p55_gated | 14 | +118.5 | 2.68 | +6.2 |

**BTC 4h OOS (frozen p45_gated):** n=10, exp **-$63.0/tr**, ret **-2.4%**, PF **0.30**, WR 10.0%, maxDD 3.97%.

### ETH 4h — IS grid (3000 bars)

| cell | n | exp $/tr | PF | ret% | | cell | n | exp $/tr | PF | ret% |
|---|---|---|---|---|---|---|---|---|---|---|
| p20_nofilter | 18 | +96.5 | 1.93 | +7.1 | | p20_gated | 15 | +149.7 | 2.60 | +9.2 |
| p25_nofilter | 17 | +105.5 | 1.98 | +7.9 | | p25_gated | 15 | +139.6 | 2.35 | +9.2 |
| p30_nofilter | 14 | +132.6 | 2.16 | +8.6 | | **p30_gated** | 13 | **+160.0** | 2.49 | +9.3 |
| p35_nofilter | 14 | +127.0 | 2.11 | +8.4 | | p35_gated | 13 | +153.9 | 2.43 | +9.1 |
| p40_nofilter | 14 | +123.7 | 2.06 | +8.3 | | p40_gated | 13 | +150.4 | 2.38 | +9.0 |
| p45_nofilter | 13 | +124.3 | 2.11 | +7.6 | | p45_gated | 12 | +153.1 | 2.47 | +8.4 |
| p50_nofilter | 13 | +120.7 | 2.05 | +7.2 | | p50_gated | 12 | +149.2 | 2.40 | +7.9 |
| p55_nofilter | 13 | +120.7 | 2.05 | +7.2 | | p55_gated | 12 | +149.2 | 2.40 | +7.9 |

**ETH 4h OOS (frozen p30_gated):** n=15, exp **-$22.2/tr**, ret **-2.2%**, PF **0.81**, WR 6.7%, maxDD 9.51%.

## 1b. Rolling expanding-window folds, 4h (4 folds x 540 bars ~ 3 months each)

### BTC 4h

| fold | train end | test window | IS-best | OOS n | OOS exp $/tr | OOS ret% | OOS PF |
|---|---|---|---|---|---|---|---|
| 1 | 2025-06-17 | 2025-06-17 -> 2025-09-15 | p35_gated | 4 | -6.8 | -0.2 | 0.76 |
| 2 | 2025-09-15 | 2025-09-15 -> 2025-12-14 | p45_gated | 2 | -100.4 | -0.7 | 0.00 |
| 3 | 2025-12-14 | 2025-12-14 -> 2026-03-14 | p45_gated | 4 | -98.0 | -1.7 | 0.00 |
| 4 | 2026-03-14 | 2026-03-14 -> 2026-06-12 | p45_gated | 2 | +87.8 | +0.7 | 2.74 |

3 of 4 folds negative. IS-best drifts p35 -> p45.

### ETH 4h

| fold | train end | test window | IS-best | OOS n | OOS exp $/tr | OOS ret% | OOS PF |
|---|---|---|---|---|---|---|---|
| 1 | 2025-06-17 | 2025-06-17 -> 2025-09-15 | p30_gated | 2 | +1337.3 | +10.7 | 18.19 |
| 2 | 2025-09-15 | 2025-09-15 -> 2025-12-14 | p45_gated | 3 | -111.6 | -1.3 | 0.00 |
| 3 | 2025-12-14 | 2025-12-14 -> 2026-03-14 | p30_gated | 4 | -142.5 | -2.1 | 0.00 |
| 4 | 2026-03-14 | 2026-03-14 -> 2026-06-12 | p45_gated | 6 | -92.8 | -3.4 | 0.00 |

3 of 4 folds negative. IS-best oscillates p30 <-> p45 (unstable). Fold 1's +$1337/tr is n=2 — one large Jul-Aug 2025 winner; remove it and every ETH fold loses. Single-big-trade dependence.

## 1c. Parameter neighborhood (OOS, anchored frozen variant)

| symbol/interval | p*-10 | p*-5 | p* (frozen) | p*+5 | p*+10 | shape |
|---|---|---|---|---|---|---|
| BTC 4h (gated, p*=45) | p35 -54.2 / PF 0.29 | p40 -53.5 / PF 0.31 | **-63.0 / PF 0.30** | p50 -62.0 / PF 0.30 | p55 -62.0 / PF 0.30 | uniformly dead — no cliff, no edge |
| ETH 4h (gated, p*=30) | p20 -34.3 / PF 0.67 | p25 -31.4 / PF 0.72 | **-22.2 / PF 0.81** | p35 -22.2 / PF 0.81 | p40 -6.3 / PF 0.94 | uniformly negative |
| BTC 1d (nofilter, p*=20) | p10 +116.3 / PF 2.04 | p15 +66.4 / PF 1.44 | **+66.4 / PF 1.44** | p25 +95.5 / PF 1.86 | p30 +333.6 / PF 3.40 | smooth positive, but n=4-6/cell |
| ETH 1d (nofilter, p*=20) | p10 +108.0 / PF 1.63 | p15 +153.4 / PF 2.36 | **+153.4 / PF 2.36** | p25 +1.6 / PF 1.01 | p30 -57.5 / PF 0.62 | **cliff** above p20; n=4-5/cell |

ETH 4h nofilter family OOS (prior winner's family): p20 +53.5/PF 1.53, p25 +45.8/PF 1.42, p30 +78.4/PF 1.70, p35 **-23.0/PF 0.80**, p40 **-7.3/PF 0.94** — cliff between p30 and p35.
BTC 4h nofilter family OOS: p20..p40 all -$53 to -$62/tr, PF 0.24-0.31 — dead everywhere.

## 2. Anchored 60/40, 1d (IS 2020-08-19 -> 2024-02-13, OOS 2024-02-14 -> 2026-06-12)

- BTC 1d: IS-best p20_nofilter (+$275.1/tr, PF 2.23, n=6 IS). OOS: n=6, exp +$66.4, ret +1.3%, PF 1.44, WR 50%, maxDD 8.12%.
- ETH 1d: IS-best p20_nofilter (+$1151.5/tr, PF 999.99 — zero losers, n=4 IS). OOS: n=4, exp +$153.4, ret +2.2%, PF 2.36, WR 50%, maxDD 7.55%.
- **Low-n caveat is fatal:** 4-6 trades per cell IS and OOS (SMA200 warmup eats 201 days; daily Donchian fires rarely; engine holds one position at a time). Many grid cells produce identical trade lists. Nothing here is statistically distinguishable from noise; MC unrunnable (<10 trades) on both. The 1d numbers cannot validate or kill anything.

## 3. Cost stress (15bps, frozen OOS cells)

| cell | OOS exp 10bps | OOS exp 15bps | OOS PF 10bps | OOS PF 15bps |
|---|---|---|---|---|
| BTC 4h p45_gated | -63.0 | -65.9 | 0.30 | 0.29 |
| ETH 4h p30_gated | -22.2 | -25.6 | 0.81 | 0.78 |
| BTC 1d p20_nofilter | +66.4 | +63.7 | 1.44 | 1.42 |
| ETH 1d p20_nofilter | +153.4 | +150.8 | 2.36 | 2.33 |

Costs are not the story — the 4h cells are dead at any fee level.

## 4. Monte Carlo (OOS trade lists, block bootstrap, 5000 sims, same method as prior sweep)

| cell | n | prob(profit)% | p5 ret% | median ret% | grade |
|---|---|---|---|---|---|
| BTC 4h p45_gated | 10 | **0.0** | -3.89 | -3.45 | marginal |
| ETH 4h p30_gated | 15 | **2.4** | -9.09 | -7.29 | marginal |
| BTC 1d p20_nofilter | 6 | unrunnable (n<10) | - | - | - |
| ETH 1d p20_nofilter | 4 | unrunnable (n<10) | - | - | - |
| ETH 4h p30_nofilter (prior exact cell) | 9 | unrunnable (n<10) | - | - | - |

## Bottom line

- **The 27-month single-window Turtle edge was regime luck.** The entire IS edge sits in the 2024-02 -> 2025-07 leg. The 2025-07 -> 2026-06 OOS window kills both symbols at 4h: every gated cell and every BTC nofilter cell is negative; IS-optimized selection lost money in 3 of 4 rolling folds on both symbols.
- ETH retains a faint pulse only in the exact prior cell family (p20-p30 nofilter, OOS PF 1.4-1.7) — but walk-forward selection would never have found it, the family cliffs at p35, and n=9 max. Not deployable evidence.
- 1d intervals: BTC passes the numeric criteria with a smooth neighborhood but on 6 trades — inconclusive by construction.
- **Recommendation: do not promote Turtle BTC/ETH 4h to any wallet on the strength of the prior sweep.** The `project_turtle_edge` memory ("Turtle trend BTC/ETH = only validated edge") should be downgraded to "failed walk-forward OOS 2026-06-12".
