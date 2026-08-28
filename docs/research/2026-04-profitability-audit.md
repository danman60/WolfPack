# WolfPack Profitability Audit — Phase 2.1

**Date:** 2026-04-11
**Period:** 2026-03-13 to 2026-04-11 (29 days)
**Total Trades:** 184 closed | **Net P&L:** $3,958.53 | **Win Rate:** 48.9%
**Total Volume:** $527,168 | **Symbols:** 7 | **Strategies:** 3 (+ NULL)

---

## Executive Summary

1. **Mean reversion is the edge.** It accounts for 48 trades but $3,831 of the $3,959 net P&L (97%). Regime momentum and EMA crossover are near breakeven. The 83 trades with no strategy tag produced only $101 — likely noise.

2. **Shorts massively outperform longs.** BTC short ($905), LINK short ($752), ARB short ($670), DOGE short ($593), AVAX short ($450) = $3,370 from shorts. Longs are near flat except ARB long ($747, single trade). SOL long is the biggest loser (-$200).

3. **Late-night ET is the profit window.** Hours 20-22 ET generated $1,654 net on only 19 trades ($87 avg). The 19:00 hour is the worst (-$240). Afternoon 14-17 ET is consistently negative.

4. **Winners leave $8.76 on the table (MFE beyond exit).** Median winner MFE is $7.94 vs avg P&L of $52.47 — exits are capturing most of the move. But the avg MFE left on table suggests a trailing stop could recover ~17% more per winner.

5. **Fee drag is minimal.** Total funding: $10.17 + estimated slippage: $38.14 = $48.31 total fees on $527K volume (0.9 bps effective). This is not a problem at current scale.

6. **Regime/conviction data is 97% NULL.** Only 5 of 184 trades have regime or conviction tagged. This metadata gap makes it impossible to validate the regime-routing thesis. Fixing this is the highest-priority instrumentation task.

7. **SOL longs are a consistent loser.** 11 trades, 27.3% WR, -$200 net, 0.17 R:R. Should be disabled or filtered to short-only.

---

## 1. By Symbol & Direction

| Symbol | Dir | Trades | WR% | R:R | Net P&L | Avg Hold (h) | Avg MFE | Avg MAE | Funding | Slip (bps) |
|--------|-----|--------|-----|-----|---------|---------------|---------|---------|---------|------------|
| BTC | short | 19 | 63.2 | 38.73 | $905.07 | -- | -- | -- | $0.00 | 0.0 |
| LINK | short | 24 | 54.2 | 5.91 | $751.97 | -- | -- | -- | $0.00 | 0.0 |
| ARB | long | 1 | 100.0 | -- | $746.92 | -- | -- | -- | $0.00 | 0.0 |
| ARB | short | 1 | 100.0 | -- | $670.26 | -- | -- | -- | $0.00 | 0.0 |
| DOGE | short | 4 | 25.0 | 24.93 | $593.25 | 0.2 | 0.00 | -293.24 | $0.23 | 5.0 |
| AVAX | short | 3 | 100.0 | -- | $449.91 | 10.0 | 184.88 | 0.00 | $3.13 | 10.0 |
| ETH | short | 8 | 37.5 | 9.44 | $70.37 | 2.0 | 0.45 | -1.80 | $0.12 | 2.0 |
| ETH | long | 54 | 48.1 | 1.67 | $57.34 | 41.7 | 3.69 | -0.16 | $0.05 | 0.5 |
| DOGE | long | 7 | 71.4 | 8.40 | $45.40 | 5.1 | 4.01 | -1.38 | $0.10 | 7.1 |
| BTC | long | 25 | 40.0 | 1.45 | $1.05 | 69.3 | 9.65 | -0.12 | $2.27 | 0.5 |
| LINK | long | 26 | 46.2 | 0.79 | -$24.63 | 7.5 | 6.06 | -2.68 | $1.55 | 0.6 |
| AVAX | long | 1 | 0.0 | -- | -$108.38 | -- | -- | -- | $0.00 | 0.0 |
| SOL | long | 11 | 27.3 | 0.17 | -$200.00 | 10.3 | 6.50 | -2.46 | $2.71 | 2.9 |

**Key observations:**
- Shorts net +$3,441 across all symbols. Longs net +$518 (and that includes the single ARB long at $747).
- BTC longs: 25 trades, 40% WR, only $1.05 net — massive churn for zero edge. Avg hold 69h means funding exposure.
- ETH longs: 54 trades (most active pair) but only $57.34 net. High volume, low yield.
- SOL longs: clear negative edge, should be disabled.

---

## 2. By Strategy

| Strategy | Trades | WR% | R:R | Net P&L | Avg Hold (h) | Avg MFE | Avg MAE | Funding |
|----------|--------|-----|-----|---------|---------------|---------|---------|---------|
| mean_reversion | 48 | 58.3 | 5.26 | $3,831.36 | 7.5 | 138.66 | -73.31 | $3.37 |
| (NULL) | 83 | 49.4 | 1.71 | $100.74 | 27.6 | 5.26 | -1.17 | $6.81 |
| regime_momentum | 48 | 37.5 | 2.04 | $19.47 | -- | -- | -- | $0.00 |
| ema_crossover | 5 | 60.0 | 1.41 | $6.96 | -- | -- | -- | $0.00 |

**Key observations:**
- Mean reversion: 26% of trades, 97% of profits. 5.26 R:R is exceptional. MFE of $138 vs MAE of -$73 shows it takes heat but pays off.
- 83 NULL-strategy trades produced $101 — these need strategy tagging to understand what they are.
- Regime momentum: 48 trades at 37.5% WR and $19 net is essentially noise. Needs investigation or disabling.
- EMA crossover: only 5 trades, too small to judge, but marginally positive.

---

## 3. By Regime at Entry

| Regime | Trades | WR% | R:R | Net P&L | Avg Hold (h) | Avg MFE | Avg MAE |
|--------|--------|-----|-----|---------|---------------|---------|---------|
| (NULL) | 179 | 50.3 | 5.65 | $3,988.53 | 30.2 | 31.87 | -1.01 |
| RANGING | 4 | 0.0 | -- | -$4.91 | 1.1 | 0.27 | -1.14 |
| unknown | 1 | 0.0 | -- | -$25.09 | 0.2 | 0.00 | -293.24 |

**Key observation:** 97.3% of trades have no regime tagged. The 4 RANGING trades all lost. This data is nearly useless for regime analysis — **instrumentation is the #1 priority.**

---

## 4. By Conviction Bucket

| Bucket | Trades | WR% | R:R | Net P&L | Avg Hold (h) |
|--------|--------|-----|-----|---------|---------------|
| <50 (NULL) | 179 | 50.3 | 5.65 | $3,988.53 | 30.2 |
| 50-59 | 4 | 0.0 | -- | -$4.91 | 1.1 |
| 70-79 | 1 | 0.0 | -- | -$25.09 | 0.2 |

**Key observation:** Same problem as regime — conviction is not being recorded. The 5 trades with conviction data all lost, but n=5 is meaningless.

---

## 5. By Time of Day (ET)

| Hour (ET) | Trades | WR% | Net P&L | Avg P&L |
|-----------|--------|-----|---------|---------|
| 0 | 8 | 37.5 | $123.66 | $15.46 |
| 1 | 7 | 42.9 | $61.16 | $8.74 |
| 2 | 8 | 25.0 | $193.29 | $24.16 |
| 3 | 6 | 50.0 | $13.78 | $2.30 |
| 4 | 7 | 14.3 | -$20.03 | -$2.86 |
| 5 | 7 | 28.6 | $506.28 | $72.33 |
| 6 | 2 | 50.0 | -$0.80 | -$0.40 |
| 7 | 3 | 66.7 | $5.57 | $1.86 |
| 8 | 15 | 53.3 | $723.61 | $48.24 |
| 9 | 11 | 63.6 | $54.41 | $4.95 |
| 10 | 15 | 66.7 | $53.12 | $3.54 |
| 11 | 7 | 71.4 | $57.70 | $8.24 |
| 12 | 4 | 25.0 | $6.07 | $1.52 |
| 13 | 1 | 0.0 | -$5.57 | -$5.57 |
| 14 | 7 | 14.3 | -$10.08 | -$1.44 |
| 15 | 4 | 75.0 | $3.94 | $0.98 |
| 16 | 8 | 25.0 | -$14.27 | -$1.78 |
| 17 | 11 | 36.4 | -$12.55 | -$1.14 |
| 18 | 8 | 100.0 | $477.13 | $59.64 |
| 19 | 11 | 18.2 | -$240.40 | -$21.85 |
| 20 | 9 | 44.4 | $776.95 | $86.33 |
| 21 | 7 | 57.1 | $35.70 | $5.10 |
| 22 | 10 | 80.0 | $877.28 | $87.73 |
| 23 | 8 | 75.0 | $292.58 | $36.57 |

**Profitable windows (net > $100):**
- **Late night (20-23 ET):** $1,982.51 on 34 trades ($58.31 avg) — the best window by far
- **Early morning (5 ET):** $506.28 on 7 trades — Asia open spillover
- **Pre-market (8 ET):** $723.61 on 15 trades — strong pre-market edge
- **Late night (0-2 ET):** $377.91 on 23 trades

**Loss windows:**
- **19:00 ET:** -$240.40 (18.2% WR) — worst single hour
- **14-17 ET:** -$36.90 combined — afternoon doldrums

---

## 6. MFE/MAE Distribution

| Outcome | Trades | Avg MFE | Median MFE | Avg MAE | Median MAE | Avg P&L | MFE Left on Table |
|---------|--------|---------|------------|---------|------------|---------|-------------------|
| Winner | 90 | $43.36 | $7.94 | $0.00 | $0.00 | $52.47 | $8.76 |
| Loser | 94 | $1.82 | $0.37 | -$29.00 | -$2.14 | -$8.13 | $5.74 |

**Key observations:**
- Winners: avg MFE $43.36 but P&L $52.47 — the avg is skewed by a few big winners. Median MFE $7.94 shows most winners are modest.
- Winners leave $8.76 on table on average — a trailing stop could capture some of this.
- Losers: avg MFE of $1.82 means most losers barely went profitable before turning. Median MAE of -$2.14 shows most losses are small, but avg MAE of -$29 is dragged by outliers (the DOGE -$293 MAE trade).
- Losers had $5.74 MFE left on table — meaning they were briefly profitable. A breakeven stop on favorable excursion could convert some losers to scratch trades.

---

## 7. Fee Drag

| Metric | Value |
|--------|-------|
| Net P&L | $3,958.53 |
| Gross Wins | $4,722.40 |
| Gross Losses | $763.87 |
| Total Funding | $10.17 |
| Avg Entry Slippage | 0.2 bps |
| Avg Exit Slippage | 0.9 bps |
| Est. Slippage Cost | $38.14 |
| **Total Fee Drag** | **$48.31** |
| Fee Drag % of Gross Wins | 1.0% |
| Total Volume | $527,168 |
| Effective Fee Rate | 0.9 bps |

**Key observation:** Fees are negligible at current scale. Even at 10x volume ($5.3M), fee drag would be ~$483 — still manageable. Funding is almost nothing ($10.17) because most trades are short-duration. BTC longs with 69h avg hold are the exception — they accumulate $2.27 total funding but that's still tiny.

---

## 8. By Source

| Source | Trades | WR% | R:R | Net P&L | Avg Hold (h) |
|--------|--------|-----|-----|---------|---------------|
| manual | 184 | 48.9 | 5.77 | $3,958.53 | 24.5 |

**Key observation:** All 184 trades are tagged "manual" — there is no brief vs mechanical split in the data. Once autobot goes live, this column will differentiate human vs automated trades.

---

## Exit Reason Breakdown

| Exit Reason | Trades | WR% | Net P&L |
|-------------|--------|-----|---------|
| (NULL) | 158 | 47.5 | $3,482.72 |
| manual | 16 | 50.0 | $426.76 |
| brief_close | 10 | 70.0 | $49.05 |

**Key observation:** 158 trades (86%) have no exit reason tagged. The 10 brief_close trades have 70% WR — small sample but suggests the Brief's close signals are accurate.

---

## Recommendations

### Immediate (next session)

1. **Fix metadata instrumentation** — regime_at_entry, conviction_at_entry, and strategy are NULL on 97% of trades. Without this data, the regime-routing thesis cannot be validated. **Expected impact:** Enables all future analysis; blocks are invisible without it.

2. **Disable SOL longs** — 11 trades, 27.3% WR, -$200, 0.17 R:R. Clear negative edge. **Expected impact:** +$200 saved over next 29 days at current frequency.

3. **Review BTC longs** — 25 trades, 40% WR, $1.05 net, 69h avg hold. Massive capital tie-up for zero return. Either tighten entry criteria or disable. **Expected impact:** Frees capital for higher-edge trades; saves ~$2/month in funding.

### Short-term (this week)

4. **Implement trailing stop for winners** — avg $8.76 MFE left on table per winner. Even capturing 50% of that = $3.94/trade x 90 winners = ~$355 additional profit over this sample period. **Expected impact:** +$355/month.

5. **Add time-of-day filter** — block entries at 19:00 ET (-$240, 18.2% WR) and consider blocking 14-17 ET (net negative). Concentrate on 20-23 ET and 8 ET windows. **Expected impact:** Avoid -$250/month in losses from bad hours.

6. **Tag NULL-strategy trades** — 83 trades with no strategy represent 45% of trades. Understanding what these are is critical. Are they manual discretionary? Untagged mean reversion? This is a data quality issue.

### Medium-term (this month)

7. **Scale mean reversion** — 97% of profits come from 26% of trades. Consider increasing position size or frequency for mean reversion signals while keeping other strategies at minimum size until they prove out.

8. **Breakeven stop for losers** — Losers averaged $1.82 MFE before going negative. A breakeven stop after $2+ MFE could convert ~20% of losers to scratch trades. **Expected impact:** ~19 trades x $8.13 avg loss x 20% conversion = ~$31 saved. Modest but free.

9. **Brief close signals are promising** — 70% WR on 10 trades. Monitor this as n grows. If it holds, automate Brief close signals as a high-confidence exit trigger.

---

*Queries saved to: `docs/research/queries/profitability_pivots.sql`*
*Data source: Supabase `wp_trade_history` table, 184 closed trades*
