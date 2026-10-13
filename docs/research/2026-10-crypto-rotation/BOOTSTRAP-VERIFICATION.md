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

Both `shot` reports passed overflow, clipping, contrast and image checks. Visual review found coherent WolfPack typography/palette, legible amounts, distinct primary actions and contained tables. Mobile holdings now use individual asset rows with readable exact units and weights; desktop retains its comparison table. No automatic screenshot delivery was performed. Research uses matching mobile cards for outcomes, chronological folds and saved trials; composed final research screenshots are `/tmp/wolfpack-rotation-qa-research-cards/research-390.png` and `research-1440.png`.

## SEO and personal-workspace release scope

Existing SEO suite ran its 20-item checklist: **20/20 items checked**, 17 of 18 scripts executed successfully. `fetch_page` refused a private localhost address by its own safety policy; this is a tool limitation, not a broken page. Raw result: `/tmp/wolfpack-rotation-seo-local.json`.

The go-live punchlist result is `/tmp/wolfpack-rotation-golive-local.json`. Interpret its public-marketing assumptions explicitly:

- Deliberate noindex/nofollow is correct for this personal paper workspace.
- Customer terms/privacy policies, sitemap marketing discovery, Search Console, analytics and social-promotion imagery are not silently invented for a personal experimental product. `/rotation/about` supplies factual data/research/funding information. A public customer launch still needs appropriate governance and verified legal facts.
- Localhost HTTP cannot certify production HTTPS/HSTS. Re-run deployed transport/header checks after release.
- Static SSR audit did not see client-rendered sign-in controls; real browser actions verified those controls.
- The initial source-name flag for `NEXT_PUBLIC_INTEL_API_KEY` was subsequently investigated against actual Production configuration and bundles: a nonempty configured value is publicly exposed. See the definitive legacy-key finding below.
- Initial favicon absence was corrected with the route's branded icon. Existing app-wide default 404 remains separate from tested rotation errors.

## Secret and security evidence

The mechanical punchlist scanned 37 first-party browser bundles without finding privileged-key patterns. A separate exact-value scan checked 487 local browser JavaScript files against the three configured WPR key/password values and found zero matches. Secret values were never written to this report. Evidence: `/tmp/wolfpack-rotation-secret-scan-local.json`.

These are bounded checks, not a claim that a full security audit passed. Backend ownership/CAS/RLS probes, scoped headers, real auth/origin checks, bounded JSON input and durable rate limits are separately reviewed. The isolated production build exact-value scan checked 146 browser JavaScript files against three server secret values and found zero matches (`/tmp/wolfpack-rotation-secret-scan-build.json`).

## Release evidence

Source commit `9e7b566c7c9843d4ccdd18b6cf67cf94a137856a` passed isolated `npm run build` and post-build `npx tsc --noEmit --incremental false`. Build log: `/tmp/wolfpack-rotation-release-build-final.log`; typecheck: `/tmp/wolfpack-rotation-final-tsc.txt`. Local legacy-route prerender retained the existing Reown `projectId=demo` HTTP 403 warning; rotation browser did not initialize that provider.

True Preview `wolf-pack-n8aij5nb4-danman60s-projects.vercel.app` / `dpl_BCzx3sFkbNRqxsM1sD5ovVkBkPa3` passed 9/9 full-workflow checks and 5/5 separate BTC→ETH→LINK→CAD checks. Five additional real-book legs charged CAD 1.16861770, preserved HOLD, reconciled exact quote/event IDs and survived reload. Genuine research results persisted, not a fallback screen. Vercel-hosted authenticated readiness proved workshop DB/auth operational.

The CLI `vercel promote --yes` rebuilt that Preview in Production, producing `dpl_422mzLkVN5MR3aQQMG2sn6LLJjyu` at `https://wolf-pack-eight.vercel.app/rotation`. It did not assign the exact Preview binary to the production alias. This deviation was established from installed CLI source and live deployment lineage. The cancellation attempt arrived after the build completed; no rollback or further deployment mutation followed.

Separate production read-only checks passed: pages/session/readiness/portfolio/trials returned 200; authenticated ledger exactly matched preview revision 3; two research records remained; real public CAD books returned 200. Production headers included HSTS, DENY, nosniff and scoped CSP; APIs were no-store. Production actual JavaScript discovery scanned 116 files against three configured server-secret values, with zero matches. Production 390/1440 screenshots passed measured checks and root visual review. No write harness ran against stable Production.

Durable sanitized JSON evidence is in `release-evidence/`. Cookies, Vercel automation secrets and credentials are omitted. This is bounded workshop acceptance, not a full public-customer security/governance certification.

Approved delivered preview screenshots are in `~/.claude/shots/sent/`: `wolfpack-rotation-preview-workspace-390-20261013T032133.png`, `wolfpack-rotation-preview-workspace-1440-20261013T032133.png`, and `wolfpack-rotation-research-preview-1440-20261012T232322.png`. Research phone `wolfpack-rotation-research-preview-390-20261012T232324.png` remains held. Final Production screenshots `wolfpack-rotation-production-workspace-{390,1440}-20261013T033053.png` were reviewed; owner delivery is controlled separately by the screenshot approval ledger.

**Paper workflow only.** Provider selection, private read-only exchange connection and live execution remain unbuilt. Funding alone does not enable trading. Forecast status remains unvalidated; private authorization, funding and actual orders require separate completed work and owner decisions.

## Production SEO and go-live mechanical audits

The named SEO suite and go-live scripts were rerun read-only against the stable production URL after deployment. Durable complete outputs: `release-evidence/production-seo.json` and `production-golive.json`.

SEO: 18/18 script runners completed, all 20 checklist topics checked. This means measured, not all SEO recommendations satisfied. Mobile Lighthouse performance 97; LCP 2111 ms, CLS 0.039, TBT 144 ms, all rated good in this run.

Generic go-live punchlist: 11 pass,9 fail,1 review,3 generic launch-blocker flags. These findings remain visible rather than being relabeled green. The public-marketing assumptions flagged missing customer legal pages, OG image, robots/sitemap, analytics and a custom404. Personal paper-workspace scope deliberately avoids invented legal/company facts, trackers and search discovery; default404 remains an existing-app gap. The static HTML CTA/form findings miss the client-rendered real sign-in controls already exercised through browser QA. The legacy `NEXT_PUBLIC_INTEL_API_KEY` finding is now confirmed as an exposed configured credential, not a false positive. Actual production scan followed 116 JavaScript artifacts with zero values among the three configured WPR secrets; the generic punchlist separately scanned 24 bundles without privileged-key patterns. HTTPS redirects, HSTS, icon, metadata and mobile viewport passed.

Public-customer launch/legal/governance approval is not claimed. These audits did not modify the deployed application or submit any production form.

## Confirmed legacy production credential exposure

A final production-only check found one configured, nonempty `NEXT_PUBLIC_INTEL_API_KEY`. Its exact decoded value occurs once in actual Production JavaScript `/_next/static/chunks/80c371bd10693fad.js`. An independent anonymous GET returned200 with the same exact match, without cookies, Authorization or Vercel bypass headers. The previous Preview environment listing omitted this Production-only variable. The initial exact-match scan also used incorrect dotenv escape decoding; corrected decoding and independent retrieval resolved that method error.

`app/src/lib/intel.ts` forwards this credential as Bearer. The current backend source uses the shared `API_SECRET_KEY` equality check for38 protected handlers, including live execute/cancel and wallet-management actions. Whether the configured remote runtime accepts this exposed credential is unverified: HTTPhealth, SSH and independent TCP probes to its configured origin timed out. No credential was sent, and no protected mutation was called. A different local `.env` value cannot establish remote validity.

This security finding remains open. No legacy infrastructure, key, environment or wallet was changed during this bounded investigation. The WPR-only secret scans remain valid for their three explicitly named workshop values and do not negate this legacy exposure. Sanitized primary proof: `release-evidence/legacy-intel-key-exposure.json`. No secret values are included.
