Created 2026-10-13T13:56:02.474021-04:00

# Direct adaptive advice in the existing rotation app

This exists so that "recommendations based on successful backtesting proven strategy were surfaced to the user so the user just had to do the actual clicks to allocate according to the best advice".

Owner repeated that best informed predictions and weekly adjustments are the deliverable. Do not substitute another research report, approval question or backtest form. Existing authorization remains active. Full Astra is explicitly selected for this app.

## Verified gap
Current runStrategyStudy converts failed historical evidence checks into HOLD and null targets. StrategyPanel requires Backtest, Adopt and Refresh before advice. The phase2 predictors are isolated research and are not the existing app's predictor. Existing portfolio balances, review cadence, fees, public marks/history, paper preview and explicit approval already provide the surrounding workflow. Reuse those paths.

## Implementation contract
- Add a versioned current advice mode alongside immutable legacy momentum studies. Preserve old saved protocols and evaluator hashes; never reinterpret an old study as a new forecast.
- Port the already inspected causal pooled ridge calculations: five chart features, two registered penalties, strictly matured execution-aligned return labels, past-only scaling. Average the two point estimates for an explicitly versioned current estimate; do not claim this ensemble has an independently validated edge. Historical predictive evidence remains weak and is stated plainly.
- At refresh, forecast the coming saved weekly/monthly horizon from completed public history. Compare retaining the actual entered units against CAD and BTC/ETH/LINK targets at the owner's saved target allocation, accounting for fees and adverse slippage. Choose the greatest estimated after-cost value. HOLD is an actual cost-aware choice, never a synonym for failed statistical qualification. Insufficient/stale/invalid inputs produce an unavailable explanation instead of invented advice.
- Output direct action, target percentages and CAD values, indicative buy/sell differences, point forecasts, costs, plain reasons, uncertainty, as-of and next review. No fabricated probability of profit. Exact executable amounts still come from existing fresh quotes and minimum/increment checks.
- A single setup/refresh action prepares and saves current advice using existing trial/plan state. First-use target allocation and cost assumptions are supplied once in the app; do not invent owner risk preferences. Existing saved preferences are reused. Detailed research stays collapsed.
- Refresh must not make a trade. Existing quote, approval, revision/expiry checks and multistep target continuation remain authoritative. Preserve all legacy perp/LP wallets and trading logic.

## Files and ownership
Backend (strategy_runner): app/src/lib/rotation/{strategy-contract.ts,strategy-api-contract.ts,strategy-server.ts}; a tightly scoped forecast helper if reuse search confirms no implementation; existing trials/action/portfolio/preview handlers only where necessary for version compatibility. Never mutate the frozen research evaluator.
UI (spot_history): app/src/components/rotation/StrategyPanel.tsx; app/src/app/rotation/page.tsx or rotation.css only where needed for contract wiring or existing visual consistency.
Independent verification (research_protocol): numerical replay against Python model, fresh-data/fees/HOLD/SHIFT/unavailable cases, old-record restoration, same-account manual path and tenant/revision boundaries. Existing QA-agent checklists extended as required.
Root: shared contracts, plan/tracking, review and delivery.

## Steps and acceptance
1. Graph impact and reuse audit; capture current real UI. Acceptance: exact current route/caller map, old behavior documented, existing styles and ledger reused. High impact across recommendation/preview/action routes explicitly surfaced.
2. Implement versioned backend advice and persistence. Acceptance: causal predictor parity, finite math, deterministic cost-aware choice, invalid history fails closed as unavailable, legacy records still readable, no funded actions.
3. Implement advice-first UI. Acceptance: one action to prepare advice after saved inputs; clear buy/sell/hold and amounts; chart reasons, uncertainty and review date visible; backtesting not a user task.
4. Run isolated build/type checks and real browser QA through existing QA agent with explicit local endpoint and test account. Acceptance: account setup, advice refresh, saved restore, costed quote/explicit approval or genuine HOLD, revisions, mobile/desktop visual review. If genuine public data only yields HOLD, report the SHIFT path as numerically/API verified only rather than fabricate a live signal.
5. Save screenshots and verification report, update current work. Deliver local reviewable result. No deployment, private exchange connection, credential mitigation, live orders, or push triggering a deployment under this scope. Those existing boundaries remain intact; do not ask for deployment until the concrete implementation is complete.

## Cost / scope
Reversible local app implementation and verification, estimated30–60 minutes. Actual owner financial holdings and production remain untouched. No extra research campaign, model search, or redesigned ledger.

## Progress
- Current source and HEAD verified; graph refreshed to a951f39.
- Gap confirmed in current study gating and StrategyPanel workflow.

## Completed local implementation — 2026-10-13T14:09:44.408263-04:00

Implemented a separate forecast-advice namespace within existing trials storage. A new pure forecast helper averages the two causal models; exact entered holdings and the existing book/fee ledger compare HOLD and four asset targets. Public inputs, individual predictions, all candidate outcomes and fingerprints are saved for later reproduction. Existing strategy evaluator and accounting functions are unchanged.

The new StrategyPanel presents one Get/Refresh recommendation action, target CAD values, buy/sell differences, estimates, costs, reasons and next review. Previous strategies are retained in a closed disclosure. New advice pre-fills the existing manual preview; it does not bypass fresh quotes, revisions or explicit approval. Advice and quote lifetimes are separate. Portfolio-ID/revision/settings changes prevent acting on old advice; execution-limited cases retain forecasts.

Acceptance: independent numerical/parity/accounting checks passed; real local QA seven checks plus eight checks with zero extra slippage allowance passed; all four phone/desktop populated/restored screenshots passed; isolated production webpack build and TypeScript passed. The initial Turbopack symlink/environment failure is retained. Genuine current data produced HOLD in both cost settings; positive SHIFT accounting was verified synthetically, not mislabeled as live browser SHIFT coverage. QA extra-slippage preference restored to10bps.

Verification: docs/research/2026-10-crypto-rotation/direct-advice-verification/VERIFICATION.md. No production/private account/wallet/security changes. A concrete Preview deployment approval was requested after completion because the repository gates deployment and the prior production security hold remains. Pending release approval is not a request to resume development.

## Live release completed — 2026-10-13T14:32:57.669839-04:00

Owner explicitly authorized live publication with "pushed live". Scoped source commit ee9296a0243e335ca6254f6134b5d4fc3ec67dce was pushed. Exact Git Preview passed seven real-browser checks and four visual reviews; same clean source rebuilt with production environment. Production artifact dpl_4N8XVfrZL1QnPo5PBsThVUH4Rz47 is READY and the stable https://wolf-pack-eight.vercel.app/rotation alias points to it without a promotion rebuild. Authenticated production login/GET-only advice and portfolio restore, unchanged financial ledger, public markets and both-size visual checks passed. No production test data mutation, funded actions or credential mitigation occurred. Existing legacy exposure remains unresolved; profitable prediction and true live SHIFT browser coverage are not claimed. Release evidence: docs/research/2026-10-crypto-rotation/direct-advice-release/RELEASE.md.
