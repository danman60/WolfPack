# Rotation bootstrap verification

October 12, 2026 Eastern. Local implementation acceptance; deployment checks will be appended after the authorized release. No live funding or exchange order was attempted.

## Real browser and server evidence

Deterministic QA used the existing QA Agent `WebExecutor`, with no LLM inference, at explicitly supplied `http://127.0.0.1:3218/rotation`. Paper inputs were disposable QA scenarios, not owner portfolio preferences.

**9/9 full-workflow checks passed** in `/tmp/wolfpack-rotation-qa-local-5/checks.json`:

- Anonymous portfolio read refused; real one-click demo session created an isolated workshop identity.
- Explicit opening CAD 10000, zero crypto, fee 20 bps and weekly cadence persisted on the server with identical initial HOLD.
- CAD 1000→BTC preview left balances unchanged; approval wrote exact preview economics once. Actual spending was CAD 999.99945189, with rounding residual retained.
- HOLD changed no units/fees; browser reload recovered the server ledger.
- CAD 100 deposit increased both portfolios and net contributions by exactly CAD 100. Independent Decimal valuation at identical captured marks showed zero increase in P/L from the flow.
- Oversized withdrawal produced the real insufficient-CAD error and left ledger unchanged.
- Downloaded server export matched the actual portfolio and included trial/audit collections.
- Genuine-data research registered its protocol then persisted its evaluation; the actual report rendered, rather than an error fallback.
- The rotation browser made no legacy `/intel/` request.

Follow-up `/tmp/wolfpack-rotation-qa-final-inspection/inspection.json` passed: server portfolio revision 3 restored, database/auth readiness operational, 2 retained research records and 9 audit entries exported. Attempting to score the future holdout returned the explicit refusal "Forward holdout remains sealed through 2027-10-12" and appended no result. Full export and trial history were read from the authenticated API.

Research widths 1440, 390, 360 and 320 passed `documentElement.scrollWidth === clientWidth` after waiting for the chart's ResizeObserver to settle. The initial immediate-resize measurement was a test timing error, not a confirmed layout defect. Final console had only the expected HTTP 409 from the intentionally refused holdout; initial Recharts size warnings were corrected and did not recur in this run.

## Defects found and corrected by actual usage

1. Browser login failed because Next normalized `request.url` to localhost while the real Origin was 127.0.0.1. Backend verified matching-host requests succeed and attacker origins fail after validating the actual HTTP Host.
2. Approval failed because PostgreSQL JSONB reordered preview object keys. The saved/regenerated economic values were deeply equal but JSON strings were different. Exact deep economic comparison corrected the false rejection.
3. Measured table-header/nav contrast failed in the initial screenshot. Scoped colors were corrected; the final composed workspace passed measured checks at both widths.

The harness also corrected its own accessible-name and withdrawal-wording assumptions; those were test errors, not product defects.

## Visual evidence

Held final screenshots:

- `/home/danman60/.claude/shots/pending/wolfpack-rotation-final-assets-390-20261013T030546.png`
- `/home/danman60/.claude/shots/pending/wolfpack-rotation-final-assets-1440-20261013T030546.png`

Both `shot` reports passed overflow, clipping, contrast and image checks. Visual review found coherent WolfPack typography/palette, legible amounts, distinct primary actions and contained tables. Mobile holdings now use individual asset rows with readable exact units and weights; desktop retains its comparison table. No automatic screenshot delivery was performed.

## SEO and personal-workspace release scope

Existing SEO suite ran its 20-item checklist: **20/20 items checked**, 17 of 18 scripts executed successfully. `fetch_page` refused a private localhost address by its own safety policy; this is a tool limitation, not a broken page. Raw result: `/tmp/wolfpack-rotation-seo-local.json`.

The go-live punchlist result is `/tmp/wolfpack-rotation-golive-local.json`. Interpret its public-marketing assumptions explicitly:

- Deliberate noindex/nofollow is correct for this personal paper workspace.
- Customer terms/privacy policies, sitemap marketing discovery, Search Console, analytics and social-promotion imagery are not silently invented for a personal experimental product. `/rotation/about` supplies factual data/research/funding information. A public customer launch still needs appropriate governance and verified legal facts.
- Localhost HTTP cannot certify production HTTPS/HSTS. Re-run deployed transport/header checks after release.
- Static SSR audit did not see client-rendered sign-in controls; real browser actions verified those controls.
- Source scan flagged existing `NEXT_PUBLIC_INTEL_API_KEY` references and an empty example value. This is not evidence of a newly leaked secret; the source reference alone cannot establish the value or its privileges.
- Initial favicon absence was corrected with the route's branded icon. Existing app-wide default 404 remains separate from tested rotation errors.

## Secret and security evidence

The mechanical punchlist scanned 37 first-party browser bundles without finding privileged-key patterns. A separate exact-value scan checked 487 local browser JavaScript files against the three configured WPR key/password values and found zero matches. Secret values were never written to this report. Evidence: `/tmp/wolfpack-rotation-secret-scan-local.json`.

These are bounded checks, not a claim that a full security audit passed. Backend ownership/CAS/RLS probes, scoped headers, real auth/origin checks, bounded JSON input and durable rate limits are separately reviewed. The isolated production build exact-value scan checked 146 browser JavaScript files against three server secret values and found zero matches (`/tmp/wolfpack-rotation-secret-scan-build.json`).

## Pending release evidence

Source freeze, isolated `npm run build` and post-build `npx tsc --noEmit --incremental false` passed. Build log: `/tmp/wolfpack-rotation-release-build.log`; typecheck: `/tmp/wolfpack-rotation-final-tsc.txt`. Legacy-route prerender retained the existing Reown `projectId=demo` HTTP 403 warning; rotation browser did not initialize that provider. Deployed URL, deployment-host workshop reachability and safe deployed verification remain to be recorded. Forecast status remains unvalidated; funding, private exchange authorization and live execution remain outside this paper verification.
