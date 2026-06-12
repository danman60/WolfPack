# Funding-z-low (F2) Edge Revalidation — 2026-06-12

**Verdict: HOLDS on BTC. DEGRADED on DOGE. Dead everywhere else (as before).**

Re-run of the Phase 6 F2 gate methodology (`docs/research/2026-05-backtest-sweep/run_phase6_funding_edge.py`, identical math: 180-bar funding z-score, fire z < -2.0 -> long, horizons {4h,12h,24h,48h}, 10 bps round-trip, 4 provenance gates) plus the Phase 8 regime segmentation, on data extended ~5 weeks past the original 2026-05-07 discovery run.

## Data (exact counts — nothing truncated silently)

| | value |
|---|---|
| Funding records per symbol | 21,436 each (BTC, ETH, SOL, LINK, AVAX, ARB, DOGE), 2024-01-01 -> 2026-06-12 04:00 UTC, hourly, complete |
| Candles per symbol | 5,001 4h bars each, 2024-02-29 20:00 -> 2026-06-12 04:00 UTC |
| Candle source | Hyperliquid `candleSnapshot` direct. Intel API (159.89.115.95:8000) refused connection at run time. HL caps at most-recent ~5000 candles per interval — same effective cap the original run had via the intel API (`limit=5000`). Consequence: the extended window's **start** is 2024-02-29 vs ~2024-01-25 originally. It is a forward-shifted window, not a strict superset. |

## 1. Gate results — original vs extended

| symbol | original (2026-05-07) | extended (2026-06-12) | n orig->ext | mean/fire orig->ext | t orig->ext |
|---|---|---|---|---|---|
| **BTC** (h=3, 12h fwd) | ALL GATES PASS | **ALL GATES PASS** | 143 -> 145 | +0.417% -> +0.415% | 2.65 -> 2.68 |
| **DOGE** (h=6, 24h fwd) | ALL GATES PASS | **Gate 2 FAIL (marginal)** | 147 -> 173 | +1.029% -> +0.884% | 2.87 -> 2.79 |
| LINK (h=6) | Gate 1 only | Gate 1 only (G2 fail) | 156 -> 166 | +0.704% -> +0.786% | 2.13 -> 2.46 |
| AVAX (h=12) | Gate 1 only | Gate 1 only (G2 fail) | 219 -> 247 | +1.019% -> +0.754% | 2.48 -> 2.03 |
| ETH | dead | dead (t=0.56) | — | — | — |
| SOL | dead | dead (t=1.71) | — | — | — |
| ARB | dead | dead (t=1.40) | — | — | — |

- **BTC**: statistically unchanged. G2 walk-forward: IS +0.566%, OOS +0.299% (retention 53%, passes). G3 Sharpe 4.56, cum +45.7% — now also beats HODL (+3.7% over this flat window). G4 1/2 perturbations pass (>=50% bar, same marginal pass shape as original).
- **DOGE**: Gate 1 still strong (t=2.79) but the 70/30 walk-forward split now fails the 50%-retention rule by a hair: IS +1.242%, OOS +0.577% (retention 46%, needed >=0.621%). OOS is still positive and same-sign — degraded, not dead.

## 2. Recent out-of-sample

Forward returns at each symbol's original best horizon, fires only.

**Most recent 90 days (2026-03-14 -> 2026-06-12):**

| symbol | n | mean/fire | WR | note |
|---|---|---|---|---|
| BTC | **10** | +0.059% | 40% | n<30 — too small for confidence |
| DOGE | **28** | +0.088% | 64% | n<30 — too small for confidence |
| LINK | 32 | +1.075% | 72% | strongest recent cell |
| AVAX | 44 | +0.135% | 48% | |
| ARB | 24 | +0.057% | 50% | n<30 |
| ETH | 36 | -0.264% | 42% | negative |
| SOL | 28 | -0.046% | 32% | negative, n<30 |

**Strict post-discovery (>=2026-05-07, 5 weeks):** BTC n=2 (+0.288%), DOGE n=26 (+0.065%), LINK n=10 (+2.067%). **All n far below 30 — directionally consistent with the edge but statistically uninformative.** This edge is rare-firing; 5 weeks cannot confirm or kill it.

## 3. Regime-conditioned expectancy (Phase 8 method, extended data)

Sim: enter on fire, exit first of {3% SL, 2% TP, 48h time-stop}, net of 10 bps. Edge = strat mean/trade minus same-regime mean 48h HODL return.

| symbol | regime | n | WR | strat/trade | edge vs HODL | original edge |
|---|---|---|---|---|---|---|
| **BTC** | SIDEWAYS | 44 | 63.6% | +0.366% | **+0.387%** | +0.41% |
| **BTC** | BEAR | 31 | 74.2% | +0.832% | **+0.765%** | +0.67% |
| BTC | BULL | 2 | 50% | -0.600% | -0.746% | (n/a) |
| **DOGE** | SIDEWAYS | 35 | 68.6% | +0.361% | **+0.518%** | +0.34% |
| DOGE | BEAR | 66 | 54.5% | -0.373% | -0.083% | -0.06% |
| LINK | SIDEWAYS | 49 | 65.3% | +0.246% | +0.357% | +0.35% |
| ETH/SOL/AVAX/ARB | all | — | — | negative or noise | | |

The Phase 8 picture replicates: **BTC SIDEWAYS and BEAR edges hold and slightly strengthen in BEAR (+0.67 -> +0.77)**. DOGE's edge remains SIDEWAYS-only; DOGE BEAR trades are negative under the SL/TP exit structure.

## 4. Regime-gated portfolio leg — honest stats

Variant: fire only when regime at entry in {SIDEWAYS, BEAR}. Full window, SL 3% / TP 2% / 48h, net of costs. MC = 10,000 trade-order resamples with replacement.

| leg | **n** | expectancy | total | WR | PF | worst MAE | MC prob-profit | MC p5 total |
|---|---|---|---|---|---|---|---|---|
| **BTC only** | **75** | **+0.492%** | +36.9% | 66.7% | **1.77** | -7.47% | **98.6%** | **+9.3%** |
| DOGE only | 101 | -0.118% | -12.0% | 59.4% | 0.90 | -9.99% | 32.0% | -52.5% |
| BTC+DOGE | 176 | +0.142% | +24.9% | 62.5% | 1.14 | -9.99% | 79.7% | -23.8% |
| all 7 symbols | 832 | -0.183% | -152.3% | 57.5% | 0.85 | -29.67% | 1.3% | -265.2% |

**n = 75 for the BTC leg over ~27 months (~2.8 trades/month). Rare-firing — this is a seasoning leg, not a portfolio core.** The DOGE gated leg is negative because the SIDEWAYS+BEAR gate admits DOGE BEAR trades (n=66, -0.373%/trade); DOGE only carries edge in SIDEWAYS. Consumers of the trade list can reconstruct a DOGE-SIDEWAYS-only variant via the `regime_at_entry` field.

**Recommendation for portfolio assembly: use the BTC-only regime-gated leg.** ~+16%/yr gross of compounding at full notional, PF 1.77, 98.6% resample prob-profit, p5 still positive. BTC+DOGE is positive but strictly dominated.

## Deliverables

- `run_fundingz_revalidation.py` — script (Phase 6/8 math verbatim; data fetch direct from HL)
- `results.json` — gates, OOS, regime, leg stats, data provenance
- `trade_list_regime_gated.json` — 832 trades, all 7 symbols, fields: symbol, entry_ts, exit_ts, entry_price, exit_price, net_pnl_pct, gross_pnl_pct, exit_reason, hold_bars, mae_pct, regime_at_entry. Portfolio leg = filter `symbol=="BTC"` (75 trades).
- `data/` — raw funding + candle caches (14 files)

## Caveats

1. Window start shifted forward ~5 weeks vs original (HL 5000-candle cap) — the "extended" comparison is a rolled window, not a superset.
2. Post-discovery true OOS is only 5 weeks, n=2 (BTC) / n=26 (DOGE) — below any confidence bar.
3. Gate 4 robustness for BTC remains marginal (1/2 threshold perturbations pass), identical to the original run.
4. Simulator fills SL/TP at exact level intra-bar (no slippage beyond the 10 bps); same assumption as Phases 7/8 — comparable, optimistic in fast tape.
5. No live trading code, wallet config, strategies/, or DB touched. All files under `docs/research/2026-06-fundingz-revalidation/`.
