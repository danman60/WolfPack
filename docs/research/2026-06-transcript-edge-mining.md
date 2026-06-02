# Transcript Edge Mining — 2026-06

Mined every `.txt` transcript in `docs/transcripts/` (54 files, ~37 unique by content; the rest are duplicate re-transcriptions of the same source). Goal: extract concrete, codifiable trading mechanics, separate signal from guru-noise, map to WolfPack's crypto-perps harness.

**Important codebase finding:** WolfPack already implements the three most concretely-specified mechanical strategies found here — `orb_session.py` (= School Run, already with the FVG/displacement variant baked in), `measured_move.py` (= Doug's 3-step), and `turtle_donchian.py` (= Dennis/Turtle). The transcripts mostly confirm/parameterize existing modules rather than introduce new ones. Embedded code comments show prior research agents already validated 55-day Turtle > 20-day on crypto.

---

## 1. Source → strategy → tag → one-liner

| # | Source / creator | Strategy name | Tag | One-line method |
|---|---|---|---|---|
| 1 | Tom Hougaard | School Run (SRS) | **MECHANICAL** | Break of the 2nd 15-min candle after session open; buy above / sell below. |
| 2 | Tom Hougaard | Anti-SRS (overnight-range conditioning) | DISCRETIONARY | Invert SRS when the school-run bar sits *inside* the overnight (00:00–06:00) range. Hougaard himself overrides it on instinct — see notes. |
| 3 | "Simply 4X" (reaction vid) | Simplified School Run | **MECHANICAL** | GBPUSD 30-min: after 8am candle, enter when a candle *body* breaks prior candle high/low before 10am; stop 3 pips beyond; 1:1 then runner. |
| 4 | Doug (26-yr trader) | Measured Move / "3-step basic math" | **MECHANICAL** | 15-min opening-range height = target. After consolidation, trade the break of consolidation toward a measured-move target = OR height; risk = 30% of target. |
| 5 | Richard Dennis / Turtles | Turtle trend-following | **MECHANICAL** | 20- (or 55-) period Donchian breakout in direction of 200-SMA; 2×ATR(20) stop; exit on opposite-channel break; risk fixed %. |
| 6 | Tom Hougaard | Trailing-stop / stop-loss philosophy | **MECHANICAL** (the stop rule) | Trail stop to just beyond the high/low of the current bar each time that bar makes a new extreme vs prior bar (on 10-min after a 5-min entry). |
| 7 | "Boring strategy" (FB reel) | 9:30 ORB + FVG | **MECHANICAL** | Mark first 5-min candle hi/lo; on break require FVG displacement, retest of FVG, engulfing confirmation; stop 1 tick beyond retest candle; fixed 3:1. |
| 8 | Tradingwithmustafah | Liquidity sweep + Break-of-Structure | **MECHANICAL** (loose) | Wait for HTF liquidity sweep of prior hi/lo → 1-min break of structure opposite → enter, stop under swept liquidity, target 1:2. |
| 9 | "Friday trader" (FB reel) | EMA-pullback + VWAP | DISCRETIONARY | 1-min: pullback to 9/20/50 EMA that price "respects" + price the right side of VWAP; skip if 9 EMA < 20 EMA. |
| 10 | FB reel (SMA 200/400) | "Value zone" consolidation breakout | **MECHANICAL** (loose) | 5-min: zone between SMA(200) & SMA(400); when price consolidates *tightly* inside it then breaks, trade the break. |
| 11 | quantjason | Algo-trading meta (styles/infra/backtest/Calmar) | GURU-NOISE (but useful infra) | No entry rules; commentary on VPS/latency, trend vs mean-reversion, Monte-Carlo/HMM stress testing, Calmar ratio, regime classification. |
| 12 | Rick Traders | FVG reversal / continuation-end | DISCRETIONARY | BoS + displacement; reversal when pullback fails to displace and aligns with a 4h FVG. |
| 13 | Aleks Rosme | Orderflow 4-step learning path | DISCRETIONARY | Structural levels → auction/value → options/gamma → volume+delta profile (POC/HVN/LVN) → footprint/bookmap. Curriculum, not a setup. |
| 14 | Max Anthony | 15-min ORB + S/R | GURU-NOISE | "I love the 15-min ORB, keep it simple, S/R + RSI." No rules given. |
| 15 | AnthonyFX | BTC 30-min break-and-retest idea | GURU-NOISE | Single discretionary call: "broke structure bullish, wait for pullback + breakout." |
| 16 | "10 years in 60s" reel | Risk-management checklist | GURU-NOISE (good risk rules) | EMA/VWAP magnet filters; risk 0.5–1%/trade; daily max loss 3% (stop after 3 full losses). |
| 17 | LuxAlgo "can't be real" | AI strategy finder | GURU-NOISE | AI picks a 5-min strategy with profit factor >2 / 50+ trades — then it hits its biggest drawdown live. Cautionary, not a method. |
| 18 | "Backtest with Claude" | LLM→PineScript→TradingView | GURU-NOISE (useful tooling) | Generate PineScript via Claude, backtest on TV, webhook to broker. Notes it failed to beat buy-and-hold. |
| 19 | alphanseider.com promo | Forward-test marketplace | GURU-NOISE (useful concept) | Use forward-tested (live, not backtested) strategies; auto-trade via broker connect. Reinforces forward-test > backtest. |
| 20 | Jackson Locschinskey (x2) | "AI chart analyzer" tool | GURU-NOISE | Screenshot chart → AI tells you entry/SL/TP. Ad. |
| 21 | Replit agent reel | "Build a trading bot" | GURU-NOISE | Vibe-code an alert bot off Alpaca API. Ad. |
| 22 | timkoda_ | Claude creative-stack | GURU-NOISE (off-topic) | Not trading — content-pipeline agents. |
| 23 | "Creating mentor's strategy with AI" | LLM→PineScript for "Trader Tom" | GURU-NOISE | Ask ChatGPT to build "Trader Tom's strategy" as PineScript. No rules. |
| 24 | NVIDIA/KX GTC reel | Quant infra tools | GURU-NOISE (off-topic) | Portfolio-optimization blueprint, KX time-series DB, news-labeling LLM. Infra name-drops. |
| 25 | Giga Qian | China "MiroFish" AI swarm predictor | GURU-NOISE (off-topic) | Open-source million-agent simulation tool. Product news, no trading method. |
| 26 | Hougaard "1% who succeed" | Mindset interview | GURU-NOISE | Pure psychology/discipline. No method. |
| 27 | Hougaard "Video 1 2025" | Channel admin / account audit | GURU-NOISE | Account-size policy, 2% risk per trade reaffirmed. No setup. |

---

## 2. Full extracted rulesets (MECHANICAL only)

### #1 / #3 — School Run (SRS) — Tom Hougaard
- **Instrument/TF:** DAX index, 15-min (Hougaard); reaction-channel variant uses GBPUSD 30-min.
- **Session:** Tied to *equity/futures open* (08:00 UK). The "school run bar" = the **2nd candle after open** (08:15–08:30 on 15-min).
- **Entry:** Buy a break **above** the school-run bar high; short a break **below** its low. A plain breakout. Hougaard also tested 6× 5-min candles instead of 2× 15-min — "narrower TF = more false signals," so he kept 15-min.
- **Reaction-vid refinement (#3):** require the *body* (not wick) of a later 30-min candle to close beyond the prior candle's hi/lo; entry must occur **before 10am**; stop 3 pips beyond the opposite extreme; **target 1:1**, then leave a runner.
- **Stop:** Conventional = beyond opposite side of school-run bar (can be large — 130-pt bar example needed ~70-pt stop in his anti variant).
- **Performance claim:** months of ~70% hit rate; he adds to winners ("aggressive trader").

### #2 — Anti-SRS overnight-range conditioning — Tom Hougaard
- **Definition:** Overnight range = 00:00–06:00 UK.
- **Rule:** If the school-run bar/trigger occurs *inside* the overnight range → **invert** the SRS signal (long trigger → short, short trigger → long). If it occurs *above* the overnight range → buy both above (normal SRS) **and** below prior-bar low. Below the overnight range → sell both below and above.
- **Tag = DISCRETIONARY despite the rule grid:** the entire 47-min "anti-SRS" review is Hougaard *overriding his own rule on instinct* trade after trade (admits "I cannot teach instinct," "I should have been short there but did nothing"). A frustrated student literally messaged him that he stopped following his own principles. **Codify the rule grid, but treat the live edge as unproven** — the author can't follow it mechanically himself.

### #4 — Measured Move / 3-step — Doug
- **Instrument/TF:** Any (demoed on Tesla, NQ futures). 15-min to *define*, 5-min to *execute*.
- **Step 1 (skip first 15m):** Let the first 15-min candle after the official open close. **Do not trade the first 15 minutes** ("death zone").
- **Step 2 (measured move):** Measure full hi→lo height of that opening candle (wicks included) = the **measured move** = profit target distance.
- **Step 3 (entry):** Drop to 5-min. Only trade *out of consolidation* (never chase). Enter on the break of the consolidation box at the OR high/low line, toward a measured-move target = OR height projected from the base of the originating move.
- **Risk:** ≤ **30% of the measured move** (e.g. $5 MM → ~$1.50 stop just beyond the breakout candle).
- **Exit:** Take the measured move and leave ("came for 5, get 5, we leave"). The pattern often repeats 2–3× per session.

### #5 — Turtle / Donchian trend-following — Richard Dennis
- **Instrument/TF:** Any liquid trending market (gold, S&P). 1-hour for short/medium; daily/weekly use 55-period.
- **Indicators:** Highest-high/lowest-low channel period **20** (or **55** on higher TF — only the upper band on HTF), **ATR(20)** smoothed SMA, **SMA(200)** trend filter.
- **Entry:** Price above SMA(200) → take **bullish** breakouts of the 20/55-period prior high (and inverse for shorts below SMA200).
- **Stop:** From the close of the breakout candle, subtract **2 × ATR(20)**.
- **Exit / profit:** Let it run; exit when the *opposite* recent low/high breaks (a Donchian structural exit — classic Turtle uses the 10-period opposite channel).
- **Risk:** Fixed **2% per trade**. Negative-expectancy win rate is fine — large trend winners pay for many small losers. Cut losses fast, let profits run.

### #6 — Hougaard trailing-stop rule (the codifiable part of the "philosophy" vid)
- After entry, switch the stop-management TF up one step (5-min entry → manage on 10-min).
- **Rule:** Each time the current bar makes a new low below the prior bar's low (for a short), move the stop to **just above the current bar's high**. Mirror for longs. Keep ratcheting as long as each new bar extends the move.
- **Target philosophy:** No fixed RR target — "I don't have a crystal ball." Hold until a *climactic volume spike* against the trend or the trailing stop is hit.

### #7 — 9:30 ORB + FVG ("boring strategy")
- **Instrument/TF:** US equities/index, 5-min, **09:30 ET** session open.
- **Setup:** Mark hi/lo of the **first 5-min candle** (09:30–09:35).
- **Entry trigger:** Price breaks the OR hi/lo *with displacement* — confirmed by a **Fair Value Gap** (expansive middle candle with gaps before/after wicks). Then wait for a **retest into the FVG**, then an **engulfing candle** covering the retest candle → enter.
- **Stop:** 1 tick beyond the retest candle's low/high.
- **Target:** Fixed **3:1 RR**.
- *(This is exactly the FVG-filter path already implemented in WolfPack's `orb_session.py`.)*

### #8 — Liquidity sweep + Break-of-Structure — Tradingwithmustafah
- **Setup:** HTF liquidity level (prior daily/weekly/overnight hi-lo) gets **swept** (price wicks beyond then rejects).
- **Entry:** On the **1-min**, wait for a **break of structure** in the opposite direction; enter on that break.
- **Stop:** Just **under the swept liquidity** (the wick extreme).
- **Target:** **1:2** (claims 3–4 setups/week). Loose because "break of structure" and "liquidity" need formal definitions to backtest — see candidate notes.

### #10 — SMA 200/400 "value zone" breakout (FB reel)
- **TF:** 5-min. Plot SMA(200) and SMA(400). The band between them = "value zone."
- **Filter:** Only trade when the value zone is **tight** (the two SMAs close together — i.e. low recent trend slope).
- **Entry:** When price enters the tight value zone, consolidates, then breaks the consolidation → trade the break direction. No stop/target specified.

---

## 3. Ranked shortlist — top automatable + crypto-transferable

> Crypto is 24/7, so equity "session open" is not a hard premise — but a crypto analog exists: **NY equity/CME open (13:30 UTC), London (08:00 UTC), daily UTC open (00:00), and funding-reset times (00:00/08:00/16:00 UTC on Hyperliquid)**. WolfPack's `orb_session.py`/`measured_move.py` already encode NY/London/Asia opens in UTC.

### Candidate 1 — Turtle/Donchian 55-period, regime-gated (HIGHEST conviction)
- **Why it might work:** Trend-following is the one style with genuine multi-decade, multi-asset evidence, and crypto perps trend hard. WolfPack already has `turtle_donchian.py` with a 200-SMA filter and regime gating; embedded comments cite a prior agent finding 55-day Turtle beats 20-day on crypto (HTX/AQR), and that the live 20-day variant had only 31.6% WR / −$62 over 19 trades. The fix (55-period) is one parameter.
- **Concrete next backtest:** Run `backtest_engine` on BTC/ETH/LINK, `breakout_period=55`, ATR(20)×2 stop, SMA(200) filter, regime gate = TRENDING_UP/DOWN only, over the last 12–18 months of perps data. Compare WR / Calmar / max-DD vs the current 20-period default. Validate with the `monte_carlo.py` module (quantjason's point: 10k Monte-Carlo / drawdown stress, not single-path).

### Candidate 2 — ORB + FVG at funding-reset / NY open (already built, needs re-validation)
- **Why it might work:** The session-open volatility premise maps to crypto's funding-reset bursts and the 13:30 UTC CME open, where TradFi flows hit BTC. WolfPack's `orb_session.py` already implements School Run + the FVG/displacement/retest/engulfing chain from the "boring strategy" reel — i.e. transcripts #1, #3, #7 are the *same* family and are coded.
- **Concrete next backtest:** Sweep `session ∈ {ny, london, asia}` and an added "funding_reset" pseudo-session (00:00/08:00/16:00 UTC) on BTC/ETH; `fvg_filter on/off`; observation 15–30 min; fixed 3:1 vs 1:1+runner. Measure whether any single session/time-window carries the edge (the equity premise says NY/London should dominate; if Asia/funding-reset wins, that's the crypto-specific signal).

### Candidate 3 — Measured Move with consolidation filter (already built)
- **Why it might work:** Pure volatility-normalized target (target = opening-range height) travels across instruments better than fixed pip/point targets, and the "no-chase, only-trade-out-of-consolidation" rule is a clean, codifiable filter. `measured_move.py` exists.
- **Concrete next backtest:** On BTC/ETH 5-min, parameterize `opening_range_minutes ∈ {5,15,30}`, `consolidation_lookback ∈ {3..12}`, risk = 30% of measured move. Key question to answer: does the "OR-height repeats 2–3×/day" claim hold in crypto, or does crypto's fatter tails blow through the 30%-of-MM stop too often? Report stop-hit rate vs target-hit rate.

### Candidate 4 — Liquidity-sweep + BoS reversal (needs formalization first)
- **Why it might work:** Crypto perps are notorious for stop-hunt wicks beyond prior daily/weekly hi-lo (liquidation cascades), which is precisely the "sweep" Mustafah describes — and WolfPack has `structural_levels.py` to source those levels.
- **Concrete next backtest:** First *formalize* "sweep" (wick beyond prior daily hi/lo by ≥ X bps, close back inside within N candles) and "BoS" (break of last 1-min swing). Then backtest entry on BoS-after-sweep, stop beyond the sweep wick, target 1:2, BTC/ETH. This is the only shortlist item **not** already implemented — build it from `structural_levels.py` outputs.

### Candidate 5 (overlay, not a strategy) — Hougaard volatility trailing stop
- **Why:** A pure exit-management rule that can be layered on ANY of the above. "Move stop beyond the current bar's extreme each time the bar extends the move" is a structural trailing stop independent of entry.
- **Concrete next backtest:** A/B the existing fixed-stop exits in `turtle_donchian` / `orb_session` against this bar-extreme trailing stop on the same trade set; measure avg-win expansion vs WR contraction.

---

## 4. Honest noise count

- **Unique sources:** ~27 (after collapsing 54 files of duplicate re-transcriptions).
- **MECHANICAL (codifiable rules present):** **8** — #1/#3 School Run, #4 Measured Move, #5 Turtle, #6 trailing-stop rule, #7 9:30-ORB+FVG, #8 liquidity-sweep+BoS (loose), #10 SMA value-zone (loose).
- **DISCRETIONARY (real method, needs human judgment):** **4** — #2 anti-SRS, #9 EMA/VWAP pullback, #12 FVG reversal, #13 orderflow curriculum.
- **GURU-NOISE (no method / ads / off-topic / pure mindset):** **15** — #11 quantjason (infra-useful but no setup), #14–27 minus the discretionary ones. Of these, the genuinely *off-topic* (not even trading) are 5: timkoda creative stack, Replit bot ad, NVIDIA/KX infra, MiroFish, and the AI-chart-analyzer ads.

**Bottom line:** Roughly **8 of ~27 unique sources carry real codifiable rules**, and **3 of those are already implemented in WolfPack** (ORB/School Run, Measured Move, Turtle). The transcript corpus's net new contribution is mostly (a) better *parameters* for existing modules (55-period Turtle, FVG chain, funding-reset session), (b) one un-built candidate (liquidity-sweep+BoS reversal), and (c) one reusable exit overlay (bar-extreme trailing stop). The guru-noise is real and high (~55%) but the mechanical minority is concrete enough to backtest directly.
