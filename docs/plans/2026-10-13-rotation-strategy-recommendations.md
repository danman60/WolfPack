# Programmatic backtesting and integrated rotation recommendations

Active implementation: October 13, 2026 Eastern, following the owner's correction to the October 12 paper release.

## Purpose and authorization

This exists so that "I'm looking to trade crypto; i just want to know when to shift positions between CAD/BTC/ETH/LINK any pairing in/out looking to only make weekly or monthly trades".

Owner correction: backtesting must be completed programmatically and inform a strategy and recommendation plan built into the app. The existing standalone research form and manual paper trade controls do not complete that workflow. Implementation remains full Astra. The new CAD spot paper domain is authorized; legacy wallet policies, exchange credentials, funding and real orders are outside this implementation.

## Verified starting point

- Source `9e7b566` provides genuine history, one fixed-rule replay, paired historical outcome estimates, authenticated workshop persistence, immutable HOLD and fresh manually approved paper quotes.
- `ResearchPanel` runs one user-configured lookback. `validation.selected` ranks trailing returns; no bounded candidate-selection study connects its result to the workspace's trade controls.
- Existing `wpr_trials` permits protocol/development/holdout records. Existing portfolio revision checks and quote consumption are the execution primitives to extend.
- All 719 currently archived historical dates have already been exposed. Additional historical comparisons are retrospective; they cannot be relabeled as an untouched test.
- A separate legacy public API-key exposure is documented. Automatic approval review blocked mitigation; post-interruption live inspection confirmed the setting, deployment and source unchanged. This feature does not retry those blocked environment or service actions.

## Implementation contracts to finalize before code

1. **Study:** one authoritative history archive, explicit owner portfolio/cadence/fee inputs and entered target-allocation/slippage assumptions. Compare a frozen five-candidate set (14/30/60/90/180-day momentum) against unchanged HOLD and a costed CAD strategy, with identical starting holdings, dates and cash-flow treatment. No silent owner risk or capital defaults. The percentage is target crypto allocation when shifting, not a hard exposure/loss limit; HOLD preserves units and permits weight drift.
2. **Selection:** choose using completed earlier inner periods, then carry a continuous portfolio through chronological outer periods. Report candidate results, selection history, costs, drawdown, sample limits and all trials. Choose HOLD when evidence is insufficient or does not demonstrate an after-cost advantage over the comparators. Do not select a winner using the same outer results reported as independent evaluation.
3. **Plan:** adopt the frozen adaptive selection procedure and its configuration, rather than permanently freezing the latest winning lookback. Retain evidence in the authenticated server record. Workspace presents a plain-language SHIFT/HOLD decision, reason, current versus target allocations, horizon, paired shift/HOLD estimates and uncertainty. Research remains explicitly unvalidated. Initial engineering evidence gates require at least three completed 60-day outer blocks, twelve completed outer review horizons, positive outer net advantage over both comparators, positive latest inner score and positive current paired mean advantage. These are disclosed engineering gates, not statistical significance or calibrated confidence.
4. **Execution:** convert a proposed target allocation to ordered paper steps. Reuse fresh order-book previews, existing manual approval, atomic portfolio revision and one-time quote consumption. Bind strategy quotes to their active plan and recommendation; reject superseded plans and stale portfolios. Never execute automatically or call an exchange's private API.
5. **User experience:** primary action is "Backtest & build my plan", not manual lookback hunting. Reuse advanced research and existing portfolio/quote components. Owner supplies unresolved allocation limits; do not prefill them with QA figures. Show a useful HOLD result rather than force a trade.

## Ownership and acceptance

- **History agent:** `strategy-contract.ts`, `strategy-study.ts`, bounded executable study and numerical evidence. Acceptance: fair baselines, causal prefix invariance, chronological selection, reproducible results, explicit candidate/trial counts and costs; adverse/no-edge cases produce HOLD.
- **Engine agent:** authenticated strategy APIs, minimal reuse/extensions of trial and portfolio persistence, migration if required, recommendation-to-quote binding. Acceptance: owner isolation, server-owned data/results, plan CAS, invalidation on portfolio/plan change, exact quote reconciliation and no duplicate approval.
- **Build/UI agent:** composed workspace strategy component, existing page/quote integration, responsive mock and real browser QA. Acceptance: explicit setup → programmatic comparison → saved plan → clear recommendation → fresh preview/manual paper approval or HOLD → reload/export; phone and desktop reviewed.
- **Parent:** contract decisions, written scope, independent evidence review, final report. No unsupported claim of profitable or validated predictive performance.

## Verification and release

First complete and review the strategy workflow on the explicit local/isolated test target using the existing QA Agent; no production write harness. Run appropriate TypeScript/build checks in an agent and review source changes. Preserve unrelated dirty files and stage explicit paths only. Any later deployment must separately account for the documented legacy-key exposure; the previous paper release's green checks do not close that security finding or this missing product workflow.

## Progress

- [x] Owner correction captured; missing connection between backtesting, strategy and recommendations verified in source.
- [x] Existing financial and database primitives identified for reuse.
- [x] Selection semantics and initial evidence gates agreed; detailed evaluator contract in `2026-10-13-rotation-automated-strategy-study.md`. Backend owns exact API and persistence bindings; UI consumes that shared contract.
- [x] Programmatic strategy study implemented and run against genuine history. Ten numerical verification groups passed; both QA schedules return HOLD. See `AUTOMATED-SELECTOR-EVIDENCE.md`. Current-recommendation cadence review remains in progress.
- [x] Persistent strategy and recommendation-to-approval workflow implemented. Migration005 applied after review; backend source frozen after independent review, two-account checks and numerical step/cutoff verification.
- [x] Composed local browser workflow, calculations, ownership and stale cases verified. Final10/10 browser checks,12/12 two-account API checks, isolated production build and postbuild TypeScript passed. Positive recommended-SHIFT browser coverage is not claimed; the current genuine-data recommendation is HOLD.
- [x] Final evidence, documentation and release status recorded without conflating paper and live execution. Source559ea6b deployed as Preview artifact `dpl_6a3g9tmBbQxdCgxgjUwnhjdmY5vH`; exact deployed browser10/10, auth/database/header checks and144-file bundle scan passed. Vercel sign-in required; Production unchanged. Private exchange auth/live execution remain unbuilt, and no profitable strategy or positive recommended-SHIFT browser path is claimed.


## Frozen backend contract — October13 09:59 Eastern

Adaptive selector adoption approved. Detailed reuse/CAS design: [server design](2026-10-12-rotation-integrated-plan-design.md). Backend owns `strategy-api-contract.ts`, `strategy-server.ts`, extensions to existing trials/portfolio/preview/action routes and server commit helper, plus workshop migration005. No legacy/environment/backend-service changes.

- Strategy trial envelopes carry `data.namespace="strategy"` and `protocolVersion="cad-rotation-selector-v1"`; old research GET/list/restore filters namespace absent, so new reports cannot reach v1 ResearchPanel. Export retains all.
- Register via existing POSTtrials `{id,kind:"protocol",data:{namespace:"strategy",protocolVersion,config:{riskPercent,slippageBps},expectedRevision}}`. Server derives current CAD capital/actual units, cadence and fees from portfolio/public marks. Evaluate via `{id,kind:"development",data:{namespace:"strategy",purpose:"study",protocolId}}`. Return `{trial}`. One protocol archive, report-only development rows.
- Adopt via POSTaction `{kind:"adoptPlan",studyId,expectedRevision,expectedPlanRevision}`. Return `{portfolio,planState}`; activePlanId references trusted study, planRevision is separate from financial revision. Adoption mutates no financial JSON.
- Current recommendation via POSTtrials `{id,kind:"development",data:{namespace:"strategy",purpose:"recommendation",expectedRevision,expectedPlanRevision}}`. Server archives current source/config, reruns adaptive policy against actual units, and appends report/provenance. Envelope exposes `decision:hold|shift|blocked`, `nextShift:{from,to,amount}|null`, reasons/note, plan/portfolio revisions, expiry (15minutes) and source references. HOLD null target preserves units. Infeasible books/minimums are blocked, not model HOLD.
- Quote via POSTpreview `{recommendationId,expectedRevision,expectedPlanRevision}`; server derives source/target/decimal amount, rejects overrides, fetches fresh full books. Existing response and approve path remain. SQL atomically verifies active plan and recommendation during quote consumption.
- Recommended HOLD via POSTaction `{kind:"hold",recommendationId,expectedRevision,expectedPlanRevision}`; record once with provenance and unchanged balances/fees. Manual actions keep current semantics.
- GETportfolio adds planState; GETtrials?strategy=1 and GETtrials?id=...&strategy=1 serve only strategy envelopes. One next pair per recommendation: liquidate non-target crypto in fixed asset order, then solve one target buy/trim using fresh full depth and post-fee marked allocation. Amounts respect eight decimals and venue increment, never exceed inventory, and require individual approval. Venue minimum/increment residuals become disclosed HOLD-at-target; insufficient depth blocks. Maximum three shifts per reviewed target. Prices/costs remain explicit at owner approval; historical net estimates are not charged again.

Migration review precedes apply: add active pointer/plan revision, service-only adoption and guarded-commit RPC, and audit-trigger discrimination for plan-only updates. Keep current trial kinds and owner RLS. Verify adoption leaves financial ledger untouched, concurrent adopts/approvals reject stale state, old research restoration remains v1-only, and new strategy artifacts export completely.

## Review findings — October 13 Eastern

- Parent reviewed migration005 before authorizing its WPR-only application: service-only grants, portfolio row locking, separate plan revision, preserved original financial CAS and plan-only audit event.
- Historical curves use the explicitly disclosed equal-basket starting scenario. Current recommendations use actual saved holdings. The UI must distinguish these bases.
- Raw gate identifiers are replaced with plain English. A withheld candidate's hypothetical outcomes are labeled separately from the actual HOLD instruction.
- Current recommendations must obey the adopted weekly/monthly schedule and unchanged-target retention behavior. Refresh cannot silently introduce daily rebalancing into a policy evaluated at a slower cadence. History/backend agents are aligning these semantics before final acceptance.
- Recommendation-bound approval must recheck evaluator provenance in addition to atomic SQL plan/portfolio revision checks.
- Separate owner research session owns `strategy-discovery/` and its data/plan. Its longer-history search is not included in the five-candidate evidence or staged by this integration.
- Review corrections completed: cumulative archive retained across refreshes; quotes resize from fresh books; at most three steps retain a reviewed target; completed unchanged targets retain units; unfinished targets expire at the next review without being marked complete. Four ordinary/DST cutoff cases pass in both implementation and independent review.

### Final execution review corrections

Server execution sells non-target crypto in fixed asset order, then solves one post-fee target buy/trim against fresh full books. At most three manually approved steps per review. Minimum/increment residuals remain owned and disclosed; insufficient book depth blocks execution. Consumed quote metadata and immutable decision audit preserve progress/completion, including no-trade completion recorded through recommended HOLD. Completed unchanged targets retain natural drift.

An unfinished target continues only until the next scheduled review begins (Eastern midnight, weekly +7 days or next calendar month). Store and display that cutoff. Recommendation expiry is capped at the cutoff, so SQL rejects boundary-crossing approvals atomically. At/after cutoff, current policy and evidence govern remaining actual holdings; an expired incomplete target is never relabeled completed by HOLD. Old records remain immutable. Cumulative adopted archives append to the newest verified archive with unchanged baseline configuration and calendar anchor.

Verification: seven genuine-book/hypothetical-balance CPU solver scenarios passed; twelve real two-account API checks passed. These verify arithmetic and auth/CAS segments, not an end-to-end positive SHIFT recommendation. Final composed browser rerun remains required after source freeze.
