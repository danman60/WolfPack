# Approved portfolio allocation rebuild — 2026-10-13

This exists so that "I want simple ongoing analysis of all the interconnected pairs with technical analysis and Sentiment analysis to make a simple recommendation on an overall reallocation of the portfolio to maximize profit".

Owner said "Build it!" after approving the native allocation mockup and adding immutable profit projections, check-in grading, and Apply executing the complete rebalance. Approved visual reference: docs/mockups/2026-10-13-portfolio-allocation/index.html. Example values there are illustrative and must never become real app defaults or signals.

Scope: existing authenticated CAD/BTC/ETH/LINK rotation workspace. No old perp wallet trading logic changes. Existing dirty files and running processes preserved. Rough effort 1–2 hours including integration and verification. Cheapest probes completed: live HEAD/status, existing ledger/API/market surfaces, actual RSS responses and credential names. Account provider is pending owner choice; funded trades must never be executed by development/testing.

## 1. Shared contracts and durable backend — strategy_runner

Extend existing exact eight-decimal accounting, auth, owner RLS, CAS, history and market books. Own allocation-contract.ts, allocation-engine.ts, allocation-server.ts, execution-adapter.ts, isolated allocation/projection/batch API routes and scoped migration. Generalize four arbitrary weights and share instant estimates with the browser. Snapshot starting holdings, prices, forecasts, model/version, analysis reference, targets, expected all-in costs, due date, expected total and incremental profit against unchanged starting holdings. Preserve legacy immutable forecasts.

Use wpr_trials immutable projection/outcome namespaces and one durable wpr_batches table only where existing transactional storage cannot represent batch state. Query live catalog first. Persist order intent and unique client order id before submission. Confirm sells before sizing buys from actual funds. Lowest estimated all-in supported route cost; analytical ratios do not imply executable markets. CAS and atomic per-leg ledger commit, unknown-order reconciliation before retry, pause partial/failure, retain actual fills. Paper and connected real accounts clearly separate.

Acceptance: arbitrary targets sum100; exact self-financing costs/minimums; same client/server estimate; frozen records survive refresh; matched baseline and cashflows; one Apply authorization; double-click/reload cannot duplicate; partial/uncertain fills pause and preserve funds. Native connector follows selected provider and server-only credentials. Development must not place funded orders.

## 2. Real six-pair technical and sentiment analysis — research_protocol

Own analysis-contract.ts, technical-analysis.ts, sentiment.ts, analysis-server.ts and api/rotation/analysis/route.ts. Six aligned completed-close charts: BTC/CAD, ETH/CAD, LINK/CAD, ETH/BTC, LINK/BTC, LINK/ETH. Clearly identify derived ratios and triangulated LINK prices. Correct Wilder RSI, MACD, moving averages, observed close-based support/resistance and explainable confluence. Do not fabricate OHLC candles or volume. Real publisher RSS title sentiment with timestamp, sources, actual per-asset coverage and unavailable status. Separately label any Bitcoin-only broad sentiment index. Historical validation excludes sentiment unless genuine point-in-time archives exist. News affects context transparently; never invent validated positive forecast lift.

Acceptance: causal prefix inputs; rising/falling/flat RSI; aligned ratios; stale/future/unavailable handling; source URLs and timestamps; no neutral-success fallback on source failure; no fabricated historic sentiment.

## 3. Approved visual workspace — spot_history

Own AllocationWorkspace and presentational components, rotation/page integration and decimal-input normalization. Reuse auth, market polling and legacy ledger controls. Dominant draggable/touch allocation donut, current versus proposed, accessible percent fields, highly visible all six charts, technical/sentiment confluence and one simple overall recommendation. Draft change instantly updates expected net profit and advantage versus unchanged holdings. Save a new immutable projection on committed interaction, never every pointer movement; display save status and prevent Apply on unsaved/stale projection. One Apply runs and shows individual batch legs, actual costs and pause/resume/reconciliation states. Existing paper account must not appear connected live. Initial holdings accept both .1 and 0.1 BTC. Existing holdings changes use audited ledger controls rather than rewriting history.

Acceptance: approved reference hierarchy at390/1440; six real charts visible; decimal quantities preserved; drag total100/current holdings unchanged; real forecast not mock values; negative/unavailable predictions honest; saved/reloaded projection immutable; working whole-batch paper execution. Old research/manual details secondary.

## 4. Check-in and historical protocol — backend plus verification

At saved due date use actual historical completed prices, actual execution and costs, same cashflow treatment for starting-holdings baseline. Identify full/partial/unexecuted allocation and distinguish hypothetical outcome from actual portfolio. Display predicted versus actual profit and incremental gain in CAD and signed error. Historical replay uses the same causal freeze/cost/future-outcome cycle, only matured labels and continuous units. No new research sweep or profit guarantee.

Acceptance: immutable forecast; causal train-through less than signal time; saved due prices rather than refresh prices; actual fills graded; cashflows do not become profit; partial/unexecuted outcomes labeled; reproducible prefix check.

## 5. Integration, verification and release — root plus agents

Graph affected before edits; preserve every direct dependent. Build in agent, isolated webpack path if needed. Meaningful numeric fixtures for costs/units/baselines/causality, QA Agent against explicit local/true Preview endpoint and reserved account. No production write tests or funded orders. Capture real composed390/1440 screenshots, inspect measured and visual results, fix until pass, then private Telegram delivery per owner request. Root reviews contracts/diff/security and commits only scoped changes. Push existing authorized branch, test true Preview, release same verified source to production under prior explicit live approval, then read-only production smoke.

Acceptance: compilation and QA pass; credentials remain server-only; original dirty work preserved; actual live URL verified; screenshot delivered privately; CURRENT_WORK and durable context updated. Report any account connection limitation precisely; do not call paper execution funded execution.

## Decisions and deviations

- 2026-10-13: Owner explicitly selected Astra/cloud work for this crypto app earlier; this scoped build continues that authorization rather than broker dispatch.
- 2026-10-13: Provider-choice async question pending (Ndax/Kraken/another). Continue provider-neutral backend, paper execution, forecasts and UI while awaiting answer.
- 2026-10-13: RSS sources selected because actual public feeds are available; NewsAPI paid production entitlement is unverified. Sentiment absence remains visible.
- 2026-10-13: Existing accounts use audited ledger controls for holdings management; no silent balance rewrite.

## Execution status — 2026-10-13T16:28:26.849666-04:00 Eastern

- Steps1–4 implemented in isolated rotation namespace. Authenticated customer setup, .1/0.1, six real charts, immutable save, complete3-order paper batch/reload, owner isolation, idempotency, partial cancellation, numeric due/cashflow controls and real mouse/touch passed.
- Review corrections recorded: exactHOLD rounding/self-financing solver, atomic commit recovery, distinct zero-sized drag handles, primary live25second prices, safe5minute forecast refresh, preApply frozen numbers and expired forecast guards. Final semanticHOLD-after-new-quote probe pending before release freeze.
- Final isolated webpack build/postbuild TypeScript PASS; source manifest06cd6ac8c84ef9c97d4b5a560a90210289807b9107d655e7e01257d233bbc248. True Git Preview and production release checks next.
- Reviewed actual desktop/phone images privately delivered Telegram21692/21693. No inventedprofitable example inserted.
- Bounded historical diagnostic36cycles/259days lost money and lagged unchangedunits; no futureprofitability or validatedforecastedge claimed. Matured prospective browsercheckin awaits natural due time; its math/sourcecutoffs tested independently.
- Native signed execution remains blocked only on provider/account choice, asyncquestion and PA decisions queued. PaperApply is operational; never report it as fundedexecution. Original wallets, dirty files and processes preserved.

## Owner steering — 2026-10-13T16:43:03.938685-04:00 Eastern

Owner: "Include simple sliders as well as pie graph and they all stay linked ans update in real time". Add four visible sliders for BTC/ETH/LINK/CAD to the existing workspace. Use the same proposed weights for sliders, pie, exact percentages and live after-cost projection; sum100. Redistribute other regions proportionally so each slider can reach its full range. Manual slider edits clear exact-unit HOLD intent. Save an immutable projection at pointer release/keyboard commit, never every movement. Actual holdings remain unchanged until Apply.

Frontend owns existing TSX/CSS only. Acceptance: real mouse/touch/keyboard linkage, total100, immediate pie/percentage/profit feedback, one saved snapshot per committed adjustment, HOLD/manual distinction, real390/1440 mechanical/visual review. No new backend policy/account changes. Existing ad5911c truePreview baseline checks remain useful; final release uses a new tested source commit including sliders. Production remains unchanged until newPreview checks pass.

## Released paper scope — 2026-10-13T17:05:05.460448-04:00 Eastern

Paper portions of steps1–4 and all slider/verification/release acceptance completed. Live https://wolf-pack-eight.vercel.app/rotation from079ccbfa, exact Production artifact verified. Finalsliderbuild/hash a8985eb58d433ba33a15f0552ecc46bd680a8e0645edff6a5340c8c247950824. TruePreview customer/batch/security plusnewslidersdelta passed; read-onlyProduction/stable verified unchangedfinancialrecords. Final reviewed screenshots privatelydelivered21694/21695.

ExplicitHOLD bug corrected end-to-end includingreplay/outcomes; exactunits preserved,0orders/0cost. Corrected fixedhistoricalresult9090.98vsunchanged9779.63 remainsnegative; no profitableforecastclaim. Native signedexchangeintegration remains pendingownerprovider/accountchoice, not completed. No fundeddevelopmentorders. See allocation-release/RELEASE.md for exactproof/limits.
