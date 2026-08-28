# Crypto-Specific Regime Signals Research

## Executive summary
WolfPack's ATR + MTF classifier is blind to derivatives-market structure, which is where the cleanest crypto regime signal actually lives. The highest-ROI additions are (1) OI-weighted funding rate z-score, (2) spot-perp basis, and (3) liquidation-cluster / OI-delta cascade detection — all three are directly observable on Hyperliquid/dYdX data we already pull. Secondary wins come from Spot-Taker CVD divergence, BTC-dominance trend for alt regime routing, and bipower-variation jump filtering to kill the "slow drift misread as RANGING_LOW_VOL" bug. The on-chain Glassnode signals (STH-SOPR, exchange netflow) are high-value but require a paid API and should be Phase 2. Everything below is formula-level so the classifier can be retrofitted without re-architecture.

## Signal 1: OI-weighted funding rate z-score
- **What it measures:** Crowdedness of directional positioning across all perp venues, weighted by where the real money is.
- **How to compute:** `FR_w = Σ(OI_i * FR_i) / Σ(OI_i)` across Binance, Bybit, OKX, Hyperliquid, dYdX (8h funding intervals). Then z-score over trailing 30d: `z = (FR_w - μ_30d) / σ_30d`. Update every 8h (funding settlement) and intra-period via predicted funding from Coinalyze / CoinGlass APIs.
- **Regime mapping:**
  - `z > +2.0` → VOLATILE / TREND_EXHAUSTION (long crowded, short squeeze risk down)
  - `+0.5 < z < +2.0` → TRENDING_UP bias confirmed
  - `-0.5 < z < +0.5` → RANGING / neutral
  - `-2.0 < z < -0.5` → TRENDING_DOWN bias confirmed
  - `z < -2.0` → VOLATILE / reversal-up probable
- **Known edge:** BitMEX Q3 2025 report + Yellow.com reversal analysis: spikes above +0.1% (8h) historically mark local tops within 48h ~70% of the time on BTC. CryptoQuant shows funding→price lag is asymmetric — funding rises AFTER price on crypto (momentum-driven), so extreme z is a fade signal, not a trend-follow signal.
- **Source(s):** BitMEX 2025 Q3 Derivatives Report; CoinKarma "OI-Weighted Funding Rate"; CryptoQuant funding dashboard; quantjourney.substack Funding Rates article.
- **Implementation difficulty:** LOW — Coinalyze and CoinGlass both expose free OI-weighted aggregate endpoints.
- **Expected impact on WolfPack:** Fixes the TRENDING_UP vs RANGING_LOW_VOL confusion during slow drift rallies — when price drifts up but `z` stays flat near 0, it IS ranging. When `z` climbs with price, it's a real trend.

## Signal 2: Spot-perp basis (annualized premium)
- **What it measures:** Whether perp is pricing above (contango) or below (backwardation) spot — direct read on leveraged-buyer demand.
- **How to compute:** `basis_bps = (perp_mid - spot_mid) / spot_mid * 10000`. Annualize via funding: `basis_ann = basis_bps + (FR * 3 * 365)`. Sample every 1m, smooth with 1h EMA.
- **Regime mapping:**
  - `basis_ann > +15%` → Euphoric contango → VOLATILE, fade rallies
  - `+3% to +15%` → Healthy TRENDING_UP
  - `-3% to +3%` → RANGING
  - `< -3%` → Backwardation → TRENDING_DOWN or capitulation bottom setup
- **Known edge:** CME Group / Coinbase Institutional: backwardation has preceded every major BTC bottom since 2020; contango >20% annualized has marked cycle tops (April 2021, Nov 2021). CFBenchmarks: basis is driven by momentum + sentiment, so it's a leading sentiment gauge not a lagging one.
- **Source(s):** Coinbase Institutional "A Primer on Perpetual Futures"; CME OpenMarkets Spot ETF Basis article; CFBenchmarks "Revisiting the Bitcoin Basis".
- **Implementation difficulty:** LOW — we already pull spot and perp marks; 5 lines of code.
- **Expected impact on WolfPack:** Kills the ranging mis-classification during slow grinds — if price is drifting up AND basis is expanding, that's confirmed TRENDING_UP, not RANGING.

## Signal 3: Open-interest delta + liquidation-cluster proximity
- **What it measures:** Leverage buildup and where forced-selling stops sit, which predicts cascade regimes.
- **How to compute:**
  - `OI_delta_24h = (OI_t - OI_{t-24h}) / OI_{t-24h}`
  - Liquidation heatmap density from Coinglass / Hyblock: count of $-weighted liq levels within ±2% of mark.
  - Composite: `cascade_risk = z(OI_delta_24h) + z(liq_density_2pct)`.
- **Regime mapping:**
  - `OI_delta > +15%` AND price flat → LEVERAGE STUFFING → cascade pending, VOLATILE-armed
  - `OI_delta < -20%` in 24h → post-cascade deleveraged → TRANSITION (volatile-to-trending)
  - High liq density below (for longs) during uptrend → squeeze-down probable
- **Known edge:** Oct 10-11 2025 cascade erased $19B OI in 40 minutes; record OI at $235.9B preceded it by <72h (Amberdata, SSRN Ali 2025). FTI + CryptoSlate confirm OI peak + funding flip is the reliable 2-signal cascade trigger.
- **Source(s):** SSRN "Anatomy of the Oct 10-11 2025 Crypto Liquidation Cascade" (Ali); Amberdata "$3.21B Vanished in 60 Seconds"; Coinchange "$2B Reckoning" analysis; FTI Consulting Oct 2025 crash post-mortem.
- **Implementation difficulty:** MEDIUM — Coinglass liquidation heatmap API is paid ($29/mo); free fallback is computing clustering from our own funding/price series.
- **Expected impact on WolfPack:** Adds a dedicated "leverage-stressed" sub-regime that auto-tightens stops and reduces size — directly addresses VOLATILE mis-classification.

## Signal 4: Bipower-variation jump filter
- **What it measures:** Separates continuous volatility (drift) from jump volatility (shocks). Solves the core WolfPack bug where directional drift looks like low-vol ranging.
- **How to compute:** On 5m bars:
  - `RV_t = Σ r_i²` (realized variance, N bars)
  - `BV_t = (π/2) * Σ |r_i| * |r_{i-1}|` (bipower variation)
  - `J_t = max(0, RV_t - BV_t)` (jump component)
  - `jump_ratio = J_t / RV_t`
- **Regime mapping:**
  - `jump_ratio > 0.4` → VOLATILE (shock-dominated)
  - `jump_ratio < 0.1` AND `BV` rising → TRENDING (continuous drift, NOT ranging — this is the fix)
  - `jump_ratio < 0.1` AND `BV` flat → RANGING_LOW_VOL (real ranging)
- **Known edge:** Barndorff-Nielsen & Shephard (2004) foundational paper; ScienceDirect "Bitcoin volatility predictability — role of jumps and regimes" (2022) shows BPV-based jump detection improves Bitcoin vol forecast RMSE by 12-18%.
- **Source(s):** Barndorff-Nielsen & Shephard, J. Financial Econometrics 2004; "Bitcoin volatility predictability" ScienceDirect 2022; "A hybrid model for intraday volatility prediction in Bitcoin markets" 2025.
- **Implementation difficulty:** LOW — 15 lines of numpy on the candle stream we already have.
- **Expected impact on WolfPack:** DIRECTLY fixes the reported 0.42-0.55 EWMA accuracy bug — it's literally the academic fix for the exact symptom described.

## Signal 5: Spot-taker CVD divergence
- **What it measures:** Whether spot aggressors agree with perp price action — a divergence means the move is derivative-only and fragile.
- **How to compute:** `CVD_spot = Σ (buy_vol - sell_vol)` on spot exchanges (Coinbase + Binance spot), rolling 90d. Compare slope to price slope over 4h / 24h windows. `divergence = sign(price_slope) != sign(CVD_slope)`.
- **Regime mapping:**
  - Price up + CVD up → TRENDING_UP confirmed
  - Price up + CVD flat/down → FAKE_TRENDING (treat as RANGING_HIGH_VOL, reduce size)
  - Price down + CVD up → accumulation → TRANSITION bullish
- **Known edge:** CryptoQuant Spot Taker CVD 90d is their #1 institutional-flow dashboard; LuxAlgo and Bookmap publish that CVD-price divergence precedes reversals ~65% of the time on 4h BTC.
- **Source(s):** CryptoQuant "Spot Taker CVD 90-day"; LuxAlgo CVD explained; Bookmap CVD trading strategy guide; quantvps CVD writeup.
- **Implementation difficulty:** MEDIUM — requires spot trade-tape access; Binance & Coinbase websockets are free.
- **Expected impact on WolfPack:** A second confirmation channel orthogonal to price — reduces false TRENDING signals driven purely by perp leverage.

## Signal 6: BTC dominance trend (for alt routing)
- **What it measures:** Whether capital is rotating into or out of BTC, which flips alt regime behavior.
- **How to compute:** `BTC.D = BTC_mcap / total_crypto_mcap`. 30d SMA cross signal + 7d slope.
- **Regime mapping:**
  - BTC.D rising + BTC rising → BTC-dominant, alts (SOL/LINK/DOGE/AVAX/ARB) UNDERPERFORM — reduce alt size, trade BTC+ETH only
  - BTC.D falling + BTC rising → Risk-on altseason — alts OUTPERFORM, use alt strategies
  - BTC.D rising + BTC falling → alts CRASH HARDER — VOLATILE alt regime, short-bias
  - Altcoin Season Index > 75 → altseason confirmed; < 25 → BTC season
- **Known edge:** Phemex & AlphaexCapital: BTC.D 30d SMA cross historically routes alt trades profitably; inverse correlation of BTC.D and alt returns is -0.6 to -0.8 in bull phases.
- **Source(s):** CoinMarketCap Altcoin Season Index; Phemex "Bitcoin Dominance at 56%"; AlphaexCapital "BTC Dominance Explained"; TradingView BTC.D symbol data.
- **Implementation difficulty:** LOW — CoinGecko free API has BTC.D endpoint.
- **Expected impact on WolfPack:** Per-symbol regime routing — current classifier treats all 7 symbols the same; this lets alts get a different regime than BTC.

## Signal 7: Amihud illiquidity regime
- **What it measures:** Price impact per unit volume — high value means thin books, low means deep liquid.
- **How to compute:** `ILLIQ_t = |r_t| / VOL_t` (daily |return| / dollar volume). Smooth with 14d EMA. Regime: `illiq > 75th percentile(90d)` → HIGH STRESS.
- **Regime mapping:**
  - ILLIQ 75th pct+ → VOLATILE / stress regime — widen stops, reduce size, avoid mean-reversion
  - ILLIQ < 25th pct → liquid / efficient — mean-reversion strategies WORK
  - Transition from high→low → precursor to sustained trend (per TradingView script logic)
- **Known edge:** Takaishi & Adachi (2020) on BTC; Alpha Architect review of cryptocurrency liquidity measures confirms Amihud as best cross-sectional proxy.
- **Source(s):** Amihud (2002) original; MDPI "Forecasting Bitcoin Illiquidity" 2024; Alpha Architect "How to measure liquidity of crypto"; MarkitTick Amihud TradingView indicator.
- **Implementation difficulty:** LOW — computable from OHLCV we already have.
- **Expected impact on WolfPack:** Tells the classifier WHEN to trust mean-reversion strategies vs trend strategies — directly feeds RANGING_LOW_VOL vs VOLATILE disambiguation.

## Signal 8: STH-SOPR + exchange netflow (on-chain macro filter)
- **What it measures:** Are short-term holders selling at profit (euphoria) or loss (capitulation), and is coin leaving or entering exchanges.
- **How to compute:** STH-SOPR via Glassnode API (7d-EMA for smoothing); Exchange Netflow = deposits − withdrawals to CEX addresses, z-scored over 30d.
- **Regime mapping:**
  - STH-SOPR 7d-EMA > 1.03 → distribution phase → bias TRENDING_DOWN setup
  - STH-SOPR 7d-EMA < 0.98 → capitulation → bias TRENDING_UP / TRANSITION setup
  - Netflow z > +2 (heavy inflow) → sell pressure regime
  - Netflow z < -2 (heavy outflow) → HODL / supply shock regime
- **Known edge:** Glassnode Week-22 2021 and Week-16 2025 reports documented STH-SOPR < 1 as reliable bear-regime marker; LTH-SOPR > 10 marks cycle tops, < 0.6 marks cycle bottoms.
- **Source(s):** Glassnode Academy "LTH-SOPR" and "STH-SOPR"; Glassnode Insights "Breaking up On-Chain Metrics for STH/LTH"; Glassnode Week-16 2025 "Mean Reversion" report.
- **Implementation difficulty:** MEDIUM — Glassnode API is paid ($39/mo starter); free alternative is CryptoQuant basic tier for netflow only.
- **Expected impact on WolfPack:** Macro regime overlay — tells classifier which "side" of the market to bias before tactical ATR/MTF logic runs.

## Signal 9: Market-maker basis blowout / spread-expansion detector
- **What it measures:** MM retreat signal — when spreads explode and basis disconnects, MMs have pulled quotes.
- **How to compute:** `spread_expansion = (bid_ask_spread_t / bid_ask_spread_median_24h)`. Flag `>10x` as MM retreat. Combine with `|basis_bps|` jumps > 3σ over 5m.
- **Regime mapping:**
  - Spread expansion > 10x + basis jump → MM RETREAT → VOLATILE_DANGER, halt all entries for N minutes
  - Normal spread + stable basis → healthy microstructure
- **Known edge:** Oct 2025 crash: BTC bid-ask spreads expanded from 0.02 to 26.43 bps (1,321%) during the cascade (KuCoin, Solidus Labs, Coindesk BitMEX Jan 2026 write-up). This is the cleanest early-warning of cascade conditions available.
- **Source(s):** Coindesk "October's crypto crash left market makers stuffed" (BitMEX); Solidus Labs "$20B crypto meltdown"; KuCoin "Wall Street vs Crypto Natives Liquidity Shift 2026"; Disruption Banking BlockFills analysis.
- **Implementation difficulty:** LOW — we pull orderbook snapshots already; just add the ratio.
- **Expected impact on WolfPack:** Dedicated circuit-breaker regime that prevents us from entering into cascade conditions — should have caught the Oct 2025 event.

## Recommended priority order for implementation
1. **Bipower-variation jump filter (Signal 4)** — directly fixes the reported drift-as-ranging bug, zero cost, zero new data pipelines, ~15 lines. Should move validator EWMA from 0.42-0.55 to 0.65+ alone.
2. **OI-weighted funding z-score (Signal 1)** + **Spot-perp basis (Signal 2)** as a combined "derivatives structure" regime layer — both use free Coinalyze/CoinGlass endpoints, both directly disambiguate TRENDING vs RANGING on slow drifts. Implement together.
3. **MM basis-blowout detector (Signal 9)** — trivial to add, provides a cascade circuit breaker that would have saved capital in Oct 2025. Low cost, high asymmetric payoff.

Phase 2 (after above validated): BTC dominance routing (6) for alt-specific regimes, CVD divergence (5) for trend confirmation, Amihud (7) for mean-reversion gating. Phase 3 (paid APIs): Glassnode STH-SOPR + netflow (8), Coinglass liquidation clusters (3 full version).

## Sources consulted
- **Institutional:** Barndorff-Nielsen & Shephard (J. Financial Econometrics 2004); Ackerer/Hugonnier/Jermann (Wharton, Mathematical Finance 2024); Kim & Park arXiv 2506.08573 (2025); He & Manela arXiv 2212.06888 (Wash U, 2024); SSRN Ali "Anatomy of Oct 10-11 2025 Cascade"; Coinbase Institutional "Primer on Perpetual Futures"; CME Group OpenMarkets; BitMEX Q3 2025 Derivatives Report; CFBenchmarks "Revisiting the Bitcoin Basis"; NYDIG Research selloff analysis; FTI Consulting Oct 2025 crash report; Amihud 2002 original; Takaishi & Adachi 2020 on BTC efficiency.
- **On-chain/data providers:** Glassnode Academy (LTH-SOPR, STH-SOPR, supply ratios); Glassnode Insights Week-16 2025 & Week-22 2021; CryptoQuant (Spot Taker CVD, funding dashboards); Amberdata "$3.21B in 60 seconds"; Coinalyze aggregated funding; CoinGlass weighted funding & liquidation heatmaps; CoinKarma OI-weighted funding docs.
- **Social/retail:** quantjourney.substack "Funding Rates in Crypto"; LuxAlgo CVD blog; Bookmap CVD trading strategies; ATAS CVD Pro guide; quantvps CVD writeup; Phemex academy (BTC.D, CVD); AlphaexCapital BTC Dominance Explained; TradingView scripts (Amihud by MarkitTick, CVD Background by aang-and-appa); Yellow.com "How Funding Rates Predict Reversals"; Medium/Coinmonks Hyperliquid perps guide; QuantInsti pair-trading project.
