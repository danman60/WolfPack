# Transcript Analysis: Trading Knowledge Extraction

**Date:** 2026-04-02
**Total files:** 39
**Unique transcripts:** 20 (19 are exact duplicates with later timestamps)
**Sources:** Tom Hougaard (7), QuantJason (7), Doug/Measured Move (1), Momentum (1), AI/Automation demos (4)

---

## 1. Summary Statistics

| Metric | Value |
|--------|-------|
| Total transcript files | 39 |
| Unique transcripts | 20 |
| Duplicate transcripts | 19 |
| Distinct strategies found | 6 |
| Fully implementable strategies | 5 |
| Psychology/mindset-only content | 3 transcripts |
| AI tooling/automation demos (no strategy) | 5 transcripts |
| Non-trading content | 1 (QuantJason joke reel) |

### Strategy Breakdown

| # | Strategy | Source | Implementable | Crypto-Compatible |
|---|----------|--------|---------------|-------------------|
| 1 | School Run (SRS) | Tom Hougaard | Yes | Adaptable |
| 2 | Anti-School Run (Anti-SRS) | Tom Hougaard | Yes | Adaptable |
| 3 | Turtle Trading (Donchian Breakout) | Richard Dennis | Yes | Yes |
| 4 | Measured Move / Opening Range | Doug | Yes | Yes |
| 5 | Trailing Stop on Higher TF | Tom Hougaard | Yes | Yes |
| 6 | Mean Reversion with Regime Classification | QuantJason | Partial | Yes |

---

## 2. Strategy Catalog

### Strategy 1: School Run (SRS) -- Tom Hougaard

**Edge Description:** Exploits the fact that the first 15-30 minutes of a session are driven by overnight order flow and institutional positioning, not the true day trend. The second 15-minute candle captures the real directional intent.

**Timeframe:** 15-minute bars (original), 30-minute bars (optimized forex variant)

**Market:** DAX (original), GBP/USD (adapted by Simply4x), applicable to any market with a defined session open

**Entry Rules:**
- Wait for market open (8:00 AM London for DAX, adaptable for crypto sessions)
- Ignore the first 15-minute candle entirely
- The second 15-minute candle (8:15-8:30) is the "School Run bar"
- **Long:** Buy when price breaks above the high of the School Run bar
- **Short:** Sell when price breaks below the low of the School Run bar

**Optimized Forex Variant (Simply4x):**
- Use 30-minute chart on GBP/USD
- Mark the 8:00 AM candle
- Wait for a subsequent 30-min candle whose **body** closes above the previous high or below the previous low
- Entry candle must form before 10:00 AM
- Stop loss: 3 pips above/below the entry candle's extreme

**Stop Loss:** Below/above the opposite extreme of the School Run bar (can be 50-130 points on DAX)

**Take Profit:** Let profits run; exit when structure breaks (lower lows in an uptrend, higher highs in a downtrend). Hougaard targets 1:1 minimum, often lets runners go.

**Risk Management:** 2% per trade on a dedicated account. Hougaard uses 50-point stops with 4 GBP/point on a 10K account.

**Win Rate:** ~70% in good months (Hougaard's reported rate)

**Key Quote:** "The first 30 minutes aren't indicative of the true trend of the day."

**Automation Potential:** HIGH. Fully mechanical entry rules. Stop and target are rule-based. The overnight range filter (Anti-SRS) adds context but is also programmable.

---

### Strategy 2: Anti-School Run (Anti-SRS) -- Tom Hougaard

**Edge Description:** When the School Run bar forms INSIDE the overnight range, conventional breakout signals are likely to fail because the market hasn't committed to a direction. Instead, fade the breakout.

**Timeframe:** 15-minute bars

**Market:** DAX primarily

**Entry Rules:**
- Define overnight range: midnight to 6:00 AM (UK time) high and low
- Identify School Run bar (second 15-min candle after open)
- **If School Run bar is INSIDE overnight range:**
  - Conventional long trigger (break above high) -> SELL SHORT instead
  - Conventional short trigger (break below low) -> DO NOT sell short (or buy instead)
- **If School Run bar is ABOVE overnight range:**
  - Buy above as normal (standard SRS)
  - Break below -> also BUY (buy the dip, trend is up)
- **If School Run bar is BELOW overnight range:**
  - Sell below as normal (standard SRS)
  - Break above -> also SELL SHORT (sell the rip, trend is down)

**Stop Loss:** ~70 points on DAX, or the size of the School Run bar

**Key Quote:** "If the school run bar takes place within the context of the overnight range, instead of buying above the high, you sell short."

**Important Caveat:** Hougaard himself sometimes overrides this with instinct based on 25+ years of experience. The mechanical rules are the base, but contextual layers (prior day overnight range tests, inside bars, buying below prior bar low) add discretionary refinement.

**Key Pattern -- Buying Below Prior Bar Low:** When price dips below a prior bar's low and immediately gets bought up, Hougaard treats this as a strong buy signal, especially when it happens near the overnight range boundary.

**Automation Potential:** HIGH for the mechanical rules. The instinct/context layer cannot be automated but the core SRS + overnight range filter is fully programmable.

---

### Strategy 3: Turtle Trading / Donchian Breakout -- Richard Dennis

**Edge Description:** Trade breakouts of N-period highs/lows with the trend, using ATR-based stops. Accept many small losses to catch large trend moves. Low win rate (~30-40%) compensated by massive risk-reward.

**Timeframe:** 1-hour (short/medium term), Daily/Weekly (long term)

**Indicators:**
- Highest High / Lowest Low (20-period for short term, 55-period for long term)
- ATR (20-period) with SMA(20) of ATR
- SMA(200) for trend direction

**Entry Rules:**
- Determine trend direction: price above SMA(200) = look for longs only; below = shorts only
- **Long:** Buy when price breaks above the 20-period highest high (or 55-period for daily)
- **Short:** Sell when price breaks below the 20-period lowest low

**Stop Loss:**
- Calculate: SMA(ATR(20)) x 2
- Place stop at: entry candle close minus (2 x ATR average) for longs
- Place stop at: entry candle close plus (2 x ATR average) for shorts

**Take Profit:**
- Exit long when price breaks below the 20-period lowest low
- Exit short when price breaks above the 20-period highest high

**Risk Management:**
- Risk no more than 2% of account per trade
- Cut losses quickly, let profits run for weeks or months
- Accept losses on ~60-70% of trades

**Key Quote:** "You don't need a positive win rate to be profitable. You can lose nine trades with a 1% stop loss and then on that one remaining trade out of 10, make 25%."

**Automation Potential:** VERY HIGH. Entirely mechanical. No discretionary elements. Already well-known and widely backtested. Perfect for algorithmic implementation.

---

### Strategy 4: Measured Move / Opening Range Breakout -- Doug

**Edge Description:** Price moves in rhythmic, repeating waves. The first 15-minute candle of the session establishes the "measured move" distance, which subsequent price waves will approximately replicate 3-5 times per day.

**Timeframe:** 15-minute (for opening range), 5-minute (for entries)

**Indicators:** None required -- pure price action

**Entry Rules:**
1. Let the first 15-minute candle close (DO NOT trade during first 15 minutes)
2. Measure the high-to-low range of that candle = the "measured move" distance
3. Switch to 5-minute chart
4. Wait for consolidation to form
5. **Long:** Buy when price breaks above consolidation range, targeting measured move distance upward
6. **Short:** Sell when price breaks below consolidation range, targeting measured move distance downward

**Stop Loss:** No more than 30% of the measured move distance

**Take Profit:** Exactly the measured move distance from the base of the breakout. Take it and leave -- do not hold for more.

**Risk Management:**
- Risk-to-reward is inherently ~1:3.3 (30% risk vs 100% target)
- Multiple trades per day possible (3-5 waves)
- Entries must be near the edges of consolidation, not in the middle

**Three Rules:**
1. Only trade breakouts from consolidation (never chase)
2. Risk max 30% of measured move
3. Take the measured move target and exit -- no greed

**Key Quote:** "The size of this next move will most likely mirror the size and speed of the first move."

**Automation Potential:** VERY HIGH. Entirely mechanical. Opening range calculation is trivial. Consolidation detection and breakout entry are straightforward to code.

---

### Strategy 5: Trailing Stop on Higher Timeframe -- Tom Hougaard

**Edge Description:** After entering on a lower timeframe (5-min), move stop management to a higher timeframe (10-min) to stay in trends longer and avoid being shaken out by noise.

**Entry Timeframe:** 5-minute
**Stop Management Timeframe:** 10-minute

**Rules:**
- Enter trade on 5-minute chart based on any setup
- Once in profit, switch to 10-minute chart for stop management
- **For shorts:** If the current 10-min bar makes a new low below the previous bar's low, move stop to just above the high of the current bar (+ small buffer ~5 points)
- **For longs:** If the current 10-min bar makes a new high above the previous bar's high, move stop to just below the low of the current bar (- small buffer)
- Continue ratcheting stop as each new bar extends the trend

**Exit Rules:**
- Stop hit (trend reversal on 10-min)
- Climactic move: a very large spike in the trend direction often marks the end (exhaustion/capitulation)

**Key Quote:** "If you are in a position initiated on a 5 minute chart, you should consider moving out to a 10 minute chart and place your stop loss according to the 10 minute chart."

**Key Quote on Exits:** "Does it hurt more to take your profits now and then seeing the market give you another 50, 60 points? Or does it hurt more to let some of your profits disappear in order to have a stop loss a little bit higher?"

**Automation Potential:** HIGH. Bar-by-bar trailing stop logic is trivial to implement. Climactic move detection is harder but optional.

---

### Strategy 6: Mean Reversion with Regime Classification -- QuantJason

**Edge Description:** Trade mean reversion (fade extended moves back to the mean) while using a regime classification tool to avoid trading during regime changes that would cause blowups.

**Details (partial -- QuantJason's content is high-level, not rule-specific):**
- Portfolio allocation: 60-80% trend following (survivorship bias assets like S&P, Gold), 20-40% mean reversion for cash flow
- Mean reversion targets: assets that deviate from their statistical norm
- Regime classification tool required to prevent blowups during regime changes
- Calmar ratio (annualized return / max drawdown) is the key metric -- target 3+ minimum, 5+ is excellent
- Fast trailing stop system improves Calmar ratio
- Stress testing: Hidden Markov Model with 10,000+ Monte Carlo simulations, NOT simple 12-month backtests

**Key Metrics:**
- Calmar ratio of 2 = okay
- Calmar ratio of 3 = decent (minimum for QuantJason's fund)
- Calmar ratio of 5+ = fantastic, suitable for leverage

**Key Quote:** "Never buy an algorithm based off of backtested data. I lost over $300,000 in a single night doing that. Always ask for live results first."

**Automation Potential:** HIGH by design (QuantJason runs algorithmic funds). However, the specific rules are not disclosed -- only the framework and principles.

---

## 3. Cross-Strategy Insights

### Common Patterns Across Sources

1. **Opening Range is Sacred:** School Run, Measured Move, and Turtle Trading all use the first N minutes/bars of a session to establish context. The first 15-30 minutes are "noise" -- the real signal comes after.

2. **Breakout + Trend Alignment:** Every mechanical strategy requires trend context before breakout entry -- SMA(200) for Turtle, overnight range for Anti-SRS, opening range direction for Measured Move.

3. **Let Winners Run, Cut Losers Fast:** Universal across Dennis, Hougaard, and Doug. Dennis accepted 60-70% loss rate. Hougaard uses higher timeframe trailing stops. Doug uses fixed measured move targets.

4. **2% Risk Per Trade is Standard:** Dennis, Hougaard, and the Momentum trader all independently advocate 2% max risk per trade.

5. **Psychology > Technique:** Hougaard, Dennis, and the Momentum trader all emphasize that most traders fail due to psychology, not strategy. "The great trader and the great trading mentality is born in the mind."

6. **Regime Awareness:** QuantJason explicitly requires regime classification. Hougaard implicitly uses it (overnight range context). WolfPack already has a regime detection module -- this validates its importance.

### Contradictions

1. **Win Rate:** Dennis/Turtle Trading thrives on LOW win rate (~30%). Hougaard's School Run reports HIGH win rate (~70%). The Measured Move targets a moderate win rate with fixed R:R. These aren't contradictions per se -- they're different risk/reward profiles that all work.

2. **Trend Following vs Mean Reversion:** QuantJason recommends a blend. WolfPack currently leans trend-following (EMA crossover, momentum, vol breakout). Adding mean reversion would diversify.

3. **Fixed Target vs Let It Run:** Doug's Measured Move prescribes exact targets (take the measured move, leave). Hougaard says let it run until structure breaks. Dennis says let it run until the opposite breakout. For automation, fixed targets are simpler; for maximizing winners, trailing stops are better. Solution: use both -- partial profit at measured move, trail the rest.

### Complementary Strategies

- **SRS + Anti-SRS** are a complete system -- they cover both breakout and mean-reversion contexts using the overnight range as the regime filter
- **Turtle Trading** is a medium/long-term trend capture strategy that complements the intraday SRS and Measured Move
- **Measured Move** provides intraday target calibration that any breakout strategy (SRS, ORB, Turtle) can use for position sizing and target setting
- **Trailing Stop on Higher TF** is a trade management technique that enhances any entry strategy

---

## 4. Implementation Priority

Ranked by: clarity of rules (can we code it?), crypto compatibility, complementarity with existing WolfPack strategies (EMA crossover, regime momentum, vol breakout, ORB session).

### Priority 1: Measured Move / Opening Range (HIGHEST)

**Why:** Fully mechanical, no indicators needed, provides exact entry/stop/target framework. WolfPack already has ORB session strategy -- Measured Move enhances it with target calibration. Directly applicable to crypto perpetual futures with defined session opens (Asian, London, NY). The 3:1+ R:R and "only trade from consolidation" rule makes it robust.

**Effort:** Low. Calculate first-candle range, detect consolidation breakout, set target = range distance, stop = 30% of range.

**Complementarity:** Extends the existing ORB session strategy with measured move targets instead of arbitrary take-profits.

### Priority 2: Turtle Trading / Donchian Breakout

**Why:** Battle-tested over 40+ years. Completely mechanical. Excellent for crypto's trending nature. Uses ATR which WolfPack already calculates. 20-period Donchian channels + 200 SMA trend filter + ATR stop = simple stack.

**Effort:** Low-Medium. Donchian channels are trivial. ATR-based stops already conceptually exist in WolfPack's volatility module.

**Complementarity:** Provides a multi-day/week trend-following system to complement the existing intraday strategies. WolfPack's regime module can filter entries to only take Turtle signals in trending regimes.

### Priority 3: School Run + Anti-SRS (Session Breakout with Overnight Range Filter)

**Why:** Hougaard's most well-defined system. The overnight range filter adds meaningful edge over basic ORB. For crypto, define "overnight" as a configurable low-volume period (e.g., 00:00-06:00 UTC for most pairs).

**Effort:** Medium. Requires defining session open, overnight range, classifying bar position relative to range. The anti-SRS logic (fade breakouts inside range) is the novel part.

**Complementarity:** Replaces or enhances the current ORB session strategy with a more nuanced entry logic (breakout vs fade based on overnight range context).

### Priority 4: Trailing Stop on Higher Timeframe

**Why:** Not an entry strategy but a trade management overlay. Applies to ALL existing strategies. Simple to implement. Significantly improves profit capture.

**Effort:** Very Low. Bar-by-bar comparison of highs/lows on a higher timeframe.

**Complementarity:** Universal improvement to trade management across all WolfPack strategies.

### Priority 5: Mean Reversion with Regime Classification

**Why:** QuantJason's framework validates WolfPack's regime detection module. However, specific rules are not provided -- only the framework. Would need to design entry/exit rules from scratch.

**Effort:** High. Framework only, no concrete rules. Need to define: what constitutes "extended from mean", what mean to use (VWAP? moving average?), regime classification criteria for enable/disable.

**Complementarity:** High -- provides the missing counter-trend strategy. WolfPack is currently trend-only. A mean reversion layer would catch profits in ranging markets where trend strategies chop.

---

## 5. Knowledge Gaps

### Missing Information

1. **Hougaard's exact position sizing formula for School Run:** He mentions adding to winners aggressively but doesn't detail the scaling rules.

2. **Anti-SRS stop loss placement:** Hougaard mentions "approximately 70 points" for DAX but doesn't give a systematic rule. The bar-size stop (full range of School Run bar) is one option he mentions. Need backtesting to determine optimal.

3. **QuantJason's specific mean reversion entry/exit rules:** He discusses the framework (Calmar ratio, regime classification, Monte Carlo stress testing) but never reveals his actual algorithm's logic. We have principles, not rules.

4. **Crypto session definitions:** All strategies are designed for traditional markets with defined opens. For 24/7 crypto markets, we need to define:
   - What constitutes "session open" (UTC 00:00? Major exchange opens?)
   - What is the "overnight range" in a market that never closes?
   - Testing multiple session definitions (Asian 00:00-08:00 UTC, London 08:00-16:00, NY 13:00-21:00) to find optimal SRS timing

5. **Measured Move validity in crypto:** Doug demonstrates on stocks and futures. Crypto's 24/7 nature and different volume profiles may affect the measured move's reliability. Needs backtesting.

6. **Interaction effects:** When multiple strategies signal simultaneously (e.g., Turtle breakout + SRS + Measured Move all agree), how to size the combined position. No transcript addresses portfolio-level strategy interaction.

7. **Market regime transitions:** QuantJason emphasizes regime classification but doesn't specify: which regime model? How many states? What are the transition rules? WolfPack's existing regime module needs validation against these principles.

### Transcripts with No Strategy Content

The following transcripts contained no extractable trading strategies:
- **timkoda_**: Claude Code creative automation (not trading)
- **Jackson Locschinskey**: AI chart analysis tool promotion (no strategy rules)
- **Mariana Antaya (trading bot)**: Replit trading bot demo (no strategy, just tooling)
- **Mariana Antaya (quant tools)**: NVIDIA portfolio optimization + KX news pipeline (infrastructure, not strategy)
- **Alpha Insider**: Claude + PineScript backtesting workflow demo (no specific strategy)
- **Tradingwithmustafah**: Using ChatGPT to generate Tom Hougaard PineScript (no new strategy)
- **QuantJason (toilet paper reel)**: Comedy, not trading
- **QuantJason (teach me reel)**: Promotional, not trading
- **QuantJason (VPS/platforms)**: Infrastructure guidance only (NinjaTrader vs MT5)

---

## 6. Key Quotes Compendium

### On Psychology
> "The great trader and the great trading mentality is born in the mind. That's where you start." -- Tom Hougaard

> "The only thing that separates me to Tiger Woods is desire and repetition." -- Tom Hougaard

> "You don't need a positive win rate to be profitable." -- Richard Dennis (via narrator)

> "Walk away from the charts whenever you are overconfident, scared, anxious, excited." -- Momentum trader

### On Risk Management
> "Risk no more than 2% of your account on each trade." -- Richard Dennis

> "Risk no more than a half percent to one percent in every trade you take." -- Momentum trader

> "You should not risk anymore than 30% of [the measured move] on this trade." -- Doug

> "Never buy an algorithm based off of backtested data. I lost over $300,000 in a single night doing that." -- QuantJason

### On Strategy
> "The first 30 minutes aren't indicative of the true trend of the day." -- Tom Hougaard

> "If the school run bar takes place within the context of the overnight range, instead of buying above the high, you sell short." -- Tom Hougaard

> "The size of this next move will most likely mirror the size and speed of the first move." -- Doug

> "Easy ways to increase Calmar would be to add a fast trailing stop system and to add a regime classification tool." -- QuantJason

### On Indicators
> "All you need for the best entries are the EMAs and VWAP." -- Momentum trader

> "If price is far above the 9 EMA, don't take the trade. If price is over 10% above VWAP, don't take the trade." -- Momentum trader

> "I don't think institutional traders are getting their wires twisted because they see a doji or a hanging man." -- Tom Hougaard
