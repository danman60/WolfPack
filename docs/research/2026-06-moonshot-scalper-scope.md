# Moonshot Scalper — Feasibility & Design Spike

**Date:** 2026-06-01
**Status:** DESIGN ONLY — no code/config/wallet changes made.
**Idea (user):** A "moonshot scalper" run by Snoop. Hunt low-mcap, high-social-buzz tokens with a promising chart, make small aggressive bets — quick long, in and out fast. Asymmetric: small size, many shots, let winners run briefly, cut fast.

All findings below verified against repo code + live Hyperliquid/dYdX/CoinGecko APIs on 2026-06-01. Where I couldn't verify, it's flagged.

---

## TL;DR verdict

- **Executable today? YES — on Hyperliquid.** 179 active perps; **117 have <$1M/24h volume, 153 have <$5M.** Hyperliquid natively lists exactly the small/low-cap names the idea targets (RSR, XAI, TURBO, 0G, BOME, GOAT, NOT, etc.). Order execution is symbol-agnostic — `hyperliquid_trading.py` resolves any listed symbol by asset index. **No on-chain/Uniswap taker-swap is needed for the listed subset, and that's good — because Uniswap code is LP-only, no taker swaps wired.**
- **Buzz signal? MAJORS-ONLY today.** `social_sentiment.py` only resolves community/social scores for **19 hardcoded CoinGecko IDs** (BTC/ETH/SOL/LINK/... none of the true small-caps). Trending list is generic, not a per-token score. To score arbitrary small-caps you must extend the CoinGecko ID map / resolve IDs dynamically. This is the **real build gap**, not execution.
- **Backtest? FORWARD-WATCH, not backtest.** Survivorship bias (dead moonshots vanish from the universe) + no historical social-buzz data make a backtest dishonest. Validate by logging signals live and paper-trading.
- **Recommendation: BUILD a forward-watch prototype (paper-only), not a live strategy yet.** Smallest first step in "Smallest viable first step" below.

---

## 1. Existing-pieces inventory

| Module / file | What it actually does | Live / stub | Reusable for moonshot? |
|---|---|---|---|
| `exchanges/hyperliquid.py` | `metaAndAssetCtxs` → full perp universe w/ markPx, 24h vol (`dayNtlVlm`), OI, funding, maxLeverage. `get_candles` (1m–1d), `get_orderbook` (L2). | **LIVE** | **YES — core.** This is the small-cap screener data source. Already pulls everything needed (vol, OI, lev) for all 179 perps in one call. |
| `exchanges/hyperliquid_trading.py` | EIP-712 signed order placement. `_get_asset_index` maps **any** listed symbol → index. Market (IOC) + limit. | **LIVE (needs `HYPERLIQUID_PRIVATE_KEY`)** | **YES.** Symbol-agnostic; trades any perp. No code change to trade small-caps. |
| `exchanges/dydx.py` | dYdX v4 indexer. `get_markets` → perp list. maxLeverage hardcoded 20. | **LIVE** | Marginal — dYdX universe far smaller, majors-skewed (see §2). Not the venue for moonshots. |
| `modules/social_sentiment.py` | alternative.me Fear&Greed + CoinGecko trending(7) + CoinGecko per-coin community/dev score. **Per-coin score gated by `_COINGECKO_IDS` (19 majors only).** | **LIVE but majors-only** | **PARTIAL — the gap.** Trending list reusable as a buzz trigger; per-token score needs ID-map extension. |
| `agents/snoop.py` | LLM agent. Consumes regime/funding/vol/liquidity + `social_sentiment` + `whale_tracker` dicts for ONE symbol; emits sentiment_score, crowd_positioning, narrative_momentum, contrarian_signal, conviction. | **LIVE** | **YES — the brain.** Already structured to ingest social+whale and emit conviction. Needs to be pointed at a candidate small-cap with that token's social/whale context. |
| `modules/whale_tracker.py` | Hyperliquid `recentTrades`, filters ≥$100k notional, net buy/sell bias. | **LIVE (Hyperliquid only)** | **YES but threshold wrong for small-caps.** $100k is huge on a $138k-OI token. Needs a per-token adaptive threshold (e.g. % of OI). |
| `modules/momentum_buckets.py` | Discrete price-bucket momentum, multi-window (5/13/34/55 bar), adaptive bucket size, regime_hint (trending/breakout/choppy). | **LIVE (pure candle math)** | **YES — the chart trigger.** `regime_hint == "breakout"` + positive momentum_score is exactly the "promising chart" signal. Symbol-agnostic. |
| `modules/volume_profile.py` | (present) volume-by-price / VWAP context. | LIVE (candle math) | Secondary — confirm breakout above value. |
| `modules/structural_levels.py` | swing highs/lows / S-R. | LIVE | Secondary — stop placement reference. |
| `modules/liquidity.py` | orderbook-derived liquidity/depth. | LIVE | **YES — gating.** Use to reject illiquid candidates pre-trade (see risk §5). |
| `strategies/vol_breakout.py`, `strategies/base.py` | Strategy ABC: `evaluate(candles, idx) -> Brief-format rec dict`. Backtest + live share this contract. | LIVE | **YES — the template.** A `MoonshotScalperStrategy` subclasses `Strategy`, emits the same rec dict; plugs into `STRATEGIES` registry + auto_trader with no engine changes. |
| `auto_trader.py` | Per-wallet config gates: `symbol_whitelist`, `strategy_whitelist`, `direction_whitelist`, `disabled_strategies`, `regime_router_enabled`, conviction floors, veto, circuit breaker, VWAP/pump guards, per-symbol mechanical stops. | LIVE | **YES — already has the levers.** A moonshot wallet = a new `paper_perp_v{N}` with `symbol_whitelist` = candidate set, `strategy_whitelist` = ["moonshot_scalper"], `direction_whitelist` = ["long"]. No global trading-logic change. |
| `backtest_engine.py` + `paper_trading.py` | Replays candles through real PaperTradingEngine. Per-asset slippage table (`SLIPPAGE_BPS`), ATR-scaled dynamic slippage, stop-slippage, funding sim. | LIVE | Backtest path exists BUT slippage table has no small-cap entries (defaults to 10bps — far too tight, see §5) and survivorship makes backtest invalid (§4). |

---

## 2. Venue / universe reality

**Hyperliquid — verified live (`metaAndAssetCtxs`, 2026-06-01):**
- **230 perps listed total; 51 delisted; 179 active.**
- maxLeverage distribution (active): `3x: 89, 5x: 55, 10x: 31, 20x: 2, 25x: 1, 40x: 1`. Hyperliquid caps the riskiest/smallest names at **3x** — a built-in universe proxy: **the 89 perps at 3x are HL's own "small/illiquid" tier.**
- **117 perps under $1M/24h volume; 153 under $5M.**
- Smallest active by 24h volume: RSR ($17k vol, $139k OI), TNSR ($21k), XAI ($25k), TURBO ($45k), RESOLV, 0G, MINA, UMA, BOME, GOAT, NOT...

**This is the central finding: Hyperliquid IS the moonshot venue. No on-chain execution required for these.** The idea's worst-case blocker (moonshots only tradeable via Uniswap taker swaps, which WolfPack can't do — Uniswap code is `lp_*` LP-only, confirmed no swap path) **does not bind**, because the targeted token class is already on HL perps.

Caveat: HL's small-caps are *established* alts, not brand-new microcaps. A token that listed on a DEX yesterday with a $2M mcap is NOT on HL. So "moonshot" here = **HL's low-volume / 3x-lev tier** (RSR/XAI/TURBO class), not literal first-day launches. If the user means genuine fresh launches, that's an on-chain taker-swap build that does not exist and is a much larger project — flag for user decision.

**dYdX — verified live (`/perpetualMarkets`):** universe is smaller and majors-skewed; not the moonshot venue. Use HL.

**Uniswap V3:** repo has `lp_pool_scanner`, `lp_fee_manager`, `lp_range_calculator`, `lp_rebalance`, `lp_monitor` — **all LP provisioning. No taker-swap / market-buy path.** Confirmed: WolfPack cannot market-buy an arbitrary on-chain token today. Not a blocker for the HL subset; IS a blocker for true microcaps.

---

## 3. Concrete screen + entry/exit/risk ruleset

### Screen (codifiable, all from data WolfPack already pulls)
Run over the 179 active HL perps each cycle:

1. **Universe / liquidity floor (hard gate):**
   - maxLeverage ≤ 5x (HL's small-cap tier) — captures the 144 small/mid names; OR explicit mcap-proxy: OI between $100k and $25M.
   - 24h volume between **$250k and $15M** (low enough to be "small-cap," high enough to fill a tiny order). Floor rejects untradeable dust (RSR's $17k vol = can't even fill $1k without moving it).
   - Live spread (top-of-book) **≤ 25 bps** at evaluation time (rejects RSR-class 42bps books).
2. **Buzz threshold (the metric):** `buzz_score` ∈ [0,100], defined as:
   `buzz_score = 50*is_trending_on_coingecko + 0.5*coingecko_community_score_normalized + (whale_net_buy_bias>0 ? 25 : 0)`
   Require **buzz_score ≥ 60** OR token appears in CoinGecko trending top-7. (Needs the ID-map extension from §1 to score arbitrary tokens — until then, buzz reduces to "is it trending + whale bias.")
3. **Chart trigger (`momentum_buckets`):** `regime_hint == "breakout"` AND `momentum_score ≥ 0.4` AND `conviction ≥ 0.5` on 5m or 15m candles. (= short windows hot, long windows flat = fresh breakout.)
4. **Snoop gate:** route the candidate through `SnoopAgent.analyze` with that token's social+whale context; require `conviction ≥ 55` and `crowd_positioning != "crowded_long"` (don't buy the top).

A candidate passing 1–4 is a "shot."

### Entry / exit / risk (asymmetric small-bet)
- **Direction:** long only (`direction_whitelist=["long"]`). The idea is moonshot upside, not shorting illiquid names (short squeeze risk on thin books is brutal).
- **Size:** **0.5% equity per shot** (small, many shots). Hard cap **max 4 concurrent shots** → ≤2% equity at risk in the sleeve. On $1k live this is $5/shot — deliberately tiny while edge is unproven.
- **Stop:** **−4%** hard mechanical stop (small-caps gap; tight stops get wicked, wide stops blow the asymmetry — 4% is the compromise; tune in forward-watch). Use `STOP_SLIPPAGE_BPS`-style adverse fill assumption, but raised for thin books (§5).
- **Take-profit / let-winners-run:** scale — take 50% off at **+8%**, trail the rest with a **−5% chandelier stop from peak**. Max upside capture without round-tripping.
- **Max hold time:** **90 minutes.** If not at +8% in 90m, the "fast money" thesis failed — close. (Scalper, not a swing.)
- **Asymmetry math:** 0.5% size, −4% stop = **−0.02% equity per loss**. A 50%-off-at-+8% then trail winner ≈ +6–15% on the position = **+0.03% to +0.075% equity per win.** At 25% win rate (consistent with the repo's documented BTC-long ~33% WR), expected value is roughly breakeven-to-slightly-positive *before* the rare runner. The edge is entirely in the trailed tail — one +40% runner (+0.2% equity) covers ~10 stops. **This only works if winners genuinely run; forward-watch must measure the tail, not the win rate.**

### Plumbing (no global change)
- New `MoonshotScalperStrategy(Strategy)` in `strategies/`, registered in `STRATEGIES`.
- New wallet `paper_perp_v{N}` ("Moonshot Scalper" thesis) with `parent_wallet_id`, `generation`, `display_name`, `description`, and config: `strategy_whitelist=["moonshot_scalper"]`, `direction_whitelist=["long"]`, `symbol_whitelist` = the live screened candidate set, small size caps.
- A pre-cycle **screener job** writes the current candidate `symbol_whitelist` into that wallet's config (the screen runs over all 179 perps; the wallet only trades the survivors).

---

## 4. Backtestability + survivorship bias

**Honest answer: not backtestable in a way you can trust. Forward-watch only.**

Two independent killers:
1. **Survivorship bias.** Dead moonshots get **delisted** — verified: 51 of 230 HL perps already carry `isDelisted`. They vanish from the universe. Any backtest over "currently-listed small-caps" only sees the survivors, systematically inflating returns (the −90% rugs that would've stopped you out aren't in the data). This is the textbook bias and it's severe for this exact strategy.
2. **No historical buzz data.** `social_sentiment` reads CoinGecko *current* trending + *current* community scores. There is **no stored time series** of past buzz. You cannot reconstruct "was XAI trending on 2026-03-12 at 14:00?" The buzz half of the signal is unbacktestable, full stop.

Partial/sanity backtest you *can* run (label it for what it is): the `momentum_buckets` breakout trigger + stop/TP rules can be replayed on HL 1m/5m candles for *currently-listed* small-caps to sanity-check the mechanical exit logic (do the stops/TPs behave, is the per-trade cost survivable). **Verified 1m candles are available for small-caps** (XAI returned 119 1m bars). But treat the P&L as upper-bound fantasy due to (1) and the missing buzz gate.

**Realistic validation path — FORWARD WATCH:**
1. Run the screen + Snoop gate live every cycle; **log every "shot" signal** (symbol, buzz_score, momentum, Snoop conviction, spread, entry) to a new table (e.g. `wp_moonshot_signals` — none exists today). *No money.*
2. Simultaneously paper-trade the full ruleset in `paper_perp_v{N}` through the existing PaperTradingEngine (real slippage/funding sim).
3. After 4–6 weeks: measure realized win rate, **tail distribution of winners** (is there a runner?), stop-out frequency, and dead-on-arrival rate (signals on tokens that then rug). The strategy lives or dies on the tail, which only forward data shows.
4. Promote to live (tiny size) only if the forward sample shows the asymmetric tail is real.

This matches the project rule (short-medium-term, regime-conditioned, forward-validated — not multi-year robustness).

---

## 5. Risk (quantified where the API exposed it)

Live orderbook pulls (2026-06-01), small-cap vs BTC:

| Symbol | Spread | Top-bid depth | Top-ask depth |
|---|---|---|---|
| RSR ($17k vol) | **42.5 bps** | $3,490 | **$571** |
| XAI ($25k vol) | **19.8 bps** | $1,038 | $1,162 |
| BTC | 0.1 bps | — | $2.6M |

- **Spread cost alone is 20–43 bps round-trip on the smallest names** vs 0.1 bps on BTC — that's **2–4% of an 8% target gone to spread.** The screen's "spread ≤ 25 bps" gate is mandatory, and RSR-class names should be rejected outright.
- **Depth is the real constraint:** top-of-book $500–$3.5k. A 0.5%-of-$1k shot ($5) fills fine; but this confirms moonshot sizing MUST stay tiny — anything >~$1k/order eats multiple levels and self-inflicts slippage. The asymmetric small-bet design is not optional, it's forced by the book.
- **Slippage model is wrong for small-caps today:** `SLIPPAGE_BPS` has no small-cap entries → defaults to **10 bps**, but measured spreads are 20–43 bps. Forward paper-trade must override per-symbol slippage to **≥ half-spread + impact** (start 25–40 bps) or it'll overstate edge. `STOP_SLIPPAGE_BPS=15` is also too tight for forced exits into thin books — assume 30–50 bps on stop fills.
- **Funding spikes:** small-cap perp funding swings far harder than majors; the flat `FUNDING_RATE_HOURLY=0.00005` sim understates it. 90-min max hold limits exposure (≤2 funding periods).
- **Liquidation cascades / wicks:** thin books wick through stops. 3x maxLev on these names means cascades are sharp. −4% stop + adverse-fill assumption is the mitigation; accept that some stops fill materially worse than −4%.
- **Rug / delist risk:** 51/230 already delisted. A held position can be delisted/halted. The 90-min max hold + tiny size bound this.

---

## BUILD / DON'T-BUILD recommendation

**BUILD — as a forward-watch paper prototype on a new `paper_perp_v{N}` wallet. DON'T put live money on it until the forward sample proves the tail.**

Reasoning:
- The expensive prerequisite (a venue that lists these tokens + symbol-agnostic execution) **already exists** — Hyperliquid + `hyperliquid_trading.py`. That's the part that's usually the blocker, and it's done.
- The chart trigger (`momentum_buckets` breakout) and the brain (`Snoop`) exist and are reusable as-is.
- The only genuinely missing piece is **per-token buzz scoring for non-majors** (extend the CoinGecko ID map / dynamic ID resolution) + an adaptive whale threshold — both small, contained additions.
- It plugs into the multi-wallet A/B framework with zero global trading-logic change (whitelists already exist, verified at `auto_trader.py:1094/1314/1359`).
- The honest risk: edge is unproven and unbacktestable. So the cost of being wrong is bounded by paper-only + (later) 0.5%/shot sizing. Low downside, optionable upside — exactly the asymmetry the idea wants, applied to the *decision* itself.

**Smallest viable first step (one focused build, paper-only):**
1. Extend `social_sentiment.py` to resolve CoinGecko IDs dynamically (or add the small-cap IDs) so it can return a per-token `buzz_score` for arbitrary HL perps.
2. Write a standalone **screener script** that pulls all 179 HL perps, applies the §3 hard gates (lev/OI/vol/spread) + buzz threshold, runs `momentum_buckets` on each survivor's 5m candles, and **logs candidate "shots" to a new `wp_moonshot_signals` table** — *no trading, no wallet, no strategy class yet.*
3. Run it on a cron for ~2 weeks and review the signal log: how many shots/day, on what tokens, do the charts actually break out, what's the spread at signal time.

That step is pure observation — it answers "is there even a stream of decent candidates?" before any strategy/wallet/sizing work, and touches zero trading logic. If the signal log looks real, *then* build `MoonshotScalperStrategy` + the `paper_perp_v{N}` wallet and paper-trade it.

---

## Report-back answers
1. **Execute low-mcap moonshots today?** YES, on **Hyperliquid** — 179 active perps, **117 under $1M/24h vol, 153 under $5M**, 89 at 3x-lev (HL's small-cap tier). Execution symbol-agnostic. dYdX = majors-only (skip). Uniswap = LP-only, no taker swaps (only matters for true off-HL microcaps).
2. **Snoop buzz coverage?** **Majors only today** — per-token social score gated by 19 hardcoded CoinGecko IDs; trending list is generic. Gap = extend ID resolution for arbitrary small-caps.
3. **Backtest or forward-watch?** **Forward-watch only.** Survivorship bias (51/230 already delisted) + zero historical buzz data make backtest dishonest. 1m/5m candles exist for mechanical sanity-check only.
4. **Build/don't-build?** **BUILD as paper forward-watch prototype, not live yet.** Smallest first step: extend buzz scoring + a screener script logging candidates to `wp_moonshot_signals`, no trading, ~2 weeks, then decide.
5. **Doc:** `/home/danman60/projects/WolfPack/docs/research/2026-06-moonshot-scalper-scope.md`
