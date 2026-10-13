# Allocation backend review

Reviewed 2026-10-13, Eastern. Existing HEAD c217479 plus scoped allocation changes; final source hashes accompany the isolated production build.

## Scope and boundaries

The new workspace uses existing rotation membership authentication, exact eight-decimal paper ledger, public market/history adapters and owner-scoped persistence. No changes to the old perpetual-wallet trading code, engine.ts, or immutable strategy-study.ts. Native exchange execution is not connected: execution-adapter.ts reports mode paper, provider paper, connected false. Its native interface is a contract, not an implemented funded connector. No funded orders were submitted.

## Authentication and persistence

All new private routes use protectedRoute before handler logic. Mutations enforce same-origin, bounded JSON requests and per-account rate limits. IDs pass UUID validation. Queries constrain owner_id to the verified session and use its authenticated JWT; client ownership fields and forecast economics are not accepted. Projection construction fetches its own history, current books and complete analysis snapshot. Settings, projections and outcomes are append-only namespaces in existing wpr_trials. The new batch table permits authenticated owner reads and service-only writes; its RPC is unavailable to anonymous/authenticated clients. Applied migration permissions were independently queried by root; see migration006.txt.

Each projection freezes starting units and revision, reference books/history, forecasts, weights, due time, costs, analysis, source hash, evaluator hash and build commit. Outcomes are separate immutable records, unique per owner/projection. Saved settings do not require visiting old research screens.

## Execution and recovery

Apply authorizes the saved paper target and its displayed total-cost allowance. Requests cannot raise that allowance above the frozen estimate. Supported execution paths are the three existing Ndax CAD books; analytical cross-pair charts are not presented as executable routes. The allocator computes self-financing post-cost quantities, respects captured depth/minimums/increments, and releases proceeds with sells before buys. Remaining buys are repriced from actual owned funds.

Batch intent is persisted before a fill. Each confirmed paper fill and its batch revision commit in the same database transaction, through the existing portfolio CAS/immutable-ledger function. A unique owner/projection batch prevents duplicate Apply; stale batch or portfolio revisions reject duplicate advancement. Pricing/limits failures pause the remaining sequence. Cancel retains confirmed fills and permits a later allocation. Unknown/partial native order states cannot be resumed blindly.

Final review found and fixed a recovery defect: atomic database commit originally sat inside the pricing-error catch. A database failure could then attempt to persist mutated fill status without its ledger commit. The commit now sits outside that catch. A transport/commit error propagates; callers reload persisted state before retrying. No fallback write fabricates a fill.

## Forecast and allocation method

The predictor averages pooled ridge simple-return estimates at penalties 1 and 10. Inputs are past 7/30/90-day log returns, 30-day volatility and price/SMA200. Scaling fits only training observations; training labels must mature strictly before the signal close. At least 252 origin dates are required. No probability of profit or validated forecast edge is claimed.

The recommendation compares unchanged units, all CAD, and a deterministic grid of three-asset allocations at the owner's saved crypto budget. The grid uses tenths of that budget; arbitrary owner-edited four-asset targets are accepted independently. Current fees, order-book spread/depth and an explicit extra slippage allowance enter the value comparison. Unpriced alternatives are disclosed; an unavailable comparison is not relabelled market HOLD. Explicit `preserveUnits` HOLD intent preserves units regardless of changing market weights. Arbitrary fixed-weight drafts remain rebalances.

Six-pair technical trends and actual headline tone qualify the explanation and confidence. They do not inject an unvalidated numerical uplift into price forecasts. Historical sentiment is excluded without a point-in-time archive.

## Check-ins and replay

Source history dates label the start of a UTC daily candle; completion is the next midnight. The saved horizon uses completed signal D, with execution-aligned endpoint D+8 for weekly or clamped calendar-month(D)+1 day for monthly. Check-in requires that exact completed reference close, never the current quote. Ledger events and cashflows are cut at the same due instant. Current executable Ndax books and Kraken reference closes are explicitly different sources.

Actual, hypothetical target and unchanged-starting-unit results remain separate. CAD deposits/withdrawals are matched and removed from profit. Partial or unexecuted targets are labelled accordingly. The pure replay uses the same causal fit, allocation and cost helpers; freezes before the next-close modeled fill; carries continuous units; and grades outcomes only after maturity. Historical depth is unknown, so replay explicitly models adverse reference-close fills rather than claiming observed exchange fills.

Independent verification reported seven financial sign-region fixtures with maximum equity error CAD4.38e-8; exact due-date/cashflow/partial-execution controls; 36 chronological forecast cycles and independent Python fit/future-perturbation checks; authenticated retry/CAS/account-isolation/pause/resume/cancel controls. Tests do not establish future profitability.

## Integration and graph

Graph refreshed locally using AST only: 12,702 nodes and 16,236 edges after the explicit HOLD correction. Affected checks cover estimator, save, Apply, advancement, check-in and RotationPage. Estimator changes reach new projection/batch routes and client preview; existing accounting exports remain unchanged. Page integration passes the existing authenticated request helper and portfolio into the workspace, adopts server-returned portfolio revisions, and clears stale manual previews after batch updates. Leading-dot decimal entry normalizes to the existing canonical decimal format.

Final delta production webpack build and post-build TypeScript passed; exact manifest `d10594a3e5710f3495004b4e8531a211b6169cda78a2ca3b946ff1400e632170`, zero source drift. Static scan: 162 files, 0 secret-value matches. Includes live-market UI integration and immutable pre-Apply projection display. New Apply after the frozen due date returns409; advancement of an expired remaining plan pauses before pricing/fills, with existing batch retries remaining read-only/idempotent. Final AST graph: 12,702 nodes,16,236 edges. Durable summary: `../allocation-rebuild/build-summary.json`.

HOLD drift correction: the observed stale-weight bug was reproduced without applying a trade. Recommendation now carries an explicit hold/shift/unavailable decision. Saving a HOLD ignores stale percentage weights and freezes authoritative current units with zero costs. Applying it creates a completed zero-order batch after normal portfolio/revision/due checks. The same intent persists through next-close historical replay. Applied zero-order HOLD counts as fully executed at check-in; an unapplied projection remains separately labelled. Legacy projections without the optional flag retain their original fixed-weight meaning.
