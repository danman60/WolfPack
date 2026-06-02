# Turtle/Donchian Breakout Sweep — period 20 vs 30/40/55, regime-gated vs not

Real BacktestEngine + real TurtleDonchianStrategy + real MonteCarloEngine. RESEARCH ONLY — no live logic touched.

**Config:** interval=4h, ATR(20)x2.0 stop, SMA(200) trend filter, ADX-proxy>25.0 = trending, start_equity=$25000, fees 5.0/5.0 bps.

Variant **nofilter** = macro_regime=None (both directions; SMA trend filter intrinsic to module). Variant **gated** = per-bar TRENDING gate injected (longs above SMA200 in uptrend, shorts below in downtrend).

## Coverage

| symbol | candles | start | end | days |
|---|---|---|---|---|
| BTC | 5001 | 2024-02-18 | 2026-06-01 | 833 |
| ETH | 5001 | 2024-02-18 | 2026-06-01 | 833 |
| LINK | 5001 | 2024-02-18 | 2026-06-01 | 833 |

## BTC

### BTC — nofilter

| period | n | ret% | exp$/tr | WR% | avgWin$ | avgLoss$ | R:R | PF | maxDD% | L/S |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 32 | +2.2 | +24.9 | 21.9 | +449 | -94 | 4.79 | 1.34 | 6.74 | 32/0 |
| 30 | 30 | +2.8 | +27.4 | 20.0 | +524 | -97 | 5.42 | 1.35 | 6.63 | 30/0 |
| 40 | 27 | +2.7 | +32.5 | 18.5 | +608 | -98 | 6.19 | 1.41 | 5.98 | 27/0 |
| 55 | 26 | +2.0 | +27.0 | 19.2 | +540 | -95 | 5.68 | 1.35 | 5.61 | 26/0 |

### BTC — gated

| period | n | ret% | exp$/tr | WR% | avgWin$ | avgLoss$ | R:R | PF | maxDD% | L/S |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 30 | +2.9 | +30.9 | 20.0 | +525 | -93 | 5.66 | 1.42 | 6.45 | 30/0 |
| 30 | 28 | +3.5 | +34.0 | 17.9 | +631 | -96 | 6.59 | 1.43 | 6.34 | 28/0 |
| 40 | 25 | +3.5 | +46.1 | 20.0 | +610 | -95 | 6.42 | 1.61 | 5.68 | 25/0 |
| 55 | 24 | +2.7 | +31.0 | 20.8 | +542 | -103 | 5.24 | 1.38 | 5.32 | 24/0 |

## ETH

### ETH — nofilter

| period | n | ret% | exp$/tr | WR% | avgWin$ | avgLoss$ | R:R | PF | maxDD% | L/S |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 29 | +11.0 | +92.4 | 20.7 | +983 | -140 | 7.02 | 1.83 | 6.87 | 29/0 |
| 30 | 23 | +12.9 | +127.5 | 26.1 | +963 | -168 | 5.75 | 2.03 | 6.73 | 23/0 |
| 40 | 27 | +8.1 | +70.5 | 18.5 | +1058 | -154 | 6.87 | 1.56 | 8.82 | 27/0 |
| 55 | 24 | +7.8 | +77.4 | 16.7 | +1252 | -158 | 7.95 | 1.59 | 8.75 | 24/0 |

### ETH — gated

| period | n | ret% | exp$/tr | WR% | avgWin$ | avgLoss$ | R:R | PF | maxDD% | L/S |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 35 | +6.1 | +51.4 | 14.3 | +1125 | -128 | 8.82 | 1.47 | 11.45 | 35/0 |
| 30 | 28 | +8.0 | +72.0 | 17.9 | +1090 | -149 | 7.3 | 1.59 | 9.85 | 28/0 |
| 40 | 26 | +8.8 | +82.4 | 19.2 | +1064 | -151 | 7.03 | 1.67 | 8.85 | 26/0 |
| 55 | 23 | +8.5 | +91.1 | 17.4 | +1259 | -155 | 8.13 | 1.71 | 8.78 | 23/0 |

## LINK

### LINK — nofilter

| period | n | ret% | exp$/tr | WR% | avgWin$ | avgLoss$ | R:R | PF | maxDD% | L/S |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 48 | -9.1 | -41.4 | 10.4 | +848 | -145 | 5.86 | 0.68 | 22.23 | 48/0 |
| 30 | 42 | -7.9 | -40.7 | 11.9 | +798 | -154 | 5.18 | 0.7 | 19.67 | 42/0 |
| 40 | 34 | -5.5 | -29.8 | 11.8 | +861 | -149 | 5.8 | 0.77 | 17.02 | 34/0 |
| 55 | 30 | -4.1 | -20.4 | 10.0 | +1089 | -144 | 7.58 | 0.84 | 16.09 | 30/0 |

### LINK — gated

| period | n | ret% | exp$/tr | WR% | avgWin$ | avgLoss$ | R:R | PF | maxDD% | L/S |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 44 | -7.2 | -37.1 | 11.4 | +820 | -147 | 5.58 | 0.72 | 21.08 | 44/0 |
| 30 | 40 | -7.0 | -38.2 | 12.5 | +774 | -154 | 5.02 | 0.72 | 18.9 | 40/0 |
| 40 | 33 | -4.9 | -29.9 | 12.1 | +863 | -153 | 5.64 | 0.78 | 16.51 | 33/0 |
| 55 | 29 | -3.5 | -20.1 | 10.3 | +1092 | -148 | 7.36 | 0.85 | 15.57 | 29/0 |

## Best cell per symbol + Monte Carlo (5000 sims, block bootstrap)

| symbol | best cell | n | exp$/tr | ret% | MC p5 ret% | MC median% | prob(profit)% | ruin% | grade |
|---|---|---|---|---|---|---|---|---|---|
| BTC | p40_gated | 25 | +46.1 | +3.5 | -5.2 | +4.6 | 74.9 | 0.0 | marginal |
| ETH | p30_nofilter | 23 | +127.5 | +12.9 | -2.5 | +13.9 | 90.5 | 0.0 | marginal |
| LINK | p55_gated | 29 | -20.1 | -3.5 | -13.3 | -1.5 | 41.8 | 0.0 | poor |

## VERDICT

- BTC nofilter: p20 exp=$+24.9 (n=32) vs p55 exp=$+27.0 (n=26) -> gap $+2.1/trade [55 WINS]
- BTC gated: p20 exp=$+30.9 (n=30) vs p55 exp=$+31.0 (n=24) -> gap $+0.2/trade [55 WINS]
- ETH nofilter: p20 exp=$+92.4 (n=29) vs p55 exp=$+77.4 (n=24) -> gap $-15.0/trade [20 wins]
- ETH gated: p20 exp=$+51.4 (n=35) vs p55 exp=$+91.1 (n=23) -> gap $+39.7/trade [55 WINS]
- LINK nofilter: p20 exp=$-41.4 (n=48) vs p55 exp=$-20.4 (n=30) -> gap $+21.0/trade [55 WINS]
- LINK gated: p20 exp=$-37.1 (n=44) vs p55 exp=$-20.1 (n=29) -> gap $+17.0/trade [55 WINS]

### Determination

**Does 55 beat 20?** Weakly. 55 wins 5 of 6 symbol/variant comparisons but the edge is small and the single best-expectancy cells sit at period 30-40, not 55:
- BTC: 55 ~= 20 (gap +$2.1 nofilter, +$0.2 gated — a wash). Best BTC cell is p40_gated.
- ETH: 20 wins nofilter (-$15/tr for 55), 55 wins decisively gated (+$39.7/tr). Best ETH cell is p30_nofilter.
- LINK: 55 wins both variants (+$21/+$17/tr) but LINK is net-LOSING at every period.
- Consistent across symbols: longer period raises R:R (5.x -> 7.x) and cuts max-DD. That part of the prior claim holds; the "55 specifically is best" part does not — 30-40 is the sweet spot here.

**Does regime-gating help?** Marginally, inconsistently. BTC: gated > nofilter at every period (p40_gated $+46 vs p40_nofilter $+32). ETH: gating HURT short periods (p20 $+92 -> $+51) but helped p55. LINK: no meaningful change to a losing strategy. Net positive on BTC, mixed on ETH, irrelevant on LINK.

**PASS/FAIL** (PASS = best long period positive expectancy AND MC 5th-pct near/positive):
- BTC — PASS (marginal). p40_gated: exp +$46/tr, +3.5% over 27mo, MC p5 -5.2%, prob(profit) 74.9%, ruin 0%.
- ETH — PASS. p30_nofilter: exp +$128/tr, +12.9%, MC p5 -2.5%, prob(profit) 90.5%, ruin 0%. Strongest cell; period 30, not 55.
- LINK — FAIL. Every cell net-negative. Best (p55_gated) -$20/tr, -3.5%, MC p5 -13.3%, prob(profit) 41.8%.

**Caveats:**
- Low sample size: 23-48 trades per cell over 27 months. MC p5 is negative on every best cell (none clear zero at 5th-pct), so "survives MC" is true only in the soft sense (prob(profit) > 50% on BTC/ETH, ruin 0%).
- Low win rate (10-26%) — pure breakout profile; expectancy carried by a few 5-8x R:R winners. Fragile to missing one big winner.
- LINK fired 100% longs, 0 shorts (48/0 etc.) under the SMA200 filter — directional exposure, not a balanced long/short test.
- 4h interval, single 2024-02 -> 2026-06 window (one regime sequence). Not multi-window walk-forward.
