# Crypto rotation repository evidence

Read-only investigation, 2026-10-12 Eastern. Owner handoff read in full. Scope: new CAD/BTC/ETH/LINK spot rotation research/design; no trading, account, wallet-key, server-start, build, deployment, code, DB or existing-work mutations.

## Primary state / startup

- WolfPack HEAD `60cccd7` (`chore: pre-reboot local checkpoint`), WolfHunt HEAD `f1f381e` (same subject). Both `git status --short` returned clean at investigation start.
- Existing graph reports were read before graph queries/explain. WolfPack graph built from `9e8e3ebe`; WolfHunt from `fac5224c`. Graphs are navigation hypotheses; all substantive findings below checked against current filesystem source. No graph rebuild.
- WolfPack CURRENT_WORK describes historical leveraged funding carry, not this new project. Its forward estimates and vault Memory claim are not validation evidence for spot rotation. Memory read; historical carry claims preserved.
- WolfPack INBOX read across bounded ranges: numerous transcription receipts, April MiroFish research, June tool ideas, Sept 1 security report. No unrelated task executed or cleared. Sept report claims 29 wp_* tables had RLS disabled then, including exchange config; current queried database did not expose those table names. This is an unresolved environment/security history, not proof of current exposure.

## Live wallet query: unresolved current system of record

Do not report fallback registry rows as live wallets.

1. Direct REST read using repo `intel/.env`: configured host `vztdmqqkxwqgkxvqgqpl.supabase.co`; Python urllib returned `URLError <urlopen error [Errno -2] Name or service not known>`.
2. Current central env / CCandSS MCP host is `netbsyvxrhrqxyzqflmd.supabase.co`. REST `GET /rest/v1/wp_wallets?select=name,wallet_mode,wallet_type,status,starting_equity,current_equity,config,display_name,generation,parent_wallet_id&order=name`: HTTP 404 with both service-role and anon credentials. Credentials never printed.
3. CCandSS MCP `SELECT name,... FROM public.wp_wallets ORDER BY name`: PostgreSQL `42P01 relation public.wp_wallets does not exist`. Independent catalog SELECT across all schemas for `table_name like 'wp_%' or table_name ilike '%wallet%'`: 0 rows.
4. COMPSYNC MCP same catalog SELECT: 0 rows.
5. `curl --max-time 5 http://localhost:8000/wallets/summary`: timeout, HTTP 000.

These establish query/environment mismatch, not that the owner's wallets are gone. Possible method faults investigated: stale repo URL, wrong current central project, public-schema-only lookup. Two different approaches (REST and SQL catalog) agree about the current central project's visible tables; historic wallet state remains unverified. No server imported or started. Current actual wallet list/configs cannot be supplied from these probes. Owner handoff lists paper_perp generations/prod_perp as historical context only.

`intel/wolfpack/wallet_registry.py:31` defines four hardcoded fallback wallets; `:140` uses them when DB rows fail/empty. `:76` WalletConfig supports perp/lp, config, generation and lineage. These are reusable isolation concepts, not spot accounts or confirmed current balances.

## Verified reuse inventory / limitations

| Surface | Current code evidence | Reuse decision |
|---|---|---|
| EVM wallet connection | WolfPack `app/src/lib/wagmi.tsx:11`: mainnet + Arbitrum; injected connector, WalletConnect, Coinbase Wallet; WalletConnect env fallback is literal `demo` at :16. `app/src/app/pools/page.tsx` imports account/connect/disconnect and LP hooks. | Reuse connector/provider setup if self-custody selected. It is EVM connection plumbing, not CAD fiat rails or native-BTC custody/execution. |
| Experiment selection | `app/src/lib/wallet/context.tsx:5`: separate perpWallet/lpWallet strings; defaults paper_perp/paper_lp. | Existing WalletSelector is selecting experiment wallets; do not confuse it with the connected browser wallet. Extend through a separate spot-account contract, preserving current experiment state. |
| Market adapter contract | `intel/wolfpack/exchanges/base.py:48`: candles, markets, funding, orderbook; MarketInfo at :38 includes OI/funding/leverage. | Basic candle/orderbook shapes reusable. Venue, actual base/quote currency, spot instrument rules, fees, CAD conversion/provenance need explicit new contracts. |
| Existing Kraken implementation | `intel/wolfpack/exchanges/kraken.py:35` maps BTC/ETH/LINK to USD spot candles; :135 loads **futures** tickers; :143 restricts PF_ instruments; `app/src/lib/exchange/kraken.ts:156` submits to `/intel/kraken/paper/buy|sell` and :175 marks results filled. | Already an implementation worth adapting, but not a production CAD spot adapter. Do not inherit its futures universe, paper fills, USD quote or max leverage. |
| Candle persistence | `intel/wolfpack/candle_cache.py:26` cache/gap-fetch/dedupe; :11 factories only Hyperliquid/dYdX; :88 catches fetch errors; :121 returns merged partial series. | Adapt cache/gap logic with explicit completeness/provenance. New evaluation must stop on insufficient real data, not accept partial results silently. |
| WolfPack replay | `intel/wolfpack/backtest_engine.py:28`, `models/backtest_models.py:6`: single symbol, long/short positions, USD equity; strategy receives full candle list plus index at engine :65; entry at current close :144. | Replay orchestration and progress/result shape useful. Not four-asset portfolio/flow/hold accounting. Truncate data before strategy, apply decision latency and later executable fills. |
| WolfPack costs/metrics | engine :142 folds entry commission/slippage into entry price; :183 records close from candle.close and price-difference P/L; :321 hardcodes hourly annualization sqrt(8760), despite configurable interval. | Require new shared fill/fee accounting and frequency-correct metrics. Closing-cost accounting and stop-fill vs reporting consistency need validation before any reuse. Do not cite current output as spot strategy evidence. |
| Existing walk-forward research | `docs/research/2026-06-turtle-walkforward/run_walkforward.py:16` anchored train/test, expanding folds, neighborhood perturbations, cost stress; :84 wrapper uses through-current-bar window. | Useful design precedent; its parameters/5001-bar data cap/costs/strategies are historical research specifics. New horizon-based purge, final holdout, frozen trial registry, authentic spot/CAD data still required. |
| WolfPack performance | `intel/wolfpack/performance_tracker.py:101` reads recent closed trades and grades symbol/direction/regime; :112 query has no wallet filter. | This is adaptive trading-score logic, not CAD account performance or fair flow-adjusted hold comparison. Avoid modifying or reusing globally across existing wallets. |
| Existing owner approval | `intel/wolfpack/api.py:658` authenticated approve route; :666 marks approved before circuit/liquidity gates; :696 executes via paper_perp engine. | UI approval interaction is precedent only. New spot execution needs quote-bound approval, idempotency, expiry, leg limits, partial-fill reconciliation, trade-only key, no withdrawal permission. Do not wire new rotation approval to old route. |
| WolfHunt multi-asset simulator | `backend/src/trading/backtesting/engine.py:352` merges symbol timestamps; :391 slices data <= current time; :403 records snapshot before trading; :415 immediately executes signal's price. | More suitable portfolio event-loop precedent, but same-close signal/fill timing must change; final after-fill valuation and stale-mark policy needed. |
| WolfHunt mock wallet | `backend/src/trading/backtesting/mock_wallet.py:74` Decimal cash/positions; :92 adverse slippage, commission, inventory checks; :163 weighted entry and realized P/L. | Potential starting point for spot ledger. Single unnamed cash currency, fixed fee model and P/L-before-fees semantics require explicit CAD accounting; timestamps inside position updates use wall-clock :168/:177 rather than event time. |
| WolfHunt history loader | `historical_data.py:190` unconditionally falls back to synthetic data after fetch failure; :207 caps requested duration to 365; :212 calls relative-days market_chart with USD and no requested end timestamp; :259 manufactures highs/lows from close multipliers. | Must not use as authoritative backtest input. Keep concepts of rate-limiting/cache only; replace data sourcing and make source/coverage failures explicit. |
| WolfHunt benchmark | `performance.py:404` accepts one benchmark-return scalar and subtracts it; engine :205 contains a test buy-and-hold strategy whose single position_taken boolean is shared across symbols. | Neither is the required cloned starting portfolio + identical external flow benchmark. Build explicit paired ledger/valuation and recommendation-level counterfactuals; don't label scalar excess return risk-adjusted alpha. |

## "Better mask" identity

Verified named implementation: injected wagmi + WalletConnect + Coinbase Wallet. Literal `rg` over both frontend src trees/package manifests plus independent Python recursive source read found 0 occurrences of `rabby`, `rainbow`, `metamask`, `reown`, `privy`, `better mask`. Broader bounded repo search found only the wagmi names and historical WalletConnect demo-project errors. This does not identify the owner's remembered provider, nor does it rule out use through a generic injected connector. Ask owner for remembered name/screenshot only if provider identity affects their choice; don't invent Rabby as fact.

## Concrete design consequences

- Separate new spot rotation domain and data/trial tables from existing perp/LP policies and auto-trader. No existing wallet scope change authorized.
- Reuse adapters/component patterns and historical research structures selectively; do not inherit historical estimated returns, futures cash conventions or synthetic-data fallbacks.
- Maintain actual, initial-hold and recommendation-level hold counterfactual ledgers with explicit CAD valuations, identical external-flow policy and transparent costs. Existing repos provide pieces, not proven complete accounting.
- Enforce point-in-time feature availability; fitting/selection inside chronological folds; purge outcome overlap across 7/30-day horizons; execute only after decision time; test quote freshness, partial fills, duplicate approvals and reconciliation against real read-only account data before funding.
- Current DB environment mapping and historical RLS report need resolution before any connection containing account credentials. Investigation/design can proceed without reviving old infrastructure.
