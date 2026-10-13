# Rotation workshop database runbook

Scope: isolated CAD/BTC/ETH/LINK paper workspace. No exchange authentication or live-order endpoint exists in this integration. Existing `wp_*` wallets and other workshop applications remain outside this schema.

## Connection and migrations

Existing NETCUP workshop tenant, database `workshop`, gateway `https://djatb.fyi/sb/workshop`. Auth health200 was verified with the tenant anon key on 2026-10-13 Eastern. The same service is reachable over tailnet `100.89.183.64:8100`. No tenant, router or infrastructure was provisioned.

Server-only environment variables in ignored `app/.env.local` (mode600): `WPR_SUPABASE_URL`, `WPR_SUPABASE_ANON_KEY`, `WPR_SUPABASE_SERVICE_ROLE_KEY`, `WPR_DEMO_ENABLED`, `WPR_DEMO_EMAIL`, `WPR_DEMO_PASSWORD`. Seeded account credentials are never returned to the browser. Do not copy these variables into `NEXT_PUBLIC_*` or commit them. Existing application environment is separate.

Applied individually and transactionally:

1. `202610130001_rotation_workshop.sql`: membership, portfolio, preview, research trial, rate-limit and migration tables; owner-read policies; server-only CAS/rate-limit functions.
2. `202610130002_rotation_owner_reads_audit.sql`: JWT owner-read previews and append-only audit table.
3. `202610130003_rotation_transactional_audit.sql`: portfolio writes insert actor/revision/event audit in the same transaction.
4. `202610130004_rotation_holdout_uniqueness.sql`: unique first holdout per owner/protocol.
5. `202610130005_rotation_strategy_plan.sql`: separate adopted-plan revision, service-only adoption/guarded decision RPCs, and transactional recommendation provenance audit. Applied after schema/grant review; readback in `security-evidence/strategy-migration.txt`.

Read actual migration state from `public.wpr_schema_migrations` before applying anything. These files are forward-only migrations, not rerunnable setup scripts. Each notifies PostgREST to reload its schema.

For an approved future SQL migration, SSH to NETCUP and use `workshop_owner` with its host-only password over `-h db.internal`, passing SQL on stdin. The owner credentials live in `/opt/netcup/stack/projects/workshop/.env`. Do not log passwords or put them in shell history. `postgres` lacks CONNECT to workshop; local socket auth for `workshop_owner` is peer-authenticated. Both are intentional boundaries. `workshop_owner` also lacks auth-schema access: `wpr_members.user_id` is a GoTrue UUID checked through `/auth/v1/user`, not a cross-schema FK. Owner RLS compares signed PostgREST `request.jwt.claims.sub`; it does not depend on inaccessible `auth.uid()`.

## Authentication and isolation

Real GoTrue password authentication establishes HttpOnly, SameSite=Strict cookies scoped to `/api/rotation`. Cookies are Secure in production. Access tokens are verified with GoTrue on every private request; expired access can refresh using the HttpOnly refresh cookie. Membership is separately required because workshop hosts other applications. There is no public registration, recovery-email workflow or access to another app's workshop account just because it has a valid JWT.

The public demo action creates a fresh synthetic GoTrue identity and membership for a new browser; an existing signed-in session resumes. Different demo visitors have different owner IDs and portfolios. Provisioning is bounded by durable DB counters:3 per IP per hour and50 total per day; ordinary sign-in rate15/IP/minute. These are technical abuse limits, not a product pricing policy. The seeded demo and isolation identities are for controlled verification only. Signing out revokes the current GoTrue session and clears cookies. Public demo users have no emailed password recovery; they must export before abandoning their browser session. Never enter exchange credentials or real customer data.

Portfolio, trial, preview and audit reads use the requesting user's JWT and owner RLS. Browser roles cannot write financial JSON or invoke the commit RPC. The trusted Next server validates real public books and engine accounting before service-role writes, with the authenticated owner ID supplied by verified session, never by request body. This service-role boundary prevents clients from minting balances by calling PostgREST directly.

## Atomic ledger behavior

One portfolio per owner. Opening units and settings are immutable. Every mutation carries `expectedRevision`; `wpr_commit_portfolio` locks that owner's row and requires exactly one next event and revision. Historical event prefix cannot change. Approval consumes the stored preview in the same transaction. Concurrent duplicates and stale tabs return409. The browser submits only a preview ID; the server reconstructs engine inputs from its own stored snapshot and compares economics before approval. Expired books are rejected, not silently refreshed under an old approval.

`wpr_audit` records sign-in, sign-out, exports and transactional portfolio actions. Research trials are immutable application records; holdout uniqueness is enforced in PostgreSQL. Service keys are privileged across workshop: only these scoped route handlers may use this module. Future code must preserve the table-prefix guard and verified owner checks.

## Operational checks

- `GET /api/rotation/readiness` while signed in: real migration and auth-health checks; explicit paper/live and recovery limitations.
- `GET /api/rotation/portfolio`: owner-scoped ledger from database, never localStorage.
- `GET /api/rotation/portfolio?export=1`: JSON attachment containing portfolio, research trials, consumed quote snapshots/legs and actor audit.
- Read `pg_tables.relrowsecurity`, `pg_policies`, table grants and `pg_proc.prosecdef` for every `wpr_*` object after migrations. RLS boolean alone does not prove owner isolation.
- Do not reset a demo portfolio to make a test pass. Use the separate disposable synthetic QA account and preserve its ledger as evidence.

## Incident and recovery boundaries

Disable new demo provisioning by setting `WPR_DEMO_ENABLED=false` and redeploying. This does not revoke existing sessions; use GoTrue session revocation for the affected account if needed. A membership removal prevents subsequent app access, but is a separately authorized administrative action. Do not delete old wallets or unrelated auth users.

NETCUP platform backup jobs are documented in DEVOPS. This task has not rehearsed a rotation-specific restore; the readiness response reports that limit. For suspected ledger corruption, keep the original row and append evidence; do not replace it with browser data. Restrict the affected workspace, export the current row/audit through an approved administrator, and follow the NETCUP restore procedure into a separate recovery target before any replacement. Actual restore and security-key rotation require their own explicit scope.

No live funding, exchange keys, custody choice, risk limits, legal entity or consumer password-recovery service has been approved by this paper integration. Those remain separate gates before real-money use.

## Adopted paper strategy

Strategy protocol/development records reuse `wpr_trials` with namespace/version tags. Existing research restores only unnamespaced records; exports retain both. Adoption changes only active plan and plan revision, never financial units/revision. Current recommendations bind owner, plan/portfolio revisions, holdings hash, archived source and evaluator fingerprint. Public history appends to the latest verified cumulative adopted archive while keeping its original calendar anchor and configuration.

A recommendation lasts at most fifteen minutes; a quote lasts at most thirty seconds. Quote sizing uses current full public books, sells off-target assets first, then solves the post-fee target allocation with fixed-point accounting. Maximum three individually approved shifts. Venue dust remains owned; depth failures block. Quote consumption and recommended HOLD append immutable decision audit in the financial transaction. A completed unchanged target retains units and natural drift. An unfinished target can continue only until the next scheduled Eastern review; recommendation expiry is capped there and checked atomically by SQL. Expired partial targets are superseded without pretending completion. Manual actions invalidate stale revisions; subsequent steps use actual current balances and the still-valid frozen target.

Verification artifacts separate real owner-isolation/HOLD browser paths from hypothetical CPU sizing against genuine public books. A favorable SHIFT recommendation has not been manufactured or persisted for a test.
