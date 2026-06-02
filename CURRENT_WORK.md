# Current Work — WolfPack

## Session 2026-06-01: Edge-hunt — 4 spikes, 1 survivor (Turtle BTC/ETH)

**Summary:** Peer's SPX GEX bot sparked an edge hunt. 4 free in-harness research spikes. 3 died, 1 survived. All research-only — NO trading logic, wallet config, or live code modified.

**Scoreboard:**
| Idea | Result |
|---|---|
| GEX regime (vol proxy) | **DEAD** — inverts hypothesis, returns near-random by regime |
| Moonshot scalper | **DEAD** — −0.55%/trade @30bps on 20 HL small-caps; 22% delisted = survivorship swamps |
| Caller attribution | **DEAD** — no source both attributable AND HL-tradeable (/biz anon, Reddit blocked) |
| **Turtle trend BTC/ETH** | **LIVE** — ETH +12.9% (PF2.03, MC90.5%), BTC +3.5% (PF1.61, MC74.9%), 27mo 4h, period 30–40 |

**New research files (all NEW, nothing live touched):**
- `docs/research/2026-06-gex-proxy/` — GEX proxy FAIL
- `docs/research/2026-06-transcript-edge-mining.md` — 54 transcripts mined; top-3 edges already in repo (orb_session/measured_move/turtle_donchian)
- `docs/research/2026-06-turtle-regime/` — Turtle sweep; BTC+ETH PASS, LINK FAIL; "55>20" only weakly holds (sweet spot p30–40)
- `docs/research/2026-06-moonshot-scalper-scope.md` + `docs/research/2026-06-moonshot-scalper/` — scope + buzz-overlap probe + mechanical-leg backtest (all FAIL)
- `intel/wolfpack/research/moonshot_screener.py` (+ `__init__.py`) — prototype, **has dead-gate bug**
- `supabase/migrations/20260601_moonshot_signals.sql` — **written, NOT applied. Do not auto-apply.**
- `docs/transcripts/20260601_*day-trading-for-5-year-olds*` — another 15min ORB + affiliate shill, no new edge

**Known bug:** `moonshot_screener.py` `is_shot` gate (`regime==breakout AND momentum≥0.4 AND conviction≥0.5`) fires 0× by construction — momentum_buckets caps momentum_score at ~0.40 on breakout bars, AND never passes. Fix or delete (moonshot dead).

**Next steps (priority):**
1. **Turtle walk-forward validation** — split 27mo BTC/ETH IS/OOS (60/40), confirm p30–40 holds OOS. MC 5th-pct negative on all best cells → single-window risk. Only real edge; prove before capital. If holds → paper-wallet candidate (confirm WHICH wallet first per multi-wallet protocol; per-wallet whitelists exist in auto_trader.py).
2. **Moonshot disposition** — fix screener dead-gate OR delete `intel/wolfpack/research/` + unapplied migration. Lean delete.
3. (Optional) ORB+FVG at funding-reset/CME-open — transcript candidate #2, not yet backtested.

**Gotchas:**
- Backtest lookback ceiling: intel API caps ~5001 candles → 4h=27mo, 15m=52d, 1m=17d. Use 4h/1d for trend, 15m for scalp.
- Realistic small-cap perp cost = 30–40bps, NOT harness default 10bps.
- `intel/wolfpack/strategies/__init__.py` (M in git) modified BEFORE this session — not mine.

---

## Active Investigation: Kronos forecasting-model install (2026-05-14 EDT)

**Status:** Installed end-to-end on SPYBALLOON. Sanity check passed. **Design doc written. No WolfPack code changed.** Awaiting user sign-off on host / cadence / wallet / scope (Open questions in the design doc).

**What was installed:**
- `~/projects/Kronos/` (cloned upstream `shiyu-coder/Kronos`, MIT license)
- `~/projects/Kronos/venv/` — torch 2.12.0+cu130, CUDA 13, RTX 3060 verified working
- HF cache at `/mnt/firmament/hf-cache/` (534 MB total): Kronos-Tokenizer-base, Kronos-Tokenizer-2k, Kronos-mini (16 MB), Kronos-small (95 MB), Kronos-base (391 MB). Kronos-large is closed-source — skipped.
- Sanity check: `~/projects/Kronos/samples/sanity_check_btc.py` — BTC/USDT 1h, lookback 480, horizon 24. **Load 2.1s, predict 0.45s, peak VRAM 136 MB.** Single-window holdout metrics: Close MAPE 0.94%, direction agreement 22/24, 24h cumulative sign match. Not edge-proof; n=1.

**Design doc:** `docs/plans/2026-05-14-kronos-integration.md` — Sage augmentation as Path A, Brief veto deferred, multi-wallet `paper_perp_v4` ("Kronos-augmented Sage") as the A/B test vehicle. **No DROPLET deploy or production restart performed.**

**Open questions for the user** (do NOT guess on these — see design doc Open Questions section):
1. Host: SPYBALLOON (recommended) vs FIRMAMENT?
2. Call cadence: every cycle, on Sage request, or only on candidate-trade?
3. Model: Kronos-small for everything, or Kronos-base for headline assets?
4. Symbol scope: current BTC/ETH/LINK watchlist or broader?
5. Wallet vehicle: new `paper_perp_v4` vs shadow-mode on existing wallets?

**Prior on edge:** low-to-moderate. WolfPack's only validated edge so far (Phase 6/8 funding-z-low long) is funding-rate-based, not OHLCV — and Kronos cannot see funding. Treat as a longshot worth A/B-testing because install is cheap.

---

## Prior Investigation: Edge Provenance Multi-Phase Backtest (2026-05-06 → 2026-05-07)

**Reason for fresh restart:** Long session (covered 13 backtest phases). Phase 12/13 portfolio simulator returned 0.00% Leg 1 returns across all windows despite 5-29 trade fires per window — this contradicts Phase 6/8 which reported Sharpe 4.56 on BTC and +0.83% per BEAR-regime trade. Phase 12/13 leg1_equity_curve has a bug. Ready to debug + re-run with fresh context.

## What was investigated this session

User opened with "pretty poor progress this last month." Investigation walked through 13 numbered phases of backtest research located in `docs/research/2026-05-backtest-sweep/`:

- **Phase 1**: 11 strategies × 7 symbols × 90d at 1h. Result: 1 marginal cell.
- **Phase 2**: regime decomposition on mean_reversion. DOGE only OOS-stable.
- **Phase 3**: 12 strategies × 7 symbols × 28mo at 4h. 2 of 168 cells passed acceptance. Bull-market noise.
- **Phase 4**: edge provenance validator (4 gates) on 5 OHLCV hypotheses. H1 capitulation flush survived on AVAX/DOGE/LINK.
- **Phase 5**: capitulation_flush as full strategy (added `intel/wolfpack/strategies/capitulation_flush.py`). Lost money on every symbol — signal-vs-strategy gap.
- **Phase 6**: funding-rate hypotheses on Hyperliquid funding history. **F2 funding-z-low → long survived all 4 gates on BTC and DOGE.** First defensible "yes" in the entire investigation.
- **Phase 7**: funding-squeeze-long as strategy with stops/TPs. Best params produced ~3%/yr DOGE, ~2%/yr BTC. Loses to HODL on every symbol.
- **Phase 8**: regime-segmented Phase 7. Strategy DID beat HODL in SIDEWAYS and BEAR sub-regimes (BTC SIDEWAYS edge +0.41%/trade, BEAR edge +0.67%/trade). Bull market was swamping the result.
- **Phase 9**: Leg 2 (BULL signals) and Leg 3 (BEAR signals) hypothesis tests. Leg 2 hypotheses all failed walk-forward. Leg 3 D3 (TSMOM short) survived on ETH and ARB but with caveats.
- **Phase 10**: 3-leg portfolio (sideways harvester + BULL ladder + BEAR mirror) on last 90 days. **0/7 symbols beat HODL.** Leg 2 lost on 6/7 even in bull tape.
- **Phase 11**: Phase 10 + 3 fixes (hysteresis, hold-while-regime, leading classifier). Made things worse — avg portfolio −4.43% vs Phase 10 −0.33%.
- **Phase 12**: HODL + Drawdown Harvester (80/20, 90/10, 70/30 blends). Last 90 days = bull, Leg 1 didn't fire. Returned 0.00% on every blend variant. **First sign of simulator bug.**
- **Phase 13**: Phase 12 architecture re-tested on historical worst-drawdown and most-sideways 90d windows per symbol. **Leg 1 fired 5-29 times per window but reported 0.00% return on every single window.** Confirmed bug.

## Critical bug to debug

**File:** `docs/research/2026-05-backtest-sweep/run_phase13_historical_windows.py` (and Phase 12 has same bug)
**Function:** `leg1_equity_curve` (lines ~125-160)

Leg 1 fires 17-29 trades in BTC's worst-drawdown 90d window (Nov 2025 → Feb 2026 where HODL was −38.7%), yet the simulator returns total return = 0.00% and max DD = 0.00%. This contradicts Phase 6 which used the same data + signal and produced Sharpe 4.56 on BTC.

Likely culprits:
1. Equity curve forward-fill clobbering trade-exit values
2. trade_pct=0.10 sizing collapsing to zero somehow
3. The `eq[i] = eq[i-1]` line at top of outer loop overwriting the inner-loop trade-exit writes
4. Maybe new_eq = eq_at_entry * ... where eq_at_entry got corrupted

Need to add print statements at entry/exit to verify equity values are non-1.0 during/after trades.

## Trade history of conclusions
1. ❌ The original 11-strategy framework has no edge in OHLCV
2. ❌ RSI(2) Connors textbook strategy fails on crypto perps
3. ✅ Capitulation flush HAS statistical signal but fails as a strategy due to SL/TP geometry
4. ✅ Funding-z low → long has REAL edge (Phase 6/8) but is rare-firing and modest magnitude
5. ❌ 3-leg regime-routed portfolio with bull-rider doesn't beat HODL — bull leg is structurally hard
6. ⚠️ HODL + Drawdown Harvester blend hypothesis is UNVALIDATED due to simulator bug

## Next steps for fresh session

1. **Debug Phase 13 leg1_equity_curve.** Add inline logging or write tiny unit test confirming trade P&L hits the equity array. Compare against Phase 6 methodology that produced Sharpe 4.56.
2. **Re-run Phase 13** with fixed simulator on the worst-drawdown windows (BTC Nov 2025–Feb 2026, ETH Jan-Apr 2025, etc.).
3. **Decide architecturally**: if fixed Leg 1 generates real alpha during HODL drawdowns, the 80/20 blend is real. If it doesn't, the architecture is dead.
4. **Do NOT cut over to live capital.** All paper wallets v1/v2/v3 should remain paused per prior session decisions.

## Wallet state (per multi-wallet evolution protocol)

All 3 paper wallets (paper_perp, paper_perp_v2, paper_perp_v3) have `regime_router_enabled=false` and have been losing money for ~12 days. v1 −$727, v2 −$392, v3 −$175 as of 2026-05-06 morning. **Recommendation pending: pause all 3 until methodology produces validated strategy.**

## Files added this session

- `intel/wolfpack/strategies/capitulation_flush.py` — registered, not deployed live
- `intel/wolfpack/strategies/rsi2_connors.py` — registered, validated as losing
- `docs/research/2026-05-backtest-sweep/` — 13 backtest scripts + JSON results + markdown summaries

## Commits made this session

None. All Phase 1-13 work is research only — strategy files were registered but no live config changes shipped. Trading bot is unchanged from 2026-04-24 commit `6169f35`.
