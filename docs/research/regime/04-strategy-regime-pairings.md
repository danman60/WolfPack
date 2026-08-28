# Strategy-Regime Optimal Pairings Research

**Date:** 2026-04-13
**Scope:** evidence-based pairings for WolfPack's 11-strategy / 6-regime router
**Sources:** institutional (AQR, Moskowitz-Ooi-Pedersen, Jegadeesh-Titman, SSRN, Quantpedia) + retail (QuantifiedStrategies, TradingView, Medium backtests, LuxAlgo, Thrive, HTX Research)

---

## Executive summary

Five pairings have the strongest combined institutional + crypto-tested evidence and should drive WolfPack's router. Everything else is secondary.

1. **TRENDING_UP / TRENDING_DOWN → Donchian-55 breakout with 200-SMA regime filter** (System 2 turtle). Modern crypto-adapted version. 35-45% raw WR, profit factor 1.8-2.4, Sharpe ~1.0 on BTC with volatility-band filter. This is the only trend strategy with a published 110-year track record (AQR) *and* crypto replication.
2. **TRENDING_UP / TRENDING_DOWN → 20-EMA pullback to MA with Fib confluence**. QuantifiedStrategies walk-forward on BTC shows ~82% WR on confirmed trend pullbacks when entered at 38.2-61.8% retracement with 20 EMA as dynamic support. The highest-WR trend continuation setup in the evidence.
3. **RANGING_LOW_VOL → Bollinger band bounce to mid-band with RSI>30 filter**. Multiple BTC backtests show 60-65% WR in confirmed ranges; Quantified Strategies' BB mean-reversion model on BTC delivered ~50% CAGR in-sample while in-market only 34% of time. Highest edge of any range strategy on crypto.
4. **RANGING_LOW_VOL → RSI(2) Connors mean reversion (long only above 200-SMA, short only below)**. Not crypto-native, but widely replicated with 70-80% raw WR; best parameter for crypto is RSI(2) < 5 for long, RSI(2) > 95 for short, exit on 5-MA cross. No hard stop per Connors (use time stop).
5. **VOLATILE / PANIC → VWAP reversion fade after k-sigma volatility jump**. BTC hourly jump-reversion (k=3-4 sigma) shows peak Sharpe in that range; fade far-from-VWAP (+/-5%) with RSI>75 or <25, target VWAP. R:R 1.5-3.0:1. Used in production by Volatility Box. Alternative: no-trade (cash = edge) during declared PANIC.

All other strategy slots in WolfPack should be treated as secondary — they either lack strong evidence or duplicate the above with inferior parameters.

---

## TRENDING_UP / TRENDING_DOWN

### Winner 1: Donchian-55 (Turtle System 2) with trend filter
- **Parameters:** 55-day upper/lower breakout for entry, 20-day opposite channel for exit, ATR-based 2N stop, 200-SMA regime filter (long only when price > 200-SMA, short only when <). Position size = 1% risk / (2 * ATR).
- **Expected WR / R:R:** 30-40% WR, 3:1 to 4:1 average R:R, profit factor 1.8-2.4 on crypto. Low WR is characteristic — the edge is in the tail trades (>10R).
- **Crypto validation:** HTX Research ran turtle on crypto: System 2 (55-day) beats System 1 (20-day) in modern crypto due to algorithmic-driven false breakouts in shorter windows. Modern fix: pair with 200-SMA filter, only trade breakouts aligned with trend.
- **Source:** AQR "A Century of Evidence on Trend-Following Investing" (110-year Sharpe ~0.75-1.0); TOS Indicators modern turtle backtest; HTX Research crypto replication; QuantifiedStrategies turtle analysis.
- **Anti-pattern:** NEVER fire in RANGING_LOW_VOL. False-breakout rate exceeds 65% there; all retail-to-crypto studies flag this.

### Winner 2: 20-EMA pullback with Fibonacci confluence
- **Parameters:** trend defined as 20-EMA > 50-EMA and price above both on HTF; entry at pullback to 20-EMA *and* within 38.2-61.8% Fib retrace of prior impulse; confirmation = bullish/bearish rejection candle; stop beyond the EMA; target = prior swing + measured move.
- **Expected WR / R:R:** 75-82% WR on confirmed pullbacks (QuantifiedStrategies BTC daily walk-forward); avg R:R ~1.5:1. Lower R multiple than Donchian but far higher hit rate.
- **Crypto validation:** Documented on BTC daily and 4H. Winner in "trend with shallow dip" context. Fails in TRANSITION where the trend itself is disputed.
- **Source:** QuantifiedStrategies "20 EMA strategy backtest"; ACY pullback confluence guide; multiple replicated on BTC charts.

### Winner 3: Time-series momentum (12-1 month)
- **Parameters:** long if BTC trailing 12-month return > 0, short if <. Moskowitz-Ooi-Pedersen formulation. Vol-target 10-15% annualized by scaling position inverse to 60-day realized vol.
- **Expected WR / R:R:** 50-55% WR monthly, Sharpe ~0.7-1.0 on BTC-only; much higher when diversified across asset classes (MOP paper: Sharpe 1.66 cross-asset).
- **Crypto validation:** Liu & Tsyvinski (2018) replicated TSMOM on crypto; found >20% annualized return for momentum strategies (though much of it is time-series not cross-sectional).
- **Source:** Moskowitz, Ooi, Pedersen (2012), AQR datasets, Liu-Tsyvinski (NBER 2018).
- **Use in WolfPack:** This is the underlying theory that validates why *any* trend strategy should work on BTC. Use as a regime-confirmation layer, not a standalone execution strategy at WolfPack's intraday timeframes.

### Runner-up: Volatility breakout (BB-Keltner squeeze)
- **Parameters:** Bollinger Band (20, 2) contracted inside Keltner Channel (20, 1.5 ATR) for 10-15 bars; entry on close outside BB in direction of HTF trend; ATR trailing stop at 2.5 ATR.
- **Expected WR:** ~55% with squeeze confirmation; Sharpe >1.0 in PyQuantLab BTC optimization (243 parameter combos).
- **Crypto validation:** PyQuantLab Medium article; LuxAlgo Keltner guide.
- **Caveat:** WR degrades sharply without squeeze pre-condition. Gate strictly.

---

## RANGING_LOW_VOL

### Winner 1: Bollinger Band bounce to mid-band + RSI filter
- **Parameters:** BB(20, 2); entry long when close touches lower band *and* RSI(14) > 30 (not making new low); exit at 20-SMA mid-band or RSI(14) > 50. Inverse for shorts. Regime gate: BB width < 40th percentile over trailing 100 bars (confirmed compression).
- **Expected WR / R:R:** 60-65% WR with RSI>30 filter (vs ~50% without); avg R:R 1:1 to 1.2:1 (small, frequent wins).
- **Crypto validation:** SSRN 5775962 (Arda, "Bollinger Bands under Varying Market Regimes: BTC/USDT") — explicitly regime-conditioned study showing mean-reversion dominance in flat-bandwidth regimes; QuantifiedStrategies BTC BB backtest (~50% CAGR while only 34% in market); Avalanche Jan 2026 case study (RSI 24 at lower band → 22% bounce to mid).
- **Source:** Arda (SSRN 2026); QuantifiedStrategies BTC BB; AvaTrade BB strategy guide; Kavout BB guide.
- **Strong evidence:** this is the highest-quality pairing in the entire study.

### Winner 2: RSI(2) Connors mean reversion
- **Parameters:** RSI(2) < 5 for long, > 95 for short; trend filter: long only if price > 200-SMA, short only if <. Exit on close above 5-SMA (long) or below 5-SMA (short). No hard stop per Connors; add a 5-bar time stop for crypto (Connors tested equities, time stops safer in 24/7 crypto).
- **Expected WR / R:R:** 70-75% WR on Connors' equity backtests; replicated 60-70% on BTC daily (ChartSchool, ElearnMarkets, MQL5 replications). R:R ~1:1.
- **Crypto validation:** Partial. FMZ and MQL5 published BTC replications showing it works directionally but produces larger losers without stops. Add ATR-based stop at 3N.
- **Source:** StockCharts ChartSchool RSI(2); QuantifiedStrategies RSI-2; Larry Connors "Short-Term Trading Strategies That Work."

### Winner 3: Support/resistance reject-and-retest (range structure)
- **Parameters:** identify support/resistance via volume profile (0.5-1.5% bin size in low vol); enter on rejection candle at level *and* retest confirming wick; stop 1 ATR beyond the level; target = opposite side of range.
- **Expected WR / R:R:** 55-65% in confirmed ranges; R:R 2:1 to 3:1 (target is the other side of the range).
- **Crypto validation:** standard S/R trading; altFINS and Altrady crypto guides corroborate the pattern on BTC.
- **Use in WolfPack:** this is the canonical `range_breakout` / range_fade play when price is *inside* the range.

---

## RANGING_HIGH_VOL

### Winner 1: Wider Bollinger (20, 2.5 or 3.0) fade + volume/RSI confirmation
- **Parameters:** bump BB stdev to 2.5-3.0 in high-vol regime (Arda SSRN). Entry only on close beyond 2.5σ with volume spike > 1.5x 20-bar avg and RSI extreme (<25 or >75). Exit at mid-band or prior swing. Stop 1.5 ATR beyond the touch.
- **Expected WR:** 55-60% (lower than low-vol ranges because wicks are common); R:R ~1.5:1.
- **Crypto validation:** Arda SSRN explicitly tests BB under varying BTC regimes; widens bands in high-vol.
- **Source:** Arda (SSRN 2026); QuantifiedStrategies BB.

### Winner 2: Liquidity sweep / stop-hunt fade
- **Parameters:** identify prior swing high/low with stop cluster; wait for sweep + close back inside range; enter on confirming engulfing/pin; stop just beyond the sweep wick + 0.5 ATR; target = opposite range side or prior VWAP.
- **Expected WR / R:R:** 60-70% when combined with fair-value-gap or momentum confluence (MindMathMoney, DailyPriceAction). Lone-wick setups win ~50%.
- **Crypto validation:** pervasive in crypto smart-money literature. BTC/ETH exhibit textbook liquidity grabs around round numbers and HTF swing points.
- **Source:** Mastery Trader Academy, DailyPriceAction 15-min strategy, Equiti liquidity sweep guide.
- **Why HIGH_VOL:** stop-hunts are most aggressive in high-ATR chop; this strategy explicitly needs vol to trigger.

### Winner 3: VWAP mean reversion (intraday only)
- **Parameters:** fade price when >+5% or <-5% from session-anchored VWAP with RSI>75 or <25; target VWAP; stop 1.5 ATR beyond the extreme. Use 00:00 UTC as anchor for crypto or 12-hour rolling VWAP.
- **Expected WR / R:R:** ~60% WR, R:R 1.5:1 to 3:1 (Volatility Box).
- **Crypto validation:** FerroQuant, Volatility Box, Mastery Trader document on BTC/ETH.
- **Source:** Volatility Box VWAP mean-reversion docs; Mastery Trader Academy; Hyrotrader VWAP in crypto.

---

## VOLATILE / PANIC

### Winner 1: Intraday volatility-jump mean reversion (k-sigma)
- **Parameters:** flag bars where return |z-score| >= 3σ (k=3-4 is sweet spot per Medium/DEV.to BTC study); fade in opposite direction after the initial impulse *closes*; stop at the impulse extreme; target VWAP or 0.5 ATR-sized take-profit.
- **Expected WR / R:R:** Sharpe peak at k=3-4 on BTC hourly; WR ~55-60%, R:R ~1.8:1.
- **Crypto validation:** Explicit BTC-USD implementation published on DEV.to (Ayrat Murtazin).
- **Source:** "Intraday Volatility Jump Mean-Reversion Strategy for BTC-USD" (DEV.to).

### Winner 2: Capitulation V-reversal (fear & greed + wick bottom)
- **Parameters:** entry after 15-30% drawdown in <72 hours with Fear & Greed < 20 *and* a confirmed bullish engulfing or hammer on a high-volume capitulation bar. Stop below the wick + 1 ATR. Target = 38.2% Fib retrace of the capitulation move.
- **Expected WR / R:R:** ~75% on confirmed V-reversals (westafricatradehub BTC pattern study, CoinSpaid capitulation analysis). R:R 2:1.
- **Crypto validation:** Bitcoin 2022 bear-market bottoms, May 2021 flush, March 2020 COVID drop all followed this pattern. Documented bullish-V pattern on BTC.
- **Caveat:** infrequent signals; expect 2-5 fires/year on BTC daily.
- **Source:** Altrady V pattern, CoinSpaid capitulation article, Amberdata crypto capitulation report.

### Winner 3: No trade (cash = edge)
- **When:** declared PANIC regime with realized vol > 2x 90-day median and trend definition broken. Moskowitz-Ooi-Pedersen inverse-vol scaling effectively does this; AQR managed-futures research explicitly cuts size during regime transitions.
- **Rationale:** both trend and mean-reversion fail in true panic. Even Connors' RSI(2) bleeds during vertical crashes. The highest-expectancy action is skipping trades and/or sizing down 70%+ (tradewink regime-sizing convention).
- **Source:** AQR "Demystifying Managed Futures", Tradewink AI regime guide, Thrive regime research.

---

## TRANSITION

### Winner 1: Wait for confirmation (no new entries) + scale out existing
- **Rule:** when regime classifier flips or confidence drops below threshold, close or scale out half of existing positions, halt new entries for N bars until new regime persists ≥ K consecutive classifications.
- **Evidence:** Tradewink/HeyGoTrade regime literature — position size in trending regime 100%, choppy 30-50%, transitioning 30% (cut 70%).
- **No specific entry strategy in TRANSITION** — the evidence is that nothing has positive expectancy here. Treat TRANSITION as a no-new-trade regime with active position management only.

### Winner 2 (optional): Inverse-volatility position sizing on continuation breakouts
- **Parameters:** if TRANSITION must trade, size = base_size * (target_vol / realized_vol). AQR time-series momentum uses this; it naturally halves size when vol doubles.
- **Strategy fit:** limit to Donchian-55 breakouts only (high R:R, low WR acceptable), with 70% size reduction vs trending regime.
- **Source:** Moskowitz-Ooi-Pedersen, AQR Trend Following whitepapers.

---

## Cross-regime losers (anti-pairings — NEVER fire)

| Strategy | Forbidden regime | Evidence |
|---|---|---|
| **EMA crossover (9/21, 12/50)** | RANGING_LOW_VOL, RANGING_HIGH_VOL | "Crypto spends ~60% of time in ranges; EMA whipsaws every bar" (PRUVIQ, Hyrotrader, ChartSwatcher). Documented net loss in ranges. Require ADX > 25 to fire. |
| **Donchian / Turtle / breakouts** | RANGING_LOW_VOL | >65% false-breakout rate; well-documented drawdown contributor. Add 200-SMA filter OR gate by ADX > 20. |
| **Bollinger mean reversion** | TRENDING_UP / TRENDING_DOWN (strong) | "Bands get ridden for extended periods." (AvaTrade, Kavout). Arda SSRN shows negative Sharpe in trending BTC regime. Require BB width < 40th pctile AND price not > 0.5σ above upper or < lower for multiple bars. |
| **RSI(2) Connors** | VOLATILE / PANIC | No hard stop + vertical moves = catastrophic loss. Documented failure in March 2020 COVID crash replications. Gate by ATR percentile < 80. |
| **Trend pullback** | RANGING, TRANSITION | Definition requires valid trend; fires false in chop. Require 20-EMA > 50-EMA > 200-EMA slope > 0 AND ADX > 20. |
| **Measured move / chart patterns** | RANGING_HIGH_VOL, PANIC | Pattern integrity breaks under volatility expansion. ~75-85% WR reported only in normal-vol trending regime. |
| **VWAP reversion** | TRENDING strongly | Price can stay >+5% from VWAP for hours/days in strong trends. Gate by ADX < 20 or regime != TRENDING. |
| **Opening range breakout** | no-volume sessions (RANGING_LOW_VOL off-hours) | Published edge has decayed on equities; partial edge on BTC but only at session starts (00:00 UTC daily open). Gate by volume > 1.5x 20-bar avg. |

---

## Parameter overrides for WolfPack's existing 11 strategies

| Strategy | Preferred regime(s) | Override params | Evidence anchor |
|---|---|---|---|
| **mean_reversion** | RANGING_LOW_VOL | RSI(2) < 5 long / > 95 short; exit 5-SMA; trend filter 200-SMA | Connors / QuantifiedStrategies |
| **band_fade** | RANGING_LOW_VOL (primary), RANGING_HIGH_VOL (secondary with BB 2.5σ) | BB(20, 2.0) low-vol; BB(20, 2.5-3.0) high-vol; RSI > 30 entry filter; exit at 20-SMA mid | Arda SSRN; QuantifiedStrategies BTC BB |
| **ema_crossover** | TRENDING_UP / TRENDING_DOWN only | 20/50 EMA; ADX > 25 gate; HARD BLOCK in any RANGING regime | ChartSwatcher, PRUVIQ, altFINS |
| **turtle_donchian** | TRENDING_UP / TRENDING_DOWN | System 2 (55/20); 200-SMA trend filter; 2N ATR stop; skip RANGING | HTX Research, TOS Indicators, AQR |
| **trend_pullback** | TRENDING_UP / TRENDING_DOWN | entry at 20-EMA + 38.2-61.8% Fib; rejection candle confirm; HTF slope > 0 | QuantifiedStrategies 20-EMA |
| **orb_session** | TRENDING open sessions only | 00:00 UTC anchor; 15-min range; require vol > 1.5x avg on break; skip low-vol days | TradingView ORB scripts, Quora/Reddit consensus |
| **regime_momentum** | TRENDING_UP / TRENDING_DOWN | 12-1 TSMOM signal; vol-targeted size 10-15% annualized | Moskowitz-Ooi-Pedersen, Liu-Tsyvinski |
| **vol_breakout** | TRENDING_UP / TRENDING_DOWN with squeeze pre-condition | BB(20,2) inside Keltner(20, 1.5 ATR) for 10-15 bars; ATR 2.5 trail; HTF trend | PyQuantLab Medium, LuxAlgo Keltner |
| **measured_move** | TRENDING continuation only | 75-85% WR only with volume confirmation ≥1.25x and prior impulse defined; skip RANGING | QuantifiedStrategies measured-move |
| **slow_drift_follow** | TRENDING_UP slow-grind | use 50-EMA pullback; avoid high-vol; size inverse to realized vol | AQR TSMOM, Quantpedia slow mean reversion |
| **range_breakout** | RANGING_HIGH_VOL (breakout) OR TRANSITION→TRENDING | require close beyond range high/low AND retest holds AND volume spike; otherwise skip | altFINS/Altrady, DailyPriceAction |

### Router logic changes implied by this research

1. **Add `RSI(2)` as the internal entry trigger for mean_reversion in RANGING_LOW_VOL** — replacing whatever entry rule currently fires. This is the single highest-WR replacement in the report.
2. **Gate `ema_crossover`, `turtle_donchian`, `trend_pullback`, `measured_move` behind ADX ≥ 20 (or ≥ 25 on higher TF)** in addition to regime label. Regime classifiers can lag; ADX is a cheap belt-and-braces.
3. **Scale `band_fade` BB stdev by regime** — 2.0σ in LOW_VOL, 2.5-3.0σ in HIGH_VOL. One strategy, two param sets, per-regime gate.
4. **Make TRANSITION a no-new-trade regime by default** — existing positions only, size cut 70%. No evidence supports new entries.
5. **In VOLATILE/PANIC, only allow `band_fade` (wide BB) + `vwap_reversion` (new entries must have k=3+ sigma trigger)**. Block everything else.
6. **Donchian on crypto must use System 2 (55-day), not 20-day**, with 200-SMA filter. System 1 is a whipsaw machine on modern BTC.
7. **Every trend strategy needs a slope filter** (20-EMA > 50-EMA > 200-EMA for longs) to catch false regime classifications.

---

## Sources

### Institutional / academic
- Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum" — Journal of Financial Economics / SSRN 2089463
- AQR "A Century of Evidence on Trend-Following Investing"
- AQR "Demystifying Managed Futures" and "Trend Following and Rising Rates" white papers
- Jegadeesh & Titman (1993) seminal momentum paper; 30-year retrospective (Springer 2022)
- Liu & Tsyvinski (2018) cryptocurrency risk factor paper (cited via Yang 2019, AUT crypto TSMOM study)
- Arda, Efe (2026) "Bollinger Bands under Varying Market Regimes: BTC/USDT" SSRN 5775962
- Padysak & Vojtko (2022) "Seasonality, Trend-following, and Mean reversion in Bitcoin" SSRN 4081000
- Beluská & Vojtko (2024) "Revisiting Trend-following and Mean-Reversion Strategies in Bitcoin" SSRN 4955617
- HTX Research "Application of Turtle Trading System in the Cryptocurrency Market"

### Retail / social-validated
- QuantifiedStrategies.com: RSI-2, 20-EMA, Bitcoin BB, Turtle, Keltner, Measured Move backtests
- Quantpedia: Bitcoin trend vs mean reversion articles
- TOS Indicators "Modern Turtle Trading Strategy"
- PyQuantLab Medium: BB-Keltner squeeze BTC optimization (243 param combos); Donchian breakout
- LuxAlgo: Keltner Channel strategy, HMM regime indicator
- Mastery Trader Academy: VWAP reversion, liquidity sweep reversal
- DailyPriceAction: 15-min liquidity sweep reversal
- FMZ Quant / Medium: BB mean reversion, dual-regime ADX+RSI adaptive system
- ChartSchool (StockCharts) RSI(2) canonical write-up
- MQL5 Articles "Day Trading Larry Connors RSI2 Mean-Reversion Strategies"
- Volatility Box: VWAP mean reversion docs; Bollinger squeeze research
- DEV.to "Intraday Volatility Jump Mean-Reversion Strategy for BTC-USD" (Ayrat Murtazin)
- Thrive "Crypto Market Regime Detection"; Tradewink AI regime guide; Monster Trading Systems regime detection
- FerroQuant VWAP Reversion Strategy
- altFINS, Altrady, Hyrotrader, Mudrex, ChartSwatcher crypto guides
- Akash Kumar (Medium) "Market Regime Classifier for Crypto using HMMs and LSTMs"
- QuantInsti Blog "Regime-Specific Trading Using HMM and Random Forest"
- westafricatradehub, CoinSpaid capitulation / V-pattern studies
- Amberdata "Crypto Markets in Capitulation as Volatility and Fear Spike"
- AvaTrade, Kavout, Cripton AI Bollinger Band guides for crypto

---

## Confidence ladder (what to trust most)

1. **HIGH:** Donchian-55 + 200-SMA on BTC; BB mean-reversion in low-vol BTC ranges; RSI(2) Connors with trend filter; regime-conditioned BB width parameters.
2. **MEDIUM:** 20-EMA pullback (high WR but retail-heavy sourcing); VWAP reversion fade; volatility-jump mean reversion; measured move with volume confirmation.
3. **LOWER (use but verify in-house):** liquidity sweep fade (lots of smart-money literature, limited rigorous backtests); ORB on crypto (edge disputed); V-pattern capitulation (infrequent, hard to size statistically).
