# Automated rotation study — proposed integration contract

Status: parent-approved pure evaluator implemented. Canonical integration plan: `docs/plans/2026-10-13-rotation-strategy-recommendations.md`. Numerical evidence: `docs/research/2026-10-crypto-rotation/AUTOMATED-SELECTOR-EVIDENCE.md`.

This exists so that "backtesting should be programmatically completed and inform an integrated strategy/recommendation plan in app, not just a user-run research form".

## Verified existing surfaces

Read current `replay.ts`, `validation.ts`, `research-contract.ts`, `ResearchPanel.tsx`, authenticated `trials/route.ts`, and bootstrap rebaseline plan. Current implementation runs one fixed momentum rule from a research form. It stores authoritative public history and actual-portfolio scenarios, restores reports, and computes chronological paired outcomes. Its latest target is the momentum winner, not the outcome of a strategy-selection procedure.

CPU AST graph rebuilt before proposing changes. `runResearch` directly affects `runValidation` and `evaluateHoldout`; their dependency reaches the trial route. `runValidation` directly affects the trial route. ResearchPanel symbol lookup was ambiguous; its exact file and parent rendering contract were read directly. Preserve v1 replay/evaluation behavior and stored protocol compatibility. New selector is a versioned extension of this research domain, not a second ledger or old-wallet feature.

## Proposed bounded study

1. Fixed, fully enumerated candidate family: positive momentum at 14, 30, 60, 90 and 180 calendar days (exactly five candidates). HOLD and costed CAD are distinct alternatives/comparators. Candidate windows are disclosed evaluator design constants, never claimed user preferences. This tests one small momentum family; it does not establish that momentum beats all other strategy families. No additional owner-picked lookback participates.
2. Capital, crypto allocation, cadence, fees and adverse slippage come only from explicit saved/form values. Lookback is selected by the bounded procedure, not required from the user. Do not load QA scenarios into a real account. Missing inputs return a needs-inputs state. Allocation is not a loss tolerance or guaranteed reserve floor between reviews.
3. One common comparison start after a 180-day warm-up, regardless of candidate window. Every comparator starts with identical already-owned equal-basket/CAD units at the same marks. HOLD leaves those units untouched. The CAD alternative liquidates its crypto at the same delayed execution proxy with actual assumed sell costs, then stays CAD without interest. A zero-return raw cash opportunity reference, if shown, must be separately labelled as a different starting composition.
4. Shared causal schedule: prior-day closes generate a signal on each weekly/calendar-month review; execution occurs at the following observed close. No same-close fills or filled data gaps. All candidates use adverse slippage, fees on every leg, nonnegative cash, and daily marked curves. Rebalance only when the selected target changes. HOLD means retain the current units, including across selector block changes; do not silently reset the basket.
5. Outer evaluation starts after 365 observed dates and advances in fixed 60-calendar-day blocks. Before each block, replay all registered candidates on the common inner prefix ending strictly before the block; pending trades or horizon labels reaching the block are excluded. Rank by the smaller after-cost CAD advantage over unchanged HOLD and costed CAD. Positive score required; deterministic ID tie-break. Otherwise select HOLD. Freeze the chosen candidate for that outer block. Per-review asset signals still use only available previous-day prices.
6. Evaluate one continuous selected-policy portfolio across outer blocks. Do not concatenate freshly reset portfolio profits or select a winner after inspecting its outer block. Outer HOLD and CAD curves share the selected-policy portfolio’s identical outer-start endowment. Report selector curve separately from candidate inner ranking/full retrospective leaderboard. Candidate switching does not itself waive fees or produce free endowment.
7. Latest selection repeats the same procedure through available completed data. The resulting current plan uses the actual saved portfolio units and fresh public marks; historical study still uses its declared scenario endowment. Return target allocation, current allocation, horizon/review date, selected rule, evidence counts, costs/assumptions, and explicit reasons. Never directly create an approval or mutate portfolio balances.

## Evidence gate for alignment

All outputs remain `retrospective-unvalidated`: all 719 days were already exposed. Chronological calculation controls code leakage; it does not recreate an unseen test or independent model development history.

Proposed conservative display gate, subject to parent agreement before coding: require at least three completed outer blocks and twelve completed non-overlapping outer review outcomes; outer selector net result must exceed both HOLD and costed CAD; latest selected candidate must have positive inner score and positive paired after-cost historical mean advantage. Otherwise the integrated result is HOLD with machine-readable reasons (`insufficient-observations`, `did-not-beat-hold`, `did-not-beat-cad`, `nonpositive-current-edge`). These are disclosed engineering sufficiency checks, not calibrated statistical significance or the owner’s investment policy. A lower-tail paired advantage gate can be added only as an explicit versioned selection criterion; it must not be presented as a maximum-loss guarantee.

For any displayed shift scenario, report horizon, historical mean shift/HOLD outcomes, paired mean advantage, empirical p10/p90, observation count and unvalidated status. Reuse joint historical asset paths, with labels complete before each forecast. Distinguish a retrospective candidate-selection result from a dependable forecast. No confidence score, expected-profit promise, advanced ML or untouched-test claim.

## Exact proposed pure interface

`runStrategyStudy(dataset: HistoryDataset, config: StrategyStudyConfig, scenario?: ResearchScenario): StrategyStudyReport`

`StrategyStudyConfig = Omit<ResearchConfig, "lookbackDays">`; exactly five candidates mean no lookback input.

`StrategyStudyReport`: version; exposure/status; explicit config; candidate specs/count; source coverage; common start; candidate results (final/HOLD/CAD values, fees, turnover, legs, drawdown and score); outer blocks (training cutoff, chosen candidate, all inner scores/counts, test dates); continuous outer daily curves with strategy/HOLD/CAD; completed review evidence; current plan (`needs-inputs` handled before pure call, `hold` or `experimental-shift`, reasons, target weights, latest signal date, next review/horizon, current-portfolio basis, paired outcomes); warnings.

`strategyStudyFingerprintSource()` includes candidate constants, selector/gates, accounting and all helpers. Every arithmetic/selection change bumps study version. Existing v1 registered protocols keep their existing fingerprint and evaluator.

## Persistence and integration ownership

- Research agent: `app/src/lib/rotation/strategy-contract.ts`, `strategy-study.ts`; pure deterministic evaluator and contract. Prefer shared audited accounting extracted from replay only if parent accepts the compatibility/fingerprint blast radius; otherwise add a small explicit generalized study replay while preserving v1. No API, UI, wallet or DB edits in this package.
- Backend agent: extend existing trial/API domain to register the whole study candidate set/config/data/hash before evaluation, persist all inner selections/outer outcomes, failed/abandoned registrations and repeated runs. Authoritative history/marks/portfolio fetched server-side; client cannot submit trusted results. Preserve owner RLS and source integrity. Existing generic jsonb trial storage can retain a versioned study document under allowed protocol/development kinds, but API/type discriminants and old restore behavior must explicitly support both versions.
- Parent/UI: integrated strategy-plan card in workspace and detailed research comparison. First explicit save/run completes the whole programmatic study; restoring an existing report shows its recommendation without requiring another research-form run. Refresh only with valid saved explicit inputs and a new source/date/portfolio revision; persist a new trial, do not overwrite evidence or run automatically on every render. Date/source/version fingerprints identify stale reports. Allocation plan must feed existing explicit public-price preview flow, with user review before any paper action.

## Acceptance

1. Real authoritative history, same start/date/cost assumptions, fixed enumerated trial count; no invented preferences or synthetic data.
2. Prefix-causality: truncating at a historical cutoff preserves all earlier choices, scores, forecasts and equity points. Perturbing later observations cannot affect earlier choices.
3. Independent CAD fee/cash/HOLD reconciliation; costs charged once; outer portfolio continuous; repeated target does not force turnover. Monthly schedule is calendar based.
4. Every completed and attempted candidate recorded; no best-looking outer candidate retroactively replaces selector outcome. UI reports selector versus both baselines and exposes insufficient-evidence HOLD.
5. Real browser saved-report restoration and workspace recommendation use; exact source/portfolio provenance visible; no automatic trade; actual composed mobile/desktop screenshots reviewed.
6. Run the full bounded comparison programmatically on genuine data, save complete numerical evidence, and report both favorable and unfavorable outcomes. Existing old wallets, exchange credentials, deployment/env and live execution untouched.

## Frozen interface detail sent for integration

Version `cad-rotation-selector-v1`. Candidate IDs `momentum-14`, `momentum-30`, `momentum-60`, `momentum-90`, `momentum-180`; selector fallback `hold`. CAD is a comparator and a momentum rule may also select CAD when every trailing return is nonpositive. HOLD means retain actual current units; it does not mean liquidate into CAD.

```ts
type StrategyStudyConfig = Omit<ResearchConfig, "lookbackDays">;
type StrategyCandidateId = "momentum-14" | "momentum-30" | "momentum-60" | "momentum-90" | "momentum-180";
type StrategyChoice = StrategyCandidateId | "hold";
type StudyMetric = {
  finalCad: number; holdCad: number; cashCad: number;
  excessHoldCad: number; excessCashCad: number;
  feesCad: number; turnoverCad: number; trades: number;
  maxDrawdownPercent: number; completedReviews: number;
};
type StudyPoint = { date: string; strategyCad: number; holdCad: number; cashCad: number };
type CandidateScore = {
  candidateId: StrategyCandidateId; lookbackDays: number;
  scoreCad: number; metrics: StudyMetric;
};
type StudyBlock = {
  start: string; end: string; trainingThrough: string;
  selected: StrategyChoice; scores: CandidateScore[];
  completed: boolean;
};
type StrategyPlan = {
  status: "hold" | "experimental-shift";
  validation: "retrospective-unvalidated";
  candidateId: StrategyChoice;
  target: Asset | null;
  targetWeights: Record<Asset, number> | null;
  reasons: string[];
  signalThrough: string;
  horizonStart: string; horizonEnd: string;
  basis: "entered-portfolio" | "equal-basket-scenario";
  startingValueCad: number;
  outerCompletedBlocks: number; outerCompletedReviews: number;
  paired: { observations: number; shift: OutcomeSummary; hold: OutcomeSummary; advantage: OutcomeSummary } | null;
};
type StrategyStudyReport = {
  version: "cad-rotation-selector-v1";
  exposure: "already-exposed";
  status: "retrospective-unvalidated";
  config: StrategyStudyConfig;
  candidateCount: 5;
  coverageStart: string; coverageEnd: string;
  comparisonStart: string; outerStart: string;
  candidates: CandidateScore[];
  blocks: StudyBlock[];
  outer: { metrics: StudyMetric; points: StudyPoint[] };
  latestSelection: { trainingThrough: string; selected: StrategyChoice; scores: CandidateScore[] };
  plan: StrategyPlan;
  notes: string[];
};
```

Candidate final rankings and latest selection are descriptive training comparisons. Only the separate continuous outer selector curve measures the selection procedure on chronologically later data. Outer partial block curve remains displayed but does not count as a completed evidence block. Pure report contains no UUID, server time, owner ID or trusted database revision. Backend protocol owns source/evaluator hashes, actual portfolio ID/revision, creation time and all trial counts; report embeds no duplicate dataset.

`targetWeights` contains fractions summing to one for an experimental shift; crypto share does not exceed the explicit chosen allocation at that target. Actual weights may drift before later reviews. HOLD returns null weights/target to preserve units. Backend generates the concrete ordered sell/buy plan from target weights and authoritative current balances/public depth using the existing decimal engine. Every subsequent paper leg still uses a fresh preview and explicit approval. Client-side numeric weights never bypass server provenance or quote accounting.

Proposed evidence gate requires three complete 60-day outer blocks and twelve completed outer review horizons. The 719-day archive has fewer than twelve full monthly outer horizons, so monthly can truthfully return insufficient-evidence HOLD even when its training winner is profitable. Gate counts are a conservative engineering rule, not a statistical skill proof. Parent approved this exact threshold before implementation; do not silently lower it to obtain a shift.

Implementation correction: latestSelection retains the currently active 60-day block choice and its earlier training cutoff; it does not rerank every daily refresh. Paired scenarios include an explicit target and remain hypothetical when the recommendation is HOLD.
