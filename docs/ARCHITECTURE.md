# Rotation architecture

Status: integrated within the WolfPack monorepo. Real local browser/server acceptance and isolated production build passed; deployment evidence is tracked separately.

## Existing architecture preserved

`app/` is Next.js 16.1.6, React 19.1.0, TypeScript 5.9.3 and Tailwind 4.2.1 as installed for this build. `intel/` contains the existing Python FastAPI intelligence/trading service. Existing Supabase migration history and perp/LP wallet policies remain unchanged by the new spot domain.

The root layout supplies Geist fonts, providers and `Nav`. `/intel/*` rewrites to the legacy service. Rotation uses separate `/api/rotation/*` endpoints and does not import/start the Python application.

## Domain modules

| Path | Contract |
|---|---|
| `app/src/lib/rotation/contract.ts` | Four assets, decimal-string units, portfolio, market, approval, performance and research types |
| `app/src/lib/rotation/engine.ts` | Canonical fixed-precision accounting, immutable opening baseline, costed quotes, approval and flow validation |
| `app/src/lib/rotation/replay.ts` | Disclosed chronological historical rule comparison; no future-data model claims |
| `app/src/lib/rotation/server.ts` | Real GoTrue sessions, membership checks, origin/input/rate limits, scoped workshop access and transactional commits |
| `app/src/lib/rotation/validation.ts` | Experimental paired horizon outcomes and chronological fold evaluation |
| `app/src/lib/rotation/research-contract.ts` | Immutable protocol/trial records, source hashes and future holdout contract |
| `app/src/app/api/rotation/market/route.ts` | Genuine public CAD books and instrument rules |
| `app/src/app/api/rotation/history/route.ts` | Genuine completed historical observations with source/coverage |
| `app/src/app/rotation/` | Composed owner workspace and route-scoped design |
| `app/src/components/rotation/` | Existing-style metrics, holdings and activity presentation |

`/api/rotation/session`, `portfolio`, `preview`, `action` and `readiness` implement the authenticated account path; `/trials` implements the research registry. Export is `GET /api/rotation/portfolio?export=1`, containing portfolio, trials, consumed previews and audit. The initial browser persistence module was retired.

Workshop migrations `202610130001_rotation_workshop.sql`, `202610130002_rotation_owner_reads_audit.sql` `202610130003_rotation_transactional_audit.sql` and `202610130004_rotation_holdout_uniqueness.sql` define `wpr_schema_migrations`, `wpr_members`, `wpr_portfolios`, `wpr_previews`, `wpr_trials`, `wpr_rate_limits` and `wpr_audit`. SQL/source review shows ownership read policies, authenticated-read/service-write separation and invoker functions. Live enforcement is verified separately by backend integration probes and browser acceptance; table presence alone is not acceptance.

## Final data flow

Authenticated owner session → rotation API → scoped workshop portfolio/ledger transaction.

Public market data → validated snapshot → fixed-precision preview → exact owner approval → idempotent paper event → persisted balances and HOLD comparison.

Historical source → coverage validation → chronology/cost-aware experimental replay → explicitly limited research result.

The client never supplies trusted identity, fees already charged, arbitrary final balances or an executable preview without server validation. Secrets stay server-side. Failed persistence never becomes UI success. Concurrent approval uses database revision/uniqueness protection rather than browser-only locks.

## Accounting invariants

- Persist quantities/CAD as decimal strings; canonical arithmetic uses integer fixed precision.
- Initial units, starting value and opening event remain immutable.
- HOLD means unchanged units; CAD external flows are matched between actual and baseline.
- P/L equals current CAD value minus initial CAD value minus net contributions.
- Fees are charged once, per disclosed execution leg; residual CAD remains visible.
- Expired/revised/duplicate approvals cannot create unapproved spending.
- Append-only events and recoverable server state support export and audit.
- Opening paper crypto cost basis is disclosed as the initial midpoint, not tax acquisition history.

## Research contract and honest labels

The current experimental method uses joint historical horizon returns. A 365-day initial prefix precedes expanding 60-day evaluation folds. Every training outcome must finish before its review; the last 180 historical days are labeled already exposed, not untouched. Reports display historical shift/HOLD means, paired advantage, 10th/90th percentiles and measured interval coverage while retaining `status: unvalidated`.

Each real run persists an immutable protocol with source SHA-256 before evaluation. A future 12-calendar-month prospective evaluation is registered; server eligibility checks refuse scoring until all required future observations exist. Later protocols can expose overlapping data, so this is not guaranteed account-wide untouched evaluation. This design provides reproducible research, not proof of useful predictive performance or permission to trade.

## Hosting and dependency reachability

Existing project link is Vercel `wolf-pack`; live read-only inspection on this session returned production deployment `dpl_Fvw68FPVJs32XgLYd27ap2sucbzA`, READY, created August 28, 2026 at 09:54 Eastern, with alias `wolf-pack-eight.vercel.app`. This is evidence about the old deployment, not deployment of the new rotation code.

Owner selected the existing Netcup workshop tenant. Tailnet gateway is `http://100.89.183.64:8100`; existing public gateway is `https://djatb.fyi/sb/workshop`. Both unauthenticated `/auth/v1/health` probes returned the gateway's API-key-required response. Subsequent authenticated local readiness and real browser persistence verified workshop database/auth usability. The public route already exists; no new public Traefik router or tenant is needed or authorized.

Local developer workspace is `http://127.0.0.1:3218/rotation` on SPYBALLOON, which has tailnet access. Existing Tailscale Serve routes proxy unrelated services and must not be repointed. Preserve Vercel hosting; do not move app hosting onto Netcup. Before a later deployment, prove the chosen application host can authenticate to the selected workshop gateway and verify assigned domain/session configuration.

## Readiness boundaries

Readiness must test database usability, session/auth configuration, public market/history access and demo isolation. It must describe unvalidated forecasts and disabled live exchange execution honestly. Existing local compiler success does not prove DB ownership, browser persistence, deployed behavior or profitable predictions.

Deployment is authorized by the owner's later instruction, after build, QA and parent review. Real account creation, KYC, private exchange keys, deposits, withdrawals, orders, transfers and swaps remain outside this implementation authorization.
