# Turtle Breadth Study — does Donchian trend-following generalize across the liquid Hyperliquid perp universe?

**Date:** 2026-06-12 · **RESEARCH ONLY** — no live trading code, wallet config, strategies/, or DB touched. All artifacts in this directory.

**Hypothesis tested:** trend-following only produces meaningful returns as a BREADTH portfolio (original Turtles traded ~20 markets), not on 1–2 symbols. WolfPack had only tested BTC (thin PASS), ETH (PASS), LINK (FAIL).

## VERDICT: FAIL

**Honest all-universe portfolio (26 symbols, no ex-ante winner knowledge): +3.97%/yr, Sharpe 0.68, max DD 7.3% at 1x.** Even levered 4x it reaches only +14.3%/yr — below the >15%/yr bar — and MC worst-tail DD blows past 30% already at 3x. Worse, **breadth UNDERPERFORMS ETH-only on the identical frame** (ETH-only: +5.79%/yr, Sharpe 0.86). Ex-ZEC (one privacy-coin mega-trend) the honest portfolio degrades to +2.73%/yr, Sharpe 0.48. Breadth does not turn this Donchian implementation into a material edge.

## Headline caveats

- **Survivorship bias:** universe selected from perps live on 2026-06-12; delisted perps are invisible. For liquid large-caps the bias is far smaller than small-caps, but the cross-sectional positive fraction below is optimistic by construction.
- **Partial windows:** 7 of 26 symbols listed mid-window (HYPE 2024-12, VVV 2025-01, ZEC 2025-04, PUMP 2025-07, XMR 2025-08, XPL 2025-08, ASTER 2025-09). They enter the portfolio at listing; ZEC/VVV (the two biggest winners) only span the 2025 alt run — favorable subperiod.
- **Funding not modeled** (same as all prior turtle sweeps). Long-only perp portfolio typically pays funding in trending-up regimes — real returns skew slightly lower.
- In-sample, single window, one regime sequence. Companion walk-forward study runs separately.

## Universe (snapshot 2026-06-12)

Rule: 24h notional volume > $10M **OR** open-interest notional > $20M (deterministic; OI added because the snapshot day was quiet — DOGE/AVAX/LINK printed <$10M vol while carrying $20–30M OI). 28 qualified; **LIT** (1,031 bars) and **MON** (1,483 bars) dropped as too young (<1,500 4h bars). **26 symbols usable, 0 fetch failures** (LINK/ASTER/ZRO needed 429 retries). Full listing with volumes in `universe.json`.

Majors (10bps/side): BTC, ETH, SOL, XRP. All others 20bps/side. Stress = +10bps/side.

## Per-symbol results — 4h Donchian long-only, p30 (common period), base costs

Same mechanics as `docs/research/2026-06-turtle-regime/`: real `BacktestEngine` + real `TurtleDonchianStrategy`, ATR(20)x2.0 stop, SMA(200) trend filter, structural channel exit, size 15% of $25k equity, long-only (`macro_regime="TRENDING_UP"`). exp bps = expectancy per trade in bps of starting equity.

| symbol | 24h vol | OI | tier via | listed | cost/side | n | p30 exp bps | p30 ret% | p30 PF | p30 maxDD% | p30 stress exp | p40 exp bps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ZEC | $129M | $178M | vol | 2025-04-19 | 20bps | 12 | +1299.3 | +154.7 | 10.33 | 27.3 | +1290.1 | +1451.9 |
| VVV | $9M | $27M | oi | 2025-01-28 | 20bps | 18 | +247.8 | +44.5 | 3.91 | 16.9 | +238.7 | +265.2 |
| ENA | $12M | $22M | vol | 2024-04-02 | 20bps | 21 | +146.8 | +29.0 | 2.90 | 11.8 | +143.6 | +127.2 |
| SUI | $6M | $36M | oi | 2024-02-29 | 20bps | 26 | +86.8 | +19.4 | 2.61 | 11.3 | +83.9 | +83.9 |
| XRP | $35M | $97M | vol | 2024-02-29 | 10bps | 35 | +77.2 | +22.9 | 2.59 | 23.2 | +73.4 | +102.8 |
| DOGE | $7M | $24M | oi | 2024-02-29 | 20bps | 30 | +71.1 | +17.5 | 2.25 | 15.3 | +68.4 | +75.3 |
| CRV | $17M | $8M | vol | 2024-02-29 | 20bps | 27 | +61.5 | +16.3 | 1.77 | 26.5 | +58.8 | +53.4 |
| ETH | $962M | $1156M | vol | 2024-02-29 | 10bps | 22 | +56.5 | +13.7 | 2.15 | 6.7 | +53.6 | +31.9 |
| HYPE | $673M | $1220M | vol | 2024-12-05 | 20bps | 23 | +40.9 | +8.9 | 1.55 | 15.4 | +38.5 | +70.5 |
| WLD | $65M | $48M | vol | 2024-02-29 | 20bps | 25 | +36.3 | +5.8 | 1.52 | 17.9 | +33.1 | -46.3 |
| TRX | $13M | $17M | vol | 2024-02-29 | 20bps | 33 | +33.7 | +10.0 | 2.29 | 17.6 | +31.3 | +25.3 |
| AAVE | $5M | $45M | oi | 2024-02-29 | 20bps | 34 | +28.1 | +6.2 | 1.40 | 18.0 | +25.6 | +19.5 |
| ADA | $9M | $21M | oi | 2024-02-29 | 20bps | 34 | +23.7 | +6.2 | 1.46 | 16.1 | +21.0 | +36.5 |
| TAO | $6M | $20M | oi | 2024-02-29 | 20bps | 28 | +18.8 | +3.8 | 1.25 | 12.9 | +16.8 | +12.6 |
| BTC | $2538M | $2023M | vol | 2024-02-29 | 10bps | 29 | +13.8 | +3.5 | 1.46 | 6.6 | +11.2 | +16.3 |
| XMR | $40M | $42M | vol | 2025-08-01 | 20bps | 12 | -0.1 | -2.2 | 1.00 | 12.3 | -2.3 | +1.2 |
| BNB | $5M | $34M | oi | 2024-02-29 | 20bps | 37 | -1.9 | -2.9 | 0.94 | 10.8 | -4.2 | -1.0 |
| TON | $14M | $47M | vol | 2024-02-29 | 20bps | 28 | -4.6 | -6.0 | 0.89 | 11.5 | -7.1 | -0.5 |
| SOL | $192M | $249M | vol | 2024-02-29 | 10bps | 30 | -8.5 | -4.2 | 0.82 | 9.9 | -10.5 | -9.0 |
| AVAX | $4M | $23M | oi | 2024-02-29 | 20bps | 33 | -12.9 | -7.4 | 0.72 | 13.6 | -15.1 | -7.5 |
| LINK | $4M | $31M | oi | 2024-02-29 | 20bps | 41 | -17.4 | -8.1 | 0.69 | 20.2 | -19.4 | -12.8 |
| NEAR | $47M | $73M | vol | 2024-02-29 | 20bps | 32 | -23.2 | -10.4 | 0.58 | 16.4 | -25.1 | -26.8 |
| PUMP | $4M | $20M | oi | 2025-07-10 | 20bps | 13 | -24.6 | -4.1 | 0.75 | 20.1 | -27.0 | -28.2 |
| ZRO | $3M | $25M | oi | 2024-02-29 | 20bps | 36 | -62.4 | -26.4 | 0.18 | 26.9 | -64.9 | -64.6 |
| ASTER | $3M | $23M | oi | 2025-09-19 | 20bps | 9 | -71.3 | -6.9 | 0.02 | 6.9 | -73.5 | -73.5 |
| XPL | $15M | $22M | vol | 2025-08-22 | 20bps | 13 | -106.7 | -15.9 | 0.06 | 19.7 | -108.7 | -118.9 |

(Full 20/30/40/55 grid in `breadth_results.json`.)

## Cross-sectional verdict

| period | positive expectancy | fraction | median exp (bps/trade) | positive under +10bps stress |
|---|---|---|---|---|
| p20 | 15/26 | 58% | +12.9 | 15/26 |
| **p30** | **15/26** | **58%** | **+21.2** | **15/26** |
| p40 | 15/26 | 58% | +14.4 | 14/26 |
| p55 | 15/26 | 58% | +19.6 | 15/26 |

- **58% positive at every period — a slim majority, not the clear majority a generalizing edge should show.** And that 58% is inflated by survivorship.
- The fraction is remarkably stable across periods, and the positive/negative split is the *same symbols* at every p — symbol selection (which coins trended in 2024-26) matters far more than the Donchian parameter.
- Stress (+10bps/side) barely moves anything: avg holding ~40 bars means costs are not the binding constraint. The edge, where present, is trend capture, not cost-sensitive scalping.
- Common period chosen: **p30** (tied fraction, best median expectancy). No per-symbol cherry-picking anywhere downstream.

## Portfolio simulation — equal-risk (inverse ann-vol weighted), p30 for all symbols

Built from per-symbol `BacktestEngine` equity-curve bar returns; weights ∝ 1/σ(underlying 4h returns, annualized), renormalized per bar over listed-and-warmed-up symbols. Window 2024-02-29 → 2026-06-12 (5,001 4h bars, 2.28 yrs). Sharpe annualized at √2190.

### HONEST portfolio = all 26 universe symbols (headline — winners and losers, since winners weren't knowable ex-ante)

| leverage | total return | CAGR | Sharpe | realized max DD | longest flat | MC median DD | MC p95 DD (worst tail) | P(DD>30%) | MC ruin |
|---|---|---|---|---|---|---|---|---|---|
| 1x | +9.3% | +3.97%/yr | 0.68 | 7.3% | 550d | 7.9% | 13.9% | 0.0% | 0% |
| 2x | +18.5% | +7.71%/yr | 0.68 | 14.2% | — | 15.4% | 26.2% | 2.0% | 0% |
| 3x | +27.4% | +11.17%/yr | 0.68 | 20.7% | — | 22.4% | **37.0%** | 16.3% | 0% |
| 4x | +35.8% | +14.32%/yr | 0.68 | 26.8% | — | 28.9% | **46.5%** | 41.0% | 0% |

MC = 5,000 block-bootstrap sims on portfolio bar returns (1-week blocks). **MC worst-tail (p95) DD crosses 30% between 2x and 3x.** At the max survivable leverage (~2x), CAGR is only ~7.7%/yr. Longest flat period at 1x: **550 days** under water — 2/3 of the test window.

Note on sizing convention: per-symbol strategies inherit the prior sweep's 15%-of-equity position sizing, so "1x" is a conservatively-deployed book (≤15% notional per symbol while in a trade). Leverage scales the whole return stream; Sharpe (0.68) is sizing-invariant and is the binding constraint — at Sharpe 0.68, any sizing that targets >15%/yr implies ~22%+ annualized vol and worst-tail DDs well past 30%.

### Sensitivities

| portfolio | n | CAGR | Sharpe | max DD (1x) |
|---|---|---|---|---|
| Honest all-universe | 26 | +3.97%/yr | 0.68 | 7.3% |
| Honest ex-ZEC | 25 | +2.73%/yr | 0.48 | 7.3% |
| Selected winners only (in-sample, OVERFIT) | 15 | +8.76%/yr | 1.25 | 8.1% |
| ETH-only, same frame | 1 | +5.79%/yr | 0.86 | 6.7% |
| Majors-only (BTC/ETH/SOL/XRP) | 4 | +3.65%/yr | 0.65 | 5.9% |

- **The single symbol ZEC carries ~1/3 of the honest portfolio's return** (one 2025 privacy-coin mega-trend, 12 trades). Remove it and Sharpe drops 0.68 → 0.48.
- The breadth portfolio's Sharpe (0.68) is *lower* than ETH alone (0.86). Diversification added losers (11/26 symbols net-negative) faster than it added independent trends — crypto alts are one correlated risk factor, not 20 independent markets. This is the core reason the Turtle-breadth analogy fails on this universe.
- Even the in-sample-selected winners-only portfolio (Sharpe 1.25, +8.8%/yr) — which you could not have held ex-ante — doesn't reach 15%/yr unlevered.

## Determination

**FAIL.** Breadth does not turn turtle from ~5%/yr (ETH-only) into something material:
1. Cross-sectional positive fraction is 58% (survivorship-inflated) — not the clear majority a real generalizing edge shows.
2. Honest all-universe portfolio: +3.97%/yr at Sharpe 0.68 — *below* the ETH-only baseline on the same frame.
3. To exceed 15%/yr it needs >4x leverage, where MC worst-tail DD is ~47%+ and P(DD>30%) is 41% — not survivable.
4. Return concentration: ZEC alone ≈ 1/3 of portfolio return; ex-ZEC Sharpe 0.48.

The diversification premise itself is what failed: liquid crypto perps trend together (one beta factor), so adding symbols mostly adds the same trend plus idiosyncratic losers. The original Turtles' ~20 markets spanned rates, FX, grains, metals, energy — genuinely independent return streams. 26 alts are not that.

**What survives:** the ETH/BTC turtle PASS from the prior sweep stands; XRP (+77bps/trade, PF 2.59, 10bps costs, full window) is the one new full-window major that looks as good as ETH and is worth a walk-forward look. ZEC-style fresh-listing momentum is a different hypothesis (listing-momentum, not breadth) — separate study if pursued.

## Files

- `fetch_universe_candles.py` — universe selection + 4h candle fetch (Hyperliquid API), `universe.json`, `candles/*.json`
- `run_breadth_sweep.py` — 26 symbols x p{20,30,40,55} x {base,stress} via real BacktestEngine → `breadth_results.json`, `equity_curves.npz`
- `run_portfolio.py` — cross-sectional stats, equal-risk portfolio, leverage sweep + MC → `portfolio_results.json`, `portfolio_curve.npz`
