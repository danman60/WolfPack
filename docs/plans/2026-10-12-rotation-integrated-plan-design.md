# Rotation integrated comparison and paper plan — proposed server contract

Sourced: 2026-10-13T09:57:40-04:00 Eastern. Design only; parent contract agreement required before implementation. No migration applied. No legacy key/env/backend/service change belongs to this task.

This exists so that “backtesting should be programmatically completed and feed integrated strategy/recommendation plan in new CAD/BTC/ETH/LINK rotation app”.

## Verified reuse and impact

Live workshop query found two protocol and two development rows in `wpr_trials`. Its check allows protocol/development/holdout only. Existing rows have owner, UUID, timestamp and JSON data. `wpr_portfolios` stores financial revision and validated financial JSON; `wpr_previews` already stores owner, portfolio/revision, trusted market/economics, expiry and consumption. No new table is proposed.

Current trial registration server-loads real history and freezes source/evaluator hashes. Current quote/action paths already fetch fresh books, seal/regenerate engine economics, reject changed revision/expiry, and consume one quote atomically with ledger commit. Extend those paths. Financial engine, original v1 research behavior, existing wallets and legacy backend remain unchanged.

Graph affected: previewShift → preview/action; approveShift → action; commitPortfolio → portfolio/action; runValidation → trials. Migration extends transaction/audit rules. All direct consumers are in this bounded integration; simultaneous adoption and approval is the main new race to reject.

## Aligned pure evaluator

Reuse the history-agent contract in [automated study design](2026-10-13-rotation-automated-strategy-study.md): `runStrategyStudy(dataset, config, scenario?) → StrategyStudyReport`, fingerprinted version `cad-rotation-selector-v1`. Configuration excludes lookback; five candidates are fixed at14/30/60/90/180, with unchanged HOLD and costed CAD comparators. Historical selection is causal and uses a continuous outer portfolio. Exact evidence gate remains subject to parent alignment; never lower it to force a shift.

`report.plan` supplies hold/experimental-shift, reasons, current target weights or null, paired outcomes, signal/horizon and unvalidated status. HOLD with null weights means retain current units, not sell into CAD. Pure results carry no owner/UUID/revision. Backend owns those trusted bindings and exact decimal shift amounts.

Recommended adoption semantics: adopt the versioned adaptive selector and explicit paper configuration, not freeze whichever candidate won today. Each subsequent review reruns the same disclosed bounded selector. Parent must agree this semantics before implementation.

## Persist using existing kinds

Keep the existing database kind constraint. Extend TypeScript discriminants by protocol/study version, preserving original v1 restores. This supersedes the initial idea of adding separate comparison/plan/recommendation kinds.

- **Protocol row**: one authoritative archived dataset; study config/candidate specification, source hash, evaluator fingerprint, build/version, actual paper scenario and portfolio/revision at registration. Client supplies explicit capital/cadence/allocation/cost inputs; server supplies history, marks and identity. Never fabricate missing inputs or treat research allocation as approved real-money risk.
- **Development row, purpose study**: protocolId and complete server-computed StrategyStudyReport, including every candidate, inner ranking and continuous outer results. All candidates share source/endowment/cost assumptions. Client cannot submit trusted results or a winner. Preserve registrations even if evaluation fails; use a visible failure attempt record/envelope rather than hiding an abandoned trial.
- **Active adopted plan**: add nullable `active_plan_id` FK to the existing trusted study development row plus nonnegative `plan_revision` default0 on `wpr_portfolios`. Immutable study→protocol carries adopted configuration and evaluator; pointer records current adoption. An append-only audit records every adoption/deactivation, including prior/new IDs and plan revision. No separate mutable plan table or financial event is required.
- **Development row, purpose recommendation**: adopted study ID/plan revision, source protocol/version/hash, current portfolio ID/financial revision and canonical holdings hash, current marks/history provenance, generation/expiry and trusted report.plan. Store server-derived nextShift `{from,to,amount}` decimal strings or HOLD; include target weights and any remaining rebalance work. No data/stale history is a blocked error, not model HOLD. A refresh appends evidence; it never overwrites a prior trial.

Do not duplicate the archive in every report. If fresh history is required for a later review, register a new source snapshot/protocol linked to the adopted selector/config first; the recommendation refers to that exact archive. Canonical hashing must be stable after PostgreSQL JSONB key ordering.

Keep active-plan columns outside financial Portfolio JSON. Adoption cannot change balances, original baseline, financial revision, fees or basis. SQL checks referenced row owner, purpose/version and matching portfolio rather than relying on FK alone. No valid adopted study means needs-plan; no explicit required inputs means needs-inputs.

## Proposed existing-route API extensions

All private handlers retain protectedRoute, GoTrue membership, user-JWT reads, origin validation, bounded bodies and durable rate limits.

1. `POST /api/rotation/trials` registers a study-version protocol with `{id,kind:'protocol',data:{protocolVersion,config}}`, server-authoritative data and portfolio snapshot. Study development request `{id,kind:'development',data:{protocolId,purpose:'study'}}` runs all five candidates. Parent UI can orchestrate one save/run operation while registrations remain durable before computation. Return existing `{trial}` envelope. Original v1 remains supported explicitly.
2. `POST /api/rotation/action` `{kind:'adoptPlan',studyId,expectedRevision,expectedPlanRevision}`. Server validates owner study and compatible evaluator/source. One SQL transaction locks portfolio, checks both revisions, validates trusted study, updates pointer/plan revision and appends adoption audit. Return `{portfolio,planState}`. Two competing adoptions produce exactly one success and one409. No extra financial ledger event.
3. `GET /api/rotation/portfolio` extends existing response with `planState:{activePlanId,planRevision,study}|null`. Existing Portfolio JSON remains compatible. Saved recommendation is current only when all portfolio/plan/source bindings match.
4. `POST /api/rotation/trials` `{id,kind:'development',data:{purpose:'recommendation',expectedRevision,expectedPlanRevision}}`. Server derives active configuration, archives any updated source, reads actual paper units/current marks and runs pure evaluator. Persist trusted recommendation envelope and exact nextShift. Request ID ensures replay cannot multiply attempts silently. Run only on explicit compute/refresh or a controlled new source/date/revision trigger—not each render.
5. `POST /api/rotation/preview` adds branch `{recommendationId,expectedRevision,expectedPlanRevision}`. Server loads owner's recommendation, verifies active plan/holdings/expiry, and derives from/to/amount itself. Fresh full books go through existing previewShift. Browser-supplied overrides are rejected in this branch. Save recommendation/plan provenance in existing preview JSON. Original manual quote remains explicitly manual.
6. `POST /api/rotation/action` kind approve retains previewId+expectedRevision. Regeneration remains unchanged; SQL commit must also lock/recheck any quote's plan binding in the same transaction that checks portfolio revision and consumes quote. Plan changes after quote creation reject409 even when holdings are unchanged. Manual quotes preserve their current portfolio-only semantics.
7. Recommended HOLD uses existing recordHold via `{kind:'hold',recommendationId,expectedRevision,expectedPlanRevision}`. SQL validates same bindings and records provenance. HOLD creates no quote/fill/fee. Replay fails by financial revision/request identity; no second success ledger event.

Exact next-shift derivation remains backend-owned: weights must be finite, nonnegative and sum to one; amounts pass the eight-decimal boundary, round down and never exceed inventory. One recommended pair at a time fits the existing safe engine. After approval, holdings revision changes, so recalculate before another leg. Approved execution sells non-target assets in fixed asset order, then solves one post-fee target adjustment against fresh full depth. Venue minimum/increment residuals stay owned and disclosed; depth failures block. At most three manually approved steps, each recomputed from current balances. Unfinished execution expires at the next scheduled Eastern review. Immutable decision audit/consumed quote metadata preserve completion; an expired partial target is superseded without being marked complete.

Historical paired net advantage already includes specified costs. The integration must state whether quote review compares actual costs to assumptions or only enforces a disclosed cost envelope; never subtract all fees a second time. Under-minimum/insufficient-depth quotes are infeasible, not fabricated fills or a model HOLD.

## Required migration, proposed only

One forward workshop-only migration after004:

- Add active plan FK/revision to wpr_portfolios and service-only atomic adoption RPC with owner/version/purpose checks.
- Extend existing portfolio commit RPC to validate persisted recommendation/plan binding under the same portfolio row lock and record recommended HOLD provenance. Preserve manual actions.
- Update `wpr_portfolio_write_audit`: it currently assumes every UPDATE appends a financial event. Plan-only updates must emit an adoption audit instead of duplicating the previous trade. Existing audit kind trial plus detail.action=adoptPlan avoids changing its constraint; use one consistent contract.
- Keep existing trial kinds/RLS/owner reads/append-only records. Browser roles still cannot write financial JSON or execute mutation RPCs. Existing broad trusted service-role boundary remains a documented limitation.

Export already includes all trials and consumed quotes. Add current plan state and persist recommendation/plan references in consumed quote data/audit so exported execution is traceable. Historical research list filters compatible version/purpose; complete export never drops the newer records.

Check actual migration sequence before implementation. This design task does not authorize live application of the proposed migration.

## Acceptance

1. One authenticated programmatic workflow computes all five candidates from a registered authoritative archive, persists every attempt/result and derives selected policy/HOLD without browser-entered results.
2. Same source/start/costs, causal cutoffs, deterministic ties, version hashes and exposed-history limitation are visible. Monthly insufficient evidence remains truthful HOLD.
3. Adoption survives reload; cross-owner IDs/direct JWT queries fail. Adoption leaves financial balances/revision/basis/fees/opening/HOLD baseline identical; audit records adoption, not a duplicate trade.
4. Current recommendation uses actual portfolio units and adopted selector. Needs-inputs/needs-plan/stale/unavailable, valid HOLD, experimental shift and infeasible quote remain distinct.
5. Recommendation → genuine fresh quote → manual approval commits once and exports original quote/recommendation/plan IDs.
6. Competing adoption/approval, changed holdings, changed plan, quote expiry, duplicate approval and edited client economics are refused atomically. HOLD preserves units/fees and records once.
7. Existing manual shift/HOLD/cash flows/v1 research/export remain intact. No private exchange calls, keys, live orders, funding, legacy wallet edits, env changes or deployment.

## Pending parent contract

Confirm adaptive-selector adoption; exact evidence threshold from history design; deterministic decimal next-pair sizing/dust policy; request-level source refresh behavior and cost gate. Pure evaluator is assigned to history agent; proposed backend ownership is trial/action/portfolio/preview routes, server helpers, one migration and runbook changes. No implementation started.
