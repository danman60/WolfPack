# Moonshot Scalper — MECHANICAL-LEG Backtest

**Generated:** 2026-06-01T14:15:42.585130+00:00  
**Interval:** 15m (52.1d history)  •  **Universe:** 20 live HL small-cap perps (<$5M/24h, >=$250k)  
**Costs:** baseline = 30.0bps slip + 5.0bps comm = **35bps/side**; stress = 40.0+5.0 = **45bps/side**. Cost paid on BOTH entry and exit.

## What this is (and is NOT)
- **Tested:** the **mechanical chart-trigger leg only** — the moonshot screener's momentum/breakout entry gate (reusing `momentum_buckets` unmodified) run bar-by-bar, long-only, with fast TP / tight stop / max-hold exits.
- **NOT tested:** the buzz filter (no historical social-buzz data) and the 51 delisted perps (gone from the data). See survivorship section.

### KEY STRUCTURAL FINDING — the literal screener gate is dead
The screener's **literal `is_shot` gate** (regime==breakout AND momentum>=0.4 AND conviction>=0.5) fired **0 times across all 20 symbols over 52.1 days** — i.e. **zero tradeable signals**. This is *structural*, not a data gap: `momentum_buckets` only labels a bar `breakout` when the short window is fast but the long window is flat (`short_vel>0.3 & long_vel<0.1`), which mechanically caps the 4-window composite momentum_score at ~0.40 on exactly those bars. So `breakout AND momentum>=0.4` is near-impossible by construction. This matches the live screener (0/7 candidates ever passed `is_shot`). **The mechanical entry, as literally coded, produces no trade stream at all.**

To still answer *'does the breakout-quick-long idea have edge'*, three FAITHFUL interpretations of the screener's intent were backtested (they fire normally):

| gate | definition |
|---|---|
| `as_written` | regime==breakout AND mom>=0.4 AND conv>=0.5 (literal screener is_shot; STRUCTURALLY FIRES 0x) |
| `breakout_intent` | regime==breakout AND mom>0 AND conv>=0.5 (faithful: fresh confident upside breakout) |
| `breakout_uptrend` | regime==breakout AND primary_trend up/strong_up AND conv>=0.5 |
| `momentum_long` | regime in {breakout,trending} AND mom>=0.4 AND conv>=0.5 (broad momentum long) |

## 1. Symbols tested + candle coverage
| symbol | bars | start | end | days | 24h vol | live spread (bps) |
|---|---|---|---|---|---|---|
| LINK | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $4,517,549 | 1.46 |
| AVAX | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $2,814,813 | 0.11 |
| ARB | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $2,535,051 | 2.02 |
| APT | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $2,582,745 | 4.41 |
| PENGU | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $2,431,643 | 1.34 |
| ICP | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,720,598 | 4.01 |
| HBAR | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,373,679 | 8.94 |
| SEI | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,338,902 | 4.7 |
| TIA | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,282,170 | 3.65 |
| WIF | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,124,602 | 0.55 |
| DOT | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,128,466 | 4.39 |
| UNI | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,883,475 | 1.37 |
| CRV | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,960,836 | 2.37 |
| JUP | 5000 | 2026-04-10 | 2026-06-01 | 52.1 | $2,271,139 | 4.8 |
| LDO | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $2,399,284 | 4.98 |
| RENDER | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $2,493,843 | 5.55 |
| DYDX | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,391,668 | 6.14 |
| IP | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $1,119,712 | 9.6 |
| OP | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $916,303 | 6.08 |
| AR | 5001 | 2026-04-10 | 2026-06-01 | 52.1 | $684,998 | 1.36 |

## 2. Headline per gate — expectancy at REALISTIC cost
| gate | signals | best combo | n trades | win% | exp%/trade @35bps | PF | exp%/trade @45bps | verdict |
|---|---|---|---|---|---|---|---|---|
| `as_written` | 0 | `tp_5pct|stop_3pct|hold_4h` | 0 | 0.0 | +0.000 | 0.00 | +0.000 | INCONCLUSIVE |
| `breakout_intent` | 4658 | `tp_8pct|stop_4pct|hold_12h` | 1292 | 37.0 | -0.575 | 0.60 | -0.773 | FAIL |
| `breakout_uptrend` | 4657 | `tp_8pct|stop_4pct|hold_12h` | 1305 | 37.5 | -0.554 | 0.61 | -0.753 | FAIL |
| `momentum_long` | 10078 | `tp_8pct|stop_3pct|hold_24h` | 1053 | 34.3 | -0.624 | 0.66 | -0.823 | FAIL |

## 3.breakout_intent — gate `breakout_intent` detail
**Best combo @ 35bps: `tp_8pct|stop_4pct|hold_12h`** → exp **-0.575%/trade**, WR 37.0%, PF 0.60, R:R 1.02, n=1292, avg hold 43.9 bars
- @ 0bps (no cost): +0.124%/trade  → **cost drag +0.698%/trade**
- @ 45bps (stress): -0.773%/trade, PF 0.51
- best combo re-optimised @ 45bps: `tp_8pct|stop_4pct|hold_12h` → -0.773%/trade

**Sweep @ 35bps (top 12 by expectancy):**
| TP | stop | hold | n | win% | exp%/trade | PF | R:R |
|---|---|---|---|---|---|---|---|
| tp_8pct | stop_4pct | hold_12h | 1292 | 37.0 | -0.575 | 0.60 | 1.02 |
| tp_2.0R | stop_4pct | hold_12h | 1292 | 37.0 | -0.575 | 0.60 | 1.02 |
| tp_1.5R | stop_4pct | hold_12h | 1312 | 37.4 | -0.580 | 0.60 | 1.00 |
| tp_5pct | stop_atr1.5 | hold_12h | 2140 | 20.6 | -0.594 | 0.47 | 1.79 |
| tp_5pct | stop_4pct | hold_12h | 1323 | 37.6 | -0.600 | 0.58 | 0.97 |
| tp_8pct | stop_3pct | hold_12h | 1343 | 36.3 | -0.600 | 0.58 | 1.02 |
| tp_2.0R | stop_3pct | hold_12h | 1365 | 36.5 | -0.603 | 0.58 | 1.01 |
| tp_1.5R | stop_3pct | hold_24h | 1042 | 41.5 | -0.603 | 0.65 | 0.92 |
| tp_8pct | stop_atr1.5 | hold_12h | 2093 | 19.9 | -0.605 | 0.46 | 1.85 |
| tp_1.5R | stop_3pct | hold_12h | 1393 | 37.7 | -0.611 | 0.57 | 0.94 |
| tp_5pct | stop_atr1.5 | hold_24h | 1909 | 18.1 | -0.611 | 0.49 | 2.22 |
| tp_5pct | stop_3pct | hold_12h | 1378 | 36.6 | -0.624 | 0.57 | 0.98 |

**Per-symbol @ 35bps on best combo `tp_8pct|stop_4pct|hold_12h`:**
| symbol | n | win% | exp%/trade | PF | total ret% | max DD% |
|---|---|---|---|---|---|---|
| LINK | 65 | 40.0 | -0.516 | 0.53 | -29.68 | 32.71 |
| AVAX | 63 | 31.8 | -0.862 | 0.29 | -42.69 | 43.09 |
| ARB | 67 | 40.3 | -0.754 | 0.51 | -41.36 | 50.04 |
| APT | 64 | 37.5 | -0.568 | 0.50 | -31.56 | 33.70 |
| PENGU | 74 | 44.6 | -0.750 | 0.58 | -44.98 | 54.94 |
| ICP | 58 | 29.3 | -0.926 | 0.44 | -43.02 | 46.32 |
| HBAR | 65 | 26.2 | -0.778 | 0.38 | -40.75 | 44.82 |
| SEI | 56 | 33.9 | -0.664 | 0.49 | -32.35 | 32.60 |
| TIA | 61 | 45.9 | -0.407 | 0.76 | -25.05 | 35.15 |
| WIF | 71 | 42.2 | -0.413 | 0.69 | -27.38 | 36.18 |
| DOT | 68 | 30.9 | -0.738 | 0.46 | -40.88 | 40.88 |
| UNI | 58 | 39.7 | -0.452 | 0.61 | -24.46 | 28.95 |
| CRV | 64 | 32.8 | -0.920 | 0.43 | -46.00 | 46.00 |
| JUP | 65 | 35.4 | -0.233 | 0.83 | -16.84 | 24.51 |
| LDO | 66 | 30.3 | -0.806 | 0.52 | -43.24 | 53.26 |
| RENDER | 63 | 41.3 | -0.083 | 0.93 | -7.64 | 27.09 |
| DYDX | 66 | 39.4 | -0.297 | 0.85 | -22.76 | 40.71 |
| IP | 69 | 37.7 | -0.520 | 0.65 | -32.49 | 42.88 |
| OP | 62 | 30.6 | -0.888 | 0.40 | -43.52 | 43.94 |
| AR | 67 | 47.8 | +0.044 | 1.03 | -0.97 | 21.36 |

## 3.breakout_uptrend — gate `breakout_uptrend` detail
**Best combo @ 35bps: `tp_8pct|stop_4pct|hold_12h`** → exp **-0.554%/trade**, WR 37.5%, PF 0.61, R:R 1.02, n=1305, avg hold 43.8 bars
- @ 0bps (no cost): +0.144%/trade  → **cost drag +0.699%/trade**
- @ 45bps (stress): -0.753%/trade, PF 0.51
- best combo re-optimised @ 45bps: `tp_8pct|stop_4pct|hold_12h` → -0.753%/trade

**Sweep @ 35bps (top 12 by expectancy):**
| TP | stop | hold | n | win% | exp%/trade | PF | R:R |
|---|---|---|---|---|---|---|---|
| tp_8pct | stop_4pct | hold_12h | 1305 | 37.5 | -0.554 | 0.61 | 1.02 |
| tp_2.0R | stop_4pct | hold_12h | 1305 | 37.5 | -0.554 | 0.61 | 1.02 |
| tp_1.5R | stop_4pct | hold_12h | 1314 | 37.9 | -0.568 | 0.60 | 0.99 |
| tp_1.5R | stop_3pct | hold_12h | 1391 | 38.3 | -0.569 | 0.59 | 0.96 |
| tp_5pct | stop_4pct | hold_12h | 1324 | 38.1 | -0.574 | 0.60 | 0.97 |
| tp_8pct | stop_3pct | hold_12h | 1354 | 36.7 | -0.577 | 0.59 | 1.02 |
| tp_2.0R | stop_3pct | hold_12h | 1366 | 37.0 | -0.579 | 0.59 | 1.00 |
| tp_1.5R | stop_3pct | hold_24h | 1032 | 41.8 | -0.581 | 0.66 | 0.92 |
| tp_5pct | stop_atr1.5 | hold_12h | 2127 | 20.9 | -0.587 | 0.47 | 1.78 |
| tp_5pct | stop_3pct | hold_12h | 1377 | 37.3 | -0.587 | 0.58 | 0.98 |
| tp_8pct | stop_atr1.5 | hold_12h | 2097 | 20.2 | -0.596 | 0.46 | 1.84 |
| tp_5pct | stop_atr1.5 | hold_24h | 1888 | 18.3 | -0.599 | 0.50 | 2.22 |

**Per-symbol @ 35bps on best combo `tp_8pct|stop_4pct|hold_12h`:**
| symbol | n | win% | exp%/trade | PF | total ret% | max DD% |
|---|---|---|---|---|---|---|
| LINK | 65 | 38.5 | -0.517 | 0.53 | -29.71 | 32.92 |
| AVAX | 65 | 32.3 | -0.874 | 0.26 | -44.06 | 44.45 |
| ARB | 68 | 41.2 | -0.556 | 0.61 | -33.40 | 43.46 |
| APT | 66 | 39.4 | -0.593 | 0.53 | -33.80 | 39.54 |
| PENGU | 74 | 44.6 | -0.743 | 0.58 | -44.69 | 54.70 |
| ICP | 60 | 31.7 | -0.805 | 0.48 | -39.89 | 47.39 |
| HBAR | 66 | 28.8 | -0.647 | 0.45 | -35.85 | 40.26 |
| SEI | 54 | 33.3 | -0.745 | 0.42 | -34.16 | 34.41 |
| TIA | 68 | 42.6 | -0.556 | 0.69 | -34.54 | 42.26 |
| WIF | 70 | 40.0 | -0.416 | 0.69 | -27.22 | 35.22 |
| DOT | 70 | 30.0 | -0.753 | 0.45 | -42.40 | 42.40 |
| UNI | 58 | 37.9 | -0.549 | 0.53 | -28.45 | 30.76 |
| CRV | 64 | 35.9 | -0.809 | 0.46 | -41.87 | 41.87 |
| JUP | 64 | 35.9 | -0.209 | 0.84 | -15.30 | 20.46 |
| LDO | 68 | 36.8 | -0.647 | 0.58 | -37.74 | 48.73 |
| RENDER | 62 | 41.9 | -0.039 | 0.97 | -4.99 | 27.50 |
| DYDX | 69 | 40.6 | -0.301 | 0.85 | -24.05 | 40.16 |
| IP | 70 | 38.6 | -0.428 | 0.71 | -28.43 | 42.28 |
| OP | 61 | 31.1 | -0.894 | 0.41 | -43.28 | 43.72 |
| AR | 63 | 46.0 | -0.021 | 0.98 | -4.74 | 20.05 |

## 3.momentum_long — gate `momentum_long` detail
**Best combo @ 35bps: `tp_8pct|stop_3pct|hold_24h`** → exp **-0.624%/trade**, WR 34.3%, PF 0.66, R:R 1.27, n=1053, avg hold 65.4 bars
- @ 0bps (no cost): +0.074%/trade  → **cost drag +0.698%/trade**
- @ 45bps (stress): -0.823%/trade, PF 0.59
- best combo re-optimised @ 45bps: `tp_8pct|stop_3pct|hold_24h` → -0.823%/trade

**Sweep @ 35bps (top 12 by expectancy):**
| TP | stop | hold | n | win% | exp%/trade | PF | R:R |
|---|---|---|---|---|---|---|---|
| tp_8pct | stop_3pct | hold_24h | 1053 | 34.3 | -0.624 | 0.66 | 1.27 |
| tp_8pct | stop_atr1.5 | hold_4h | 3063 | 23.8 | -0.628 | 0.38 | 1.20 |
| tp_5pct | stop_atr1.5 | hold_4h | 3116 | 23.9 | -0.635 | 0.38 | 1.19 |
| tp_1.5R | stop_4pct | hold_12h | 1495 | 36.7 | -0.640 | 0.59 | 1.01 |
| tp_2.0R | stop_3pct | hold_12h | 1554 | 34.9 | -0.648 | 0.57 | 1.07 |
| tp_8pct | stop_3pct | hold_12h | 1507 | 34.2 | -0.650 | 0.57 | 1.09 |
| tp_5pct | stop_atr1.5 | hold_12h | 2327 | 20.3 | -0.653 | 0.46 | 1.80 |
| tp_8pct | stop_atr1.5 | hold_12h | 2182 | 18.6 | -0.656 | 0.45 | 1.97 |
| tp_2.0R | stop_atr1.5 | hold_12h | 3366 | 33.8 | -0.662 | 0.34 | 0.68 |
| tp_8pct | stop_4pct | hold_12h | 1456 | 35.4 | -0.664 | 0.57 | 1.04 |
| tp_2.0R | stop_4pct | hold_12h | 1456 | 35.4 | -0.664 | 0.57 | 1.04 |
| tp_1.5R | stop_3pct | hold_12h | 1638 | 36.3 | -0.665 | 0.56 | 0.98 |

**Per-symbol @ 35bps on best combo `tp_8pct|stop_3pct|hold_24h`:**
| symbol | n | win% | exp%/trade | PF | total ret% | max DD% |
|---|---|---|---|---|---|---|
| LINK | 45 | 35.6 | -0.666 | 0.47 | -26.82 | 27.73 |
| AVAX | 47 | 29.8 | -1.141 | 0.27 | -42.28 | 42.28 |
| ARB | 49 | 22.4 | -1.367 | 0.37 | -50.21 | 53.25 |
| APT | 50 | 36.0 | -0.736 | 0.58 | -32.77 | 38.87 |
| PENGU | 58 | 36.2 | -0.866 | 0.61 | -42.21 | 51.79 |
| ICP | 61 | 32.8 | -0.575 | 0.70 | -32.76 | 47.66 |
| HBAR | 43 | 39.5 | -0.424 | 0.66 | -17.95 | 25.01 |
| SEI | 50 | 40.0 | -0.441 | 0.73 | -22.10 | 25.28 |
| TIA | 62 | 40.3 | -0.090 | 0.95 | -10.50 | 31.09 |
| WIF | 50 | 34.0 | -0.698 | 0.63 | -31.69 | 37.71 |
| DOT | 51 | 37.2 | -0.800 | 0.54 | -35.22 | 35.22 |
| UNI | 43 | 37.2 | -0.818 | 0.49 | -30.96 | 33.30 |
| CRV | 51 | 29.4 | -1.101 | 0.42 | -44.37 | 45.51 |
| JUP | 54 | 35.2 | -0.371 | 0.80 | -21.37 | 25.91 |
| LDO | 54 | 33.3 | -0.595 | 0.69 | -30.27 | 41.08 |
| RENDER | 56 | 26.8 | -0.994 | 0.52 | -44.79 | 44.79 |
| DYDX | 70 | 37.1 | +0.333 | 1.16 | +15.99 | 38.61 |
| IP | 50 | 30.0 | -0.850 | 0.60 | -37.01 | 46.11 |
| OP | 52 | 38.5 | -0.540 | 0.71 | -27.15 | 34.90 |
| AR | 57 | 33.3 | -0.291 | 0.86 | -19.58 | 32.98 |

## 4. SURVIVORSHIP BIAS — results are OPTIMISTICALLY BIASED (headline caveat)
Only **currently-listed** HL perps are testable. Of **230 HL perps, 51 are already delisted** — and delisting is exactly the fate of a failed moonshot (pumped, dumped, went to ~zero, removed). Those **−100% paths are absent from this data**. Every symbol tested here is a *survivor*; the test cannot see the moonshots that died.

**Drag estimate.** 51/230 = **22% of the perp population delisted**. The mechanical leg is long-only on breakouts — precisely the entries most exposed to a token that subsequently collapses and delists. If the screener's small-cap candidates delist at even half that base rate (~11%) and a delisting trade averages ~−80% (vs a clean survivor stop at −3/−4%):

> drag ≈ 0.11 × (−80%) ≈ **−8.8%/trade** of hidden downside. Even a conservative 5% delist rate × −80% ≈ **−4%/trade**.

The best survivor-only expectancy measured (gate `breakout_uptrend`) is **-0.554%/trade**. A delisting drag of −4 to −9%/trade **swamps it by 1–2 orders of magnitude**. For survivors to carry the strategy to breakeven after delistings, they would need to average roughly **+4 to +9%/trade NET** — versus the -0.554%/trade actually observed.

## 5. OVERALL VERDICT
- Literal screener gate (`as_written`): **dead** — 0 signals, structural.
- Best faithful interpretation (`breakout_uptrend`): **FAIL** — best-combo expectancy at realistic 35bps = -0.554%/trade (PF 0.61, n=1305). Negative before any buzz overlay or survivorship correction.

### **FAIL**
Even on survivor-only data the mechanical leg's best honest expectancy is -0.554%/trade — and the survivorship drag (−4 to −9%/trade) **dominates it**. The mechanical chart-trigger leg, in isolation, does **not** demonstrate a robust edge on thin HL small-caps at realistic cost. Spread/cost is the killer on this class: the per-trade edge lives entirely inside the 30–40bps cost band. The buzz filter would need to add edge an order of magnitude larger than the mechanical leg's — AND dodge the delisting tail — to make the full strategy viable.

## Files
- `moonshot_backtest_results.json` — full per-gate / per-symbol / sweep results
- `moonshot_backtest_summary.md` — this summary
- `run_moonshot_backtest.py` — the harness