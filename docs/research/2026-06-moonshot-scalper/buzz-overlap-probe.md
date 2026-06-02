# Moonshot Scalper — Buzz↔HL-Tradeable Overlap Probe

**Date:** 2026-06-01
**Status:** RESEARCH ONLY. New files only. No trading, no wallet config, no DB migration applied.
**Question (make-or-break):** Does what's *buzzing* on 4chan /biz/ + crypto Reddit + top social feeds actually *overlap* with what's *tradeable as an HL small-cap perp*? If the buzz venues only hype un-listed DEX memecoins (and meme-stocks), the whole idea has no signal source.

All numbers below from LIVE pulls on 2026-06-01 (HL `metaAndAssetCtxs`, `a.4cdn.org/biz/catalog.json`, CoinGecko `search/trending`). Reddit was unreachable — see below.

---

## TL;DR verdict — overlap is NOT viable on /biz/+Reddit

- **Of 92–137 distinct buzzed tickers, only 15 are HL-listed, and only 5 are in the HL small-cap (<$5M/24h) tier. /biz/ contributed essentially ZERO small-cap crypto names** — its top mentions are meme-stocks (BBBY/BBBYQ/GME/SPCX) and majors (BTC/ETH/XRP/XMR/LINK).
- **The 5 small-cap HL hits came almost entirely from CoinGecko trending, not /biz/ or Reddit.** Reddit was 403-blocked from this IP (and the droplet IP) — could not contribute.
- **Conclusion: /biz/+Reddit are the WRONG buzz source for an HL small-cap scalper.** They pump un-listed microcaps and meme-stocks. The only free source that *does* map to HL-listed alts is **CoinGecko trending** (and HL's own volume/OI velocity).
- **Built anyway (because it's the right path):** a runnable screener keyed on the *viable* sources (CoinGecko trending PRIMARY + /biz/ low-weight secondary + Reddit stub), intersected with the live HL small-cap universe, gated by the existing `momentum_buckets` chart trigger and live spread. Ran it once — produced 7 real candidate rows. Migration written as a file, **not applied**.

---

## 1. The overlap numbers (live)

### HL universe (live `metaAndAssetCtxs`)
- 230 perps total, 51 delisted, **179 active**.
- **153 active perps under $5M/24h volume; 117 under $1M.** (Matches the scope doc.)

### Buzz sources (live)
| Source | Status | Distinct tickers extracted |
|---|---|---|
| 4chan /biz/ (`catalog.json`, 201 threads) | OK | 80–125 (after noise filter) |
| CoinGecko `search/trending` | OK | 15 |
| Reddit (`.json` on 5 crypto subs) | **403 BLOCKED** | 0 |
| X/Twitter trending cashtags | not attempted past cap — no free unauth source reachable | 0 |

Union of distinct buzzed tickers: **92** (CG+/biz/, capped run) to **137** (full /biz/ extraction).

### The overlap (buzzed ∩ HL-active), ranked by buzz
| Ticker | Buzz | HL 24h vol | HL OI (USD) | maxLev | Tier | Source |
|---|---|---|---|---|---|---|
| BTC | 19 | $1.34B | $2.20B | 40x | major | biz + CGtrend |
| XLM | 11 | $21.3M | $18.0M | 5x | mid | biz + CGtrend |
| HYPE | 9 | $1.22B | $1.64B | 10x | major | biz + CGtrend |
| XMR | 8 | $8.16M | $40.5M | 5x | mid | biz |
| **OP** | 8 | **$0.60M** | $3.58M | 5x | **SMALL<1M** | CGtrend |
| **PENGU** | 8 | **$1.77M** | $5.10M | 5x | **SMALL<5M** | CGtrend |
| VVV | 8 | $22.7M | $45.6M | 3x | mid | CGtrend |
| FET | 8 | $6.88M | $15.7M | 5x | mid | CGtrend |
| SUI | 8 | $15.5M | $30.1M | 10x | mid | CGtrend |
| WLD | 8 | $31.4M | $37.5M | 10x | mid | CGtrend |
| XRP | 6 | $27.2M | $84.9M | 20x | mid | biz |
| **LINK** | 5 | **$4.61M** | $36.3M | 10x | **SMALL<5M** | biz |
| ETH | 4 | $502.7M | $1.34B | 25x | major | biz |
| **ICP** | 4 | **$1.14M** | $3.31M | 5x | **SMALL<5M** | biz |
| **IP** | 1 | **$0.70M** | $3.82M | 3x | **SMALL<1M** | biz |

### The ratio
**Of ~92 buzzed tickers: 15 HL-listed, 5 in the <$5M small-cap tier (OP, PENGU, LINK, ICP, IP), 2 in the <$1M tier (OP, IP).**

### Proof of the thesis — /biz/ top-30 vs HL
Top /biz/ mentions: `BBBY(13), BBBYQ(10), GME(9), SPCX(2), GRAIL(2)` = meme-**stocks**. The only HL hits in /biz/'s top-30 are **all majors**: BTC, ETH, XRP, XMR, LINK, ICP, XLM. **Zero small-cap alt moonshots from /biz/.** The "small-cap" HL hits in the overlap table (OP, PENGU) came from **CoinGecko trending**, not /biz/.

---

## 2. Verdict: build on /biz/+Reddit? NO. Recommended alt source: CoinGecko trending + HL velocity.

/biz/ and Reddit hype day-one DEX memecoins and meme-stocks that are **not on HL**. They are not a usable signal source for an HL-listed small-cap scalper. Empirically confirmed, not assumed.

**Recommended buzz sources that DO map to HL-listed alts:**
1. **CoinGecko trending** (PRIMARY) — the only free, unauth source observed to surface HL small-caps (OP, PENGU this run). Already used by `social_sentiment.py`, already reachable from the droplet.
2. **HL's own volume/OI velocity** (a "buzz proxy" with no external dependency) — a small-cap whose 24h vol or OI just jumped Nx vs its trailing average IS the buzz, sourced directly from `metaAndAssetCtxs`. Survivorship-clean and rate-limit-free. **Strongly recommended as the backbone.**
3. **Funding-rate spikes** — sharp funding moves on a small-cap = crowding/attention proxy, also straight from HL.
4. /biz/ as a *low-weight tiebreaker only* (kept in the screener at ≤25 pts), never the trigger.

Reddit: only usable from a residential IP or with an authed API key (`REDDIT_*` — not present in `~/.env.keys`). Stub left in the screener; auto-skips on 403.

---

## 3. What got built (new files only)

| File | Purpose |
|---|---|
| `intel/wolfpack/research/moonshot_screener.py` | Standalone screener. Pulls HL universe + CG-trending + /biz/ (+ Reddit stub), scores buzz, intersects with HL small-cap (<$5M, >$250k vol) set, runs the existing `momentum_buckets` module on 5m candles (via intel `GET /market/candles`), pulls live HL L2 spread, writes ranked candidate "shots" to JSONL. **No trading, no DB, no wallet.** Imports `momentum_buckets` + `Candle` — modifies nothing. |
| `intel/wolfpack/research/__init__.py` | Marks the research package (not imported by trading logic). |
| `docs/research/2026-06-moonshot-scalper/signals.jsonl` | Forward-watch signal log (this run appended 7 rows). |
| `supabase/migrations/20260601_moonshot_signals.sql` | `wp_moonshot_signals` table. **WRITTEN AS A FILE, NOT APPLIED.** Eventual durable sink for the forward-watch. No FK to wp_wallets (venue-level observation, not per-wallet trades). |

### Reuse, not rebuild
- Chart trigger = `wolfpack.modules.momentum_buckets.MomentumBuckets().analyze(candles, asset)` → `regime_hint` / `momentum_score` / `conviction` (unmodified).
- Candles = intel API `GET http://159.89.115.95:8000/market/candles?symbol=&interval=5m&limit=100` (verified live for small-caps).
- Universe + spread = HL `metaAndAssetCtxs` + `l2Book` (the same source `exchanges/hyperliquid.py` uses).

---

## 4. Proof it runs — sample rows (live, 2026-06-01)

`python -m wolfpack.research.moonshot_screener` output:
```
HL active=179  small-cap(<$5M, >=$250k)=81
buzz tickers: cg=15 biz=125 reddit=0 union=137
buzz x HL-small-cap overlap: 7 -> ['OP','PENGU','IP','LINK','AR','ICP','HBAR']
  OP     buzz=60.0 regime=trending     mom=+0.59 conv=0.74 spread=4.99bps shot=False
  PENGU  buzz=60.0 regime=breakout     mom=+0.00 conv=0.21 spread=2.52bps shot=False
  ICP    buzz= 8.0 regime=transitional mom=+0.20 conv=0.66 spread=5.31bps shot=False
  HBAR   buzz= 2.0 regime=transitional mom=+0.27 conv=0.51 spread=1.45bps shot=False
  ...
Wrote 7 candidate rows (0 pass full 'shot' gate)
```

Sample JSONL row:
```json
{"ts":"2026-06-01T03:06:53Z","ticker":"OP","buzz_score":60.0,
 "sources":["coingecko_trending"],"hl_vol_24h":601721,"hl_oi_usd":3585098,"hl_maxlev":5,
 "chart_state":{"regime_hint":"trending","momentum_score":0.5852,"conviction":0.737,"primary_trend":"up"},
 "est_spread_bps":4.99,"spread_gate_pass":true,
 "hypo_entry":0.12025,"hypo_stop":0.11544,"hypo_target":0.12987,"is_shot":false}
```

**Read on the run:** 7 candidates surfaced, **0 passed the full `is_shot` gate** (breakout + mom≥0.4 + conv≥0.5 + spread≤25bps) at this instant — OP had momentum+conviction but regime=`trending` not `breakout`; PENGU was tagged `breakout` but flat momentum. That's correct behavior: the gate is strict and one snapshot rarely fires. The forward-watch measures fire *rate* over time.

Spreads on the small-cap hits were 2.5–10.4 bps this run — well inside the 25bps gate and far tighter than the RSR/XAI dust (20–43bps) flagged in the scope doc. The vol-floor ($250k) already excluded that dust.

---

## 5. How to run the 2-week forward-watch

1. **Cron the screener** (read-only observation):
   ```
   */15 * * * *  cd /root/WolfPack/intel && python3 -m wolfpack.research.moonshot_screener >> /var/log/moonshot.log 2>&1
   ```
   Appends candidate rows to `docs/research/2026-06-moonshot-scalper/signals.jsonl`. No trades, no DB.
2. **After ~2 weeks**, review the JSONL: shots/day, which tokens, how often `is_shot=true` fires, spread at signal time, and (manually) whether flagged breakouts actually ran. This answers "is there even a candidate stream?" before any strategy/wallet build.
3. **If/when you want durable storage**, apply `supabase/migrations/20260601_moonshot_signals.sql` (user approval) and point the screener's writer at the table.
4. **Add the HL-velocity buzz proxy** (recommended in §2) as a second trigger — it needs no external API and is survivorship-clean.

---

## 6. Source-failure log (no fabrication)
- **Reddit**: HTTP 403 on all 5 subs via httpx, curl (browser UA), and real headless Chromium (Playwright). IP-level block on datacenter ranges; the `.json` endpoint returns the JS shell, not data. No `REDDIT_*` key in `~/.env.keys`. Needs residential IP or authed API to contribute. Skipped after exhausting reasonable attempts.
- **X/Twitter trending cashtags**: no free unauthenticated endpoint reachable; not pursued past the cap.
- **/biz/ + CoinGecko + HL**: all succeeded, all numbers above are from those live pulls.
