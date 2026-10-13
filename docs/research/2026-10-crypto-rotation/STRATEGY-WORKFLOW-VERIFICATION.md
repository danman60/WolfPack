# Strategy workflow verification

Owner intent: completed programmatic backtesting must inform a strategy and recommendation plan inside the app, leaving each allocation decision to the owner.

## Scope

The existing paper workspace now compares a fixed family of five momentum windows, saves the complete study, adopts its adaptive selection procedure, and calculates a current recommendation from saved holdings. The UI explains the decision and hypothetical outcomes, including costs and downside. Existing paper quote approval and HOLD recording remain the execution paths. No private exchange authentication or live order path is added.

This integration does not claim a successful strategy was found. The genuine-data QA study returns HOLD for both cadences. Its historical results and limitations are documented in [AUTOMATED-SELECTOR-EVIDENCE.md](AUTOMATED-SELECTOR-EVIDENCE.md). Separate longer-history strategy discovery belongs to another owner session and is not evidence for this evaluator.

## Verified intermediate checks — October 13, 2026 Eastern

- Eleven numerical acceptance groups passed, including 24 causal-prefix comparisons, 36 boundary scenarios and six schedule checks. Historical baseline accounting, costs and drawdown reconcile independently.
- Ten local browser checks passed with zero console errors. The real journey runs a study, adopts it, saves the current HOLD recommendation, records HOLD once without changing units or fees, rejects stale reuse, restores records after reload and exports the immutable evidence.
- The browser checks reject client pair/amount overrides and confirm old advanced research and new strategy records remain separate.
- Actual desktop and phone screens passed measured overflow, text and contrast checks and visual review. A reviewed local desktop capture was delivered through `shot-approve`.
- Workshop migration005 was reviewed and applied separately. Readback confirms the active plan pointer and separate plan revision, invoker functions with fixed search paths, and RPC execution granted to service role only. Plan adoption preserves financial data/revision; its audit event is separate from a trade.
- Twelve two-account API checks passed: cross-owner reads/adoption return404, stale plan adoption returns409 without financial or plan changes, and research namespaces remain isolated.
- Seven server solver scenarios and six independent reviewer scenarios passed using genuine public books and explicitly hypothetical paper holdings. They cover purchases, trims, three-step rotations, CAD exits, venue dust and insufficient depth. Fees reconcile to the execution engine; holdings never overdraw. These are numerical solver checks, not a positive recommended-SHIFT browser journey.

Intermediate browser evidence: `release-evidence/strategy-local-intermediate.json`. Migration evidence: `security-evidence/strategy-migration.txt`.
Owner isolation and solver evidence: `security-evidence/strategy-owner-isolation.json`, `security-evidence/strategy-solver-audit.json`, and [STRATEGY-STEP-REVIEW.md](STRATEGY-STEP-REVIEW.md).

## Final local acceptance

Backend corrections are complete and independently reviewed. Unfinished steps retain their reviewed target until the next scheduled review, then expire without being marked complete. Completed unchanged targets preserve units. Fresh quotes size from current books. The cumulative archive retains its original dates/configuration across refreshes. Four ordinary/daylight-saving midnight cases passed both implementation and independent reviewer checks.

Final local browser rerun passed10/10 with zero console errors. The isolated production build and postbuild TypeScript passed; all83 source/config files matched the working source used for QA. The146-file client bundle scan found zero matches for three configured WPR credential values and the previously exposed legacy key value. Final source screenshots passed measured and visual review. One public-history acquisition returned503; a bounded retry succeeded against the real source without code or data substitution. This external dependency can fail visibly rather than producing fabricated results.

Final local evidence: `release-evidence/strategy-local-final.json`, `strategy-local-build.json`, and `strategy-local-build-scan.json`.

## Verified Preview release — October 13, 2026 at 10:40 Eastern

Deployed reviewed commit `559ea6b4b26681798d8ddda71e2f04cfed67227b` from a clean detached worktree to artifact `dpl_6a3g9tmBbQxdCgxgjUwnhjdmY5vH`, READY Preview:

https://wolf-pack-5fe1is84l-danman60s-projects.vercel.app/rotation

Vercel deployment protection remains enabled; the owner signs in to Vercel. No automation bypass is shared. The exact deployed workflow passed10/10 with zero console errors, including real-data study/adoption, HOLD recording, stale reuse rejection, namespace separation, reload and export. Authenticated session/readiness/portfolio/strategy endpoints returned200 with operational workshop auth/database. Desktop and phone passed measured and visual review; the reviewed deployed desktop was delivered through `shot-approve`.

The actual Preview scan read144 referenced JavaScript files with zero unread assets and zero exact matches for the configured WPR credentials or known legacy key value. Scoped security headers passed. Evidence: `release-evidence/strategy-preview-deployment.json`, `strategy-preview-qa.json`, and `strategy-preview-scan.json`. Production and environment settings were unchanged. This Preview does not revoke or repair the older exposed production artifact.

## Release boundaries

The separate legacy browser-key exposure remains unresolved. This feature does not retry the previously blocked credential/environment/backend mitigation. New deployment is restricted to the existing Preview environment, with bundle inspection before a release claim; Production is not promoted as part of this correction.

All current historical data was previously exposed. These are retrospective comparisons and disclosed engineering gates, not an untouched test, calibrated forecast or guarantee of returns. A real-data HOLD journey does not establish that a positive recommended-SHIFT path was exercised. Manual pair execution coverage is reported separately.
