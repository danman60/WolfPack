# WolfPack rotation bootstrap rebaseline

Existing Project mode. Full Astra implementation; no local model dispatch or inference. This plan supersedes browser-local storage and broker instructions in `2026-10-12-rotation-paper-build.md`.

## Purpose

This exists so that "I'm looking to trade crypto; i just want to know when to shift positions between CAD/BTC/ETH/LINK any pairing in/out looking to only make weekly or monthly trades".

## Authoritative requirement sources

1. Owner handoff `/tmp/crypto-rotation-astra-20261012-214732.md`: complete four-asset purpose, prediction, owner-click execution, P/L, identical-start no-action benchmark, Ontario/CAD constraints and no live financial authorization.
2. Owner "Keep building the trading bot/app": implementation authorized.
3. Owner "No locals full astra": supersedes all prior broker/leaf/local-QA instructions for this work.
4. Owner request to complete according to bootstrap with Netcup workshop: supersedes browser-local ledger as final storage; existing-project extension, authenticated server-owned data and readiness required.
5. Owner "You can deploy I'll mind the funding gate": deployment authorized after concrete build, QA and review. Funding, private exchange credentials and live orders remain a distinct owner gate.

No new interview or scaffold is required. The handoff is the requirements input; unanswered financial preferences stay explicit forms/research constraints.

## Current architecture inventory

Read-only snapshot during integration, October 12 Eastern:

- HEAD `60cccd72cb5ed623ab37bb9d25d457fa1b3cb871`; `main` is one commit ahead of `origin/main`.
- 9 existing routed pages; 2 new rotation API routes (`market`, `history`) at inventory time; rotation page/auth/server routes still being integrated.
- 15 existing SQL migration files, plus Python FastAPI `intel/` subsystem. Existing production wallet schema remains unresolved; new workshop integration uses a distinct namespace.
- Installed Next 16.1.6, React 19.1.0, TypeScript 5.9.3, Tailwind 4.2.1. npm lockfile matched manifest; `npm ci` installed 868 packages without changing either.
- Baseline `npx tsc --noEmit` passed before new files were integrated; output `/tmp/wolfpack-rotation-baseline-tsc.txt`.
- Live new dev server: 127.0.0.1:3218, owned exec session30368; no pre-existing process restarted. Static design server: 127.0.0.1:3328.
- Graph rebuilt by local CPU AST tooling. `Nav()` impact: root layout import; existing root providers preserved.
- Vercel linked project `wolf-pack`; production alias `wolf-pack-eight.vercel.app`; inspected deployment `dpl_Fvw68FPVJs32XgLYd27ap2sucbzA` READY, created August 28 at 09:54 Eastern. This does not establish the new code is deployed.
- Workshop has both tailnet gateway `100.89.183.64:8100` and an existing public gateway `https://djatb.fyi/sb/workshop`; live unauthenticated health requests returned matching API-key-required responses. Authenticated host-to-DB proof remains a deployment acceptance check.
- Pre-existing dirty research, transcript, CURRENT_WORK and INBOX content preserved. Stage by explicit paths only.

## Requirement coverage matrix

Statuses updated from real local browser/server acceptance and isolated production build. Deployment evidence follows after preview verification.

| ID | Requirement | Status | Primary evidence and remaining acceptance |
|---|---|---|---|
| R1 | Exactly CAD/BTC/ETH/LINK spot | Paper verified | Exact contract keys and four-asset composed workspace |
| R2 | Weekly/monthly review and real HOLD | Paper verified | Explicit cadence saved; HOLD preserved all units and fees in real browser/server path |
| R3 | Any pair in/out via simple clicks | Paper implemented | Canonical CAD-mediated pair engine; CAD→BTC browser preview/approval passed; live execution not connected |
| R4 | CAD value and realized/unrealized P/L after costs | Paper verified | Independent decimal valuation and exact quote/charged-fee assertions passed |
| R5 | Permanent identical-start no-action comparison | Paper verified | Opening/baseline unchanged after approved shift; flows matched |
| R6 | Deposits/withdrawals separated from performance | Paper verified | CAD100 matched deposit added no P/L; oversized withdrawal refused without ledger change |
| R7 | Predictive ranking/allocation | Experimental | Disclosed momentum ranking; validated predictive value and owner risk limits remain open |
| R8 | Forward shift/HOLD outcomes, horizon and loss calibration | Experimental | Joint historical means, paired advantage and p10/p90 rendered; observed fold coverage is diagnostic, not calibrated confidence |
| R9 | Genuine backtests, costs, no leakage, fair HOLD | Research implemented | Genuine719day data, chronological report and frozen registry saved; causal-prefix checks documented separately |
| R10 | Walk-forward, untouched period, regime/trial discipline | Partial |365day prefix/60day folds and immutable records verified; last180days already exposed. Future12month scoring sealed per protocol, but other trials can expose overlapping data; no account-wide untouched-test claim |
| R11 | Ontario/CAD access and custody choice | Partial | Public CAD books genuine; provider/account-specific fees and custody remain owner choices |
| R12 | Wallets/account-backed management | Paper verified | Real isolated workshop identity and server ledger; no funded/private exchange account connected |
| R13 | Durable server persistence and ownership | Verified locally | Real GoTrue/RLS/CAS probes plus browser reload; deployment-host proof pending |
| R14 | Export and decision audit | Verified locally | Real downloaded portfolio/trials/audit/consumed-quote export; final fresh-preview audit-ID assertion included |
| R15 | Existing app extension and old-wallet isolation | Verified bounded scope | Separate rotation domain, original providers retained elsewhere; rotation browser made no legacy intel calls; no old trading logic edits |
| R16 | Complete reviewed application, authorized deploy | Local acceptance passed | Real9-check flow, responsive measurements, build and TypeScript passed; immutable preview and production smoke pending |

## Conflicts and superseded requirements

- Browser-local storage was the initial implementation slice. Owner now requires Netcup workshop; localStorage is not the final ledger or cross-device persistence proof.
- Broker dispatch and local QA inference were initial standing policy. Owner explicitly chose full Astra; CPU tools remain allowed, local model inference does not.
- Initial handoff withheld deployment. Owner later explicitly authorized deployment, while retaining funding/live-order control.
- Bootstrap describes workshop as tailnet-only. Current sysadmin documentation and live gateway response establish an existing public workshop gateway. Reuse that route if deploying to Vercel; do not create a new public router, tenant or hidden DB substitution.
- Experimental momentum research does not equal a calibrated predictive investment system. Keep R7/R8/R10 incomplete until evidence closes them; attractive charts cannot close these rows.
- Current implemented research proposal: joint empirical horizon outcomes, 365-day initial prefix, expanding 60-day folds, completed labels strictly before each review, final 180 historical days explicitly already exposed, and a future 12-calendar-month registered prospective evaluation. Show p10/p90 and observed coverage as historical diagnostics, always unvalidated until promotion evidence exists.

## Reusable implementation surfaces

Reuse root layout, Geist typography, global WolfPack tokens/cards and the rotation MetricCard exemplar. Preserve original exchange/wallet providers for old routes. Extend `Nav` to add Rotation and stop legacy status polling only there.

Reuse new rotation contracts and engine across server routes; no duplicate client financial implementation. Existing Kraken/futures adapter, old approval routes and WolfHunt synthetic history remain unsuitable for CAD spot execution as documented in REUSE-EVIDENCE.

## Production-readiness gaps

1. Prove scoped real session/demo access, server identity checks, request-origin checks, rate limits, input limits and cross-owner rejection. Never rely on a client-hidden control.
2. Verify actual workshop schema/RLS, writers, transaction/revision/idempotency behavior and migration tracking; apply no unrelated migration.
3. Readiness must query usable DB/public-data dependencies and report research/live-trading limitations honestly. Configuration presence alone is not usability.
4. Export the server-owned record and prove reauthentication/reload recovers it. Demo data cannot leak into owner portfolios.
5. Privacy/terms are not fabricated. This is a personal experimental workspace with no customer billing or claimed public legal policy; no invented entity, address or refund product.
6. Password recovery is required if the final access model exposes normal password accounts. Verify the actual selected auth flow before asserting a reset workflow works.
7. Validate final composed UI, measured mobile overflow, console/network errors and intended navigation. Mock screenshots do not close final UI acceptance.
8. Build/tsc, source review, actual deployed route, actual deployment-host DB reachability and production safe-path checks must pass before calling the deployment operational.
9. Backups/restore and incident handling remain operational facts to verify; a workshop database row alone is not a rehearsed restore.

## Work packages

All implementation is Astra per owner override. No broker/model allocation applies.

1. **Domain and public data** — R1–R6/R9: `contract.ts`, `engine.ts`, `replay.ts`, market/history API routes. Acceptance: owner supplies amounts; live public quote produces costed shift; one approval conserves inventory and preserves HOLD; genuine history generates disclosed comparison without synthetic fallback.
2. **Workshop authentication and persistence** — R12–R14: backend-owned rotation server/auth/storage modules, scoped API routes and one explicitly numbered workshop migration. Acceptance: fresh session signs in; creates isolated paper account; another user cannot read it; approved action persists once; reload/export read same server data. Record actual files/schema from completed integration.
3. **Composed application** — R1–R6/R14–R16: `app/src/app/rotation/page.tsx`, `rotation.css`, `components/rotation/*`, `components/Nav.tsx`. Acceptance: sign-in → explicit setup → genuine quote → preview → approve/HOLD → cash flow → export → research at desktop/mobile; no legacy `/intel` calls.
4. **Documentation/readiness** — all rows: `docs/PRD.md`, `DESIGN.md`, `ARCHITECTURE.md`, this matrix and `CURRENT_WORK.md`; readiness surface in backend package. Acceptance: every claimed completed feature names a read artifact; incomplete forecasts/live actions remain explicit.
5. **Deterministic QA/build/review** — R4–R6/R13–R16: `tests/agent/flow-rotation-paper.md`, `rotation-paper-qa.py`, CPU build/compiler reports. Existing QA Agent WebExecutor only, no model calls. Acceptance: real browser actions with independent server-state oracle, exact money/flow checks, duplicate protection, source failures, fresh-session isolation, export content, mobile metrics, screenshots reviewed by parent.
6. **Authorized deployment** — R16: existing Vercel project, exact server-only workshop env values and existing gateway. Acceptance: parent approves completed code/visual review; build/QA pass; deploy; read deployed app and authenticated readiness/DB result; safe read-only production verification. No test funding or live orders.

## Owner-blocked

- Actual custody/provider/account, real capital/acquisition history, loss tolerance/reserve/allocation limits and review timing. Paper/research inputs do not resolve these choices.
- Funding and live execution remain explicitly owner-controlled. No exchange credential creation/import or financial action follows from deployment authorization.
- Model promotion thresholds and final evaluation protocol need owner agreement before a claim of validated predictive value.
- New commercial legal/billing/email identities are not needed for the current personal paper workflow and must not be invented.

## Preserve / Do Not Touch

Existing perp/LP wallets, trading policies, Python service startup, applied migration history, old integration contracts, other tenant data, running user processes, existing Tailscale Serve/Traefik routes and unrelated dirty-tree files. Root/deploy project link stays intact. No re-scaffold, new Supabase project, new Netcup tenant or broad staging.

## Continue vs rebuild

**Extend the existing app.** Existing Next shell, token vocabulary, exchange integration context and reusable accounting/research concepts support this workflow. None of the inspected evidence justifies a rewrite. The new spot domain is isolated because the owner requested different asset/account behavior; existing futures behavior remains intact.

## Verification ledger

- PASS: manifest/lock consistency, npm dependency installation, baseline TypeScript.
- PASS: mock 390/1440 mechanical checks and visual review; screenshots held.
- PASS: existing Vercel deployment and both workshop gateway responses read without mutation.
- PASS: integrated application production build/TypeScript, real browser money/research workflow, authenticated server reload/export, final 320–1440px overflow checks. Evidence: `docs/research/2026-10-crypto-rotation/BOOTSTRAP-VERIFICATION.md`.
- PENDING: immutable preview release/browser QA, promotion and read-only production smoke.
