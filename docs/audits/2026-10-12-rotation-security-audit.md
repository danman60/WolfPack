# Rotation security audit — scoped paper workshop

Snapshot: 2026-10-12T23:08:12-04:00 Eastern. Counts: {'N/A': 42, 'UNVERIFIED': 27, 'FAIL': 21, 'PASS': 17}.

This audits the working tree based on git `60cccd72cb5ed623ab37bb9d25d457fa1b3cb871`, localhost `127.0.0.1:3218`, and the live NETCUP workshop `wpr_*` schema. It does **not** certify a deployed production rotation release. Existing old-wallet routes and other workshop applications are outside this audit. Audit collection is read-only. Separately requested fixes now include a protected route base, safe error boundary, scoped headers, and consumed-quote audit linkage; this matrix records the checked source/runtime after those fixes.

13 authenticated API probes,6 direct auth/RLS probes and7 approval probes passed;4 follow-up checks prove preview/event ID linkage, consumed quote export, typed validation correlation and protected-route rejection (30 checks total). Two concurrent approval requests committed exactly once (200/409); client-supplied balance/fee forgery fields were ignored; fees matched the server preview once. Database catalog proves7 RLS-enabled tables, owner-read policies, no anon access and no authenticated mutation/function-execute grants. These are positive narrow findings, not a declaration that107 controls pass.

Full git-history Gitleaks scan completed with0 findings using redaction. Environment file is ignored. Neither finding proves the production client bundle or CI secret gate; those remain separately scoped controls.

The strict checklist reports expected research-workshop gaps as FAIL, including consumer terms/privacy/retention/deletion, absolute session lifecycle, privileged runtime writer authority, complete operational telemetry and merge gates. The UI explicitly describes personal paper research and prohibits exchange secrets or real customer data. Live funding remains gated.

## Critical/high failures

- **FC-POLICY-01 (high)**: About page explicitly says public customer terms remain future work; it is not published customer terms with legal entity, law and liability cap. Evidence: `app/src/app/rotation/about/page.tsx; filesystem page inventory found0 terms/privacy/security pages`.
- **FC-POLICY-06 (high)**: Consumer retention policy explicitly remains unestablished; pervisitor synthetic identities and rows currently have no defined expiry schedule. Evidence: `docs/operations/rotation-workshop.md; app/src/app/rotation/about/page.tsx`.
- **FC-PRIV-01 (high)**: Data note discloses workshop storage, but a complete published privacy policy is not supplied. Must resolve actual entity/contact/retention facts before customer use. Evidence: `GET /legal/privacy returned404; filesystem policy/recovery page inventory[]; app/src/app/rotation/about/page.tsx`.
- **FC-PRIV-03 (high)**: Ledger/trial/audit export works, but it is not a complete personal-data export of GoTrue identity/session/provider records. Evidence: `app/src/app/api/rotation/portfolio/route.ts:8; security-evidence/server-verification.json`.
- **FC-PRIV-04 (critical)**: Account lifecycle and deletion across GoTrue, primary data, backups and logs are explicitly not implemented for consumer use. Evidence: `docs/operations/rotation-workshop.md Incident and recovery; app/src/app/rotation/about/page.tsx Your records`.
- **FC-PRIV-05 (high)**: Schema has no deletion/expiry lifecycle columns or scheduled purge writer; immutable paper data currently persists indefinitely. Evidence: `supabase/migrations/202610130001_rotation_workshop.sql; docs/operations/rotation-workshop.md`.
- **FC-TENANT-02 (critical)**: Reads use userJWT and RLS, but trusted request mutations use the workshop-wide service key. This deliberately prevents direct PostgREST financial minting but fails the strict background-only-admin-key control; narrower writer authority is required before sensitive/customer data. Evidence: `app/src/lib/rotation/server.ts:54,163; app/src/app/api/rotation/trials/route.ts:112`.
- **FC-AUTH-06 (high)**: One-hour access and seven-day renewable refresh cookies plus local logout exist; no absolute/idle session policy or user session-list/all-session revoke surface proven. Evidence: `app/src/lib/rotation/server.ts:73,80,139; GoTrue container GOTRUE_JWT_EXP=3600`.
- **FC-PAY-07 (high)**: Internal database/auth mutations use bearer authentication over TLS, not per-body HMAC. No claim of this stricter service-to-service control. Evidence: `app/src/lib/rotation/server.ts:54,69`.
- **FC-AUDIT-01 (critical)**: Append-only actor/time/action/revision trail works and transactional mutation audit is proven, but source-address fields and defined retention are not implemented. Evidence: `supabase/migrations/202610130002_rotation_owner_reads_audit.sql; security-evidence/server-verification.json`.
- **FC-AUDIT-04 (high)**: Operational containment/recovery note exists; no complete severity/oncall/customer-notification/breach-clock runbook with owner-confirmed contacts. Evidence: `docs/operations/rotation-workshop.md Incident and recovery boundaries`.
- **FC-OBS-10 (high)**: Outbound15s timeouts are explicit; there is no per-dependency circuit breaker or aggregate request budget. PostgREST/host pool sizing was not changed or validated here. Evidence: `app/src/lib/rotation/server.ts:57,71; docs/operations/rotation-workshop.md`.
- **FC-EDGE-02 (high)**: An enforced partial CSP now limits frame ancestors, objects, base URI and form actions. It does not restrict script sources, so the strict script-allowlist control remains FAIL. Production header verification remains separate. Evidence: `security-evidence/local-headers-updated.txt; app/next.config.ts`.
- **FC-TEST-01 (high)**: Default branch permits direct pushes. Repository rule change requires explicit owner workflow decision. Evidence: `gh api repos/danman60/wolfpack/branches/main/protection returned404 Branch not protected`.
- **FC-TEST-02 (high)**: No repository CI workflow exists to enforce the specified test/lint/build/security gates. Local checks are not merge protection. Evidence: `rg --files .github returned directory absent; pathlib .github/workflows.exists() false`.
- **FC-TEST-04 (high)**: QA uses explicitly scoped disposable identities in real workshop, preserving evidence. It does not recreate an empty isolated database perCI run. Evidence: `tests/agent/rotation-paper-qa.py; docs/operations/rotation-workshop.md`.
- **FC-TEST-07 (high)**: Additive migrations applied transactionally and recorded; no migration rehearsal on a production copy or rollback script was part of this paper-workshop change. Evidence: `supabase/migrations/202610130001_rotation_workshop.sql through004; security-evidence/db-security.txt`.

## entity_legal

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-ENTITY-01 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Personal paper experiment has no sales, checkout or economic-nexus calculation. |
| FC-ENTITY-02 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No sale or tax collection; CAD deposits are simulated ledger entries. |
| FC-ENTITY-03 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Grep the signup path for a country/region allowlist or geo-IP check; attempt a signup from a disallowed region with a VPN or spoofed geo header and confirm refusal. If the product serves everywhere, confirm that is a recorded decision in config or docs, with the matching regional obligations (GDPR, AI disclosure) wired up. |

## policies_contracts

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-POLICY-01 | FAIL | app/src/app/rotation/about/page.tsx; filesystem page inventory found0 terms/privacy/security pages — About page explicitly says public customer terms remain future work; it is not published customer terms with legal entity, law and liability cap. |
| FC-POLICY-02 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No payment or refund flow in scoped rotation routes. |
| FC-POLICY-03 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No B2B or enterprise customer contract in this personal workshop scope. |
| FC-POLICY-04 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No PHI processed in rotation schema or forms. |
| FC-POLICY-05 | FAIL | app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Factual research/data note and internal runbook exist, but no public disclosure contact or complete security posture page. |
| FC-POLICY-06 | FAIL | docs/operations/rotation-workshop.md; app/src/app/rotation/about/page.tsx — Consumer retention policy explicitly remains unestablished; pervisitor synthetic identities and rows currently have no defined expiry schedule. |
| FC-POLICY-07 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Private first-party UI API, not a published third-party integration API. |

## privacy_compliance

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-PRIV-01 | FAIL | GET /legal/privacy returned404; filesystem policy/recovery page inventory[]; app/src/app/rotation/about/page.tsx — Data note discloses workshop storage, but a complete published privacy policy is not supplied. Must resolve actual entity/contact/retention facts before customer use. |
| FC-PRIV-02 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No analytics/ad/model provider receives rotation user data in the scoped routes; market fetches request public books only. |
| FC-PRIV-03 | FAIL | app/src/app/api/rotation/portfolio/route.ts:8; security-evidence/server-verification.json — Ledger/trial/audit export works, but it is not a complete personal-data export of GoTrue identity/session/provider records. |
| FC-PRIV-04 | FAIL | docs/operations/rotation-workshop.md Incident and recovery; app/src/app/rotation/about/page.tsx Your records — Account lifecycle and deletion across GoTrue, primary data, backups and logs are explicitly not implemented for consumer use. |
| FC-PRIV-05 | FAIL | supabase/migrations/202610130001_rotation_workshop.sql; docs/operations/rotation-workshop.md — Schema has no deletion/expiry lifecycle columns or scheduled purge writer; immutable paper data currently persists indefinitely. |
| FC-PRIV-06 | PASS | app/src/lib/rotation/server.ts:100; app/src/app/api/rotation/portfolio/route.ts:7; security-evidence/rls-verification.json — UUID identifiers; session response excludes tokens; database reads scoped to authenticated owner. |
| FC-PRIV-07 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Research output is deterministic numerical replay, not model-generated prose. |

## tenant_isolation

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-TENANT-01 | PASS | security-evidence/db-security.txt; security-evidence/rls-verification.json — All7 wpr tables have RLS. Anon has no table access. Authenticated owners SELECT only; no INSERT/UPDATE/DELETE or RPC execute. Owner mismatch returns200[]. |
| FC-TENANT-02 | FAIL | app/src/lib/rotation/server.ts:54,163; app/src/app/api/rotation/trials/route.ts:112 — Reads use userJWT and RLS, but trusted request mutations use the workshop-wide service key. This deliberately prevents direct PostgREST financial minting but fails the strict background-only-admin-key control; narrower writer authority is required before sensitive/customer data. |
| FC-TENANT-03 | PASS | app/src/lib/rotation/server.ts:80,151; app/src/app/api/rotation/action/route.ts:13; app/src/app/api/rotation/trials/route.ts:43 — Owner IDs derive from GoTrue verified session and membership; request body cannot override owner. |
| FC-TENANT-04 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No rotation realtime, websocket or SSE channels. |
| FC-TENANT-05 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Private portfolio/trial reads are no-store; public-market metadata cache has no user records. |
| FC-TENANT-06 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: For each shared service inspect the document, message or object schema for a tenant field and the query path for a tenant filter; search the index as tenant A for a term present only in tenant B's data, and list object-storage prefixes for tenant separation. |
| FC-TENANT-07 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No vector search or RAG in rotation. |
| FC-TENANT-08 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No model agent reads rotation user data. |
| FC-TENANT-09 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm a monitor over query or audit logs for requests where the session tenant differs from the row tenant, wired to a real alert channel; fire a synthetic cross-tenant read and confirm the alert arrives. |

## authn_sessions

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-AUTH-01 | PASS | app/src/lib/rotation/server.ts:35; security-evidence/protected-route-inventory.json; security-evidence/post-review-verification.json — All seven private exported handlers use protectedRoute, which verifies GoTrue identity and app membership before handler logic. Public exceptions are enumerated: session authentication boundary, public market and public history. Unauthenticated protected request returns401 with correlationID. Source inventory and local runtime verified; deployment verification remains separate. |
| FC-AUTH-02 | PASS | app/src/app/api/rotation/action/route.ts:13; app/src/app/api/rotation/trials/route.ts:46; security-evidence/rls-verification.json — Preview and trial IDs are combined with session-owner filters and RLS; cross-owner query returns no records. |
| FC-AUTH-03 | PASS | app/src/lib/rotation/server.ts:122; supabase/migrations/202610130001_rotation_workshop.sql — No public admin-control API. Demo provisioning assigns fixed synthetic metadata and member record; client cannot choose a role or existing identity. |
| FC-AUTH-04 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — One workspace-member permission tier; demo marks synthetic account lifecycle, not an elevated user role. |
| FC-AUTH-05 | PASS | app/src/lib/rotation/server.ts:73; security-evidence/server-verification.json — HttpOnly, SameSiteStrict, host-only path/api/rotation; Secure enabled in production source. Local cookie flags read directly. Production cookie still requires deployment verification. |
| FC-AUTH-06 | FAIL | app/src/lib/rotation/server.ts:73,80,139; GoTrue container GOTRUE_JWT_EXP=3600 — One-hour access and seven-day renewable refresh cookies plus local logout exist; no absolute/idle session policy or user session-list/all-session revoke surface proven. |
| FC-AUTH-07 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Sign in on two clients, change the password on one and replay the other's token, expecting rejection; in code confirm a per-user token version or revocation list is bumped on those events. |
| FC-AUTH-08 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — GoTrue issues tokens; app does not implement its own token issuer. |
| FC-AUTH-09 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — GoTrue verifies tokens via server /auth/v1/user; app does not decode/verify JWTs itself. |
| FC-AUTH-10 | PASS | app/src/lib/rotation/server.ts:80; security-evidence/server-verification.json — Every private request resolves bearer token through trusted GoTrue user endpoint before reading identity and applies membership check. |
| FC-AUTH-11 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No OAuth/social-login or private exchange authorization flow. |
| FC-AUTH-12 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Inspect service-to-service calls for user session cookies or a single shared API key; confirm each caller holds its own credential with an expiry and a narrow scope, and that agent identities are separately enumerable in IAM or config so their actions can be attributed. |
| FC-AUTH-13 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Personal paper workshop does not sell enterprise SSO. |

## input_output_attacks

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-INPUT-01 | PASS | app/src/lib/rotation/server.ts:33; app/src/lib/rotation/engine.ts; app/src/app/api/rotation/trials/route.ts; security-evidence/server-verification.json — Bounded streaming JSON body, type/range validation for financial inputs and revisions; negative deposit refused400. |
| FC-INPUT-02 | PASS | app/src/app/api/rotation/action/route.ts:16; security-evidence/approval-verification.json — Explicit action fields; server rebuilds preview economics. Injected after/fee fields ignored; exact trusted balances and fees persisted. |
| FC-INPUT-03 | PASS | app/src/lib/rotation/server.ts:54; supabase/migrations/202610130001_rotation_workshop.sql — PostgREST structured bodies and fixed-name SQL functions with typed parameters; no user SQL concatenation. |
| FC-INPUT-04 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Rotation sends no email. |
| FC-INPUT-05 | PASS | app/src/app/rotation/page.tsx; app/src/components/rotation/ActivityList.tsx — User names/descriptions render as React text expressions; scoped UI does not feed them into an HTML sink. |
| FC-INPUT-06 | PASS | app/src/lib/rotation/server.ts:24; local curl sameOrigin200 versus attackerOrigin403 observed2026-10-12 Eastern — Origin must equal protocol plus browser-controlled HTTPHost; missing Origin/cross-site rejected; Strict cookies. Fixed Next bind-host normalization mismatch. |
| FC-INPUT-07 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Rotation exposes no LLM output. |
| FC-INPUT-08 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Rotation has no model ingestion pipeline. |
| FC-INPUT-09 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Rotation exposes no upload endpoint; bounded JSON requests are covered under INPUT-01. |

## payments_webhooks

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-PAY-01 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No rotation webhook endpoints. |
| FC-PAY-02 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No rotation webhook deliveries; paper duplicate approvals tested separately. |
| FC-PAY-03 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No rotation webhook business logic. |
| FC-PAY-04 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No checkout or real charges. |
| FC-PAY-05 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No paid entitlement or plan flow. |
| FC-PAY-06 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No scheduled rotation HTTP task endpoint. |
| FC-PAY-07 | FAIL | app/src/lib/rotation/server.ts:54,69 — Internal database/auth mutations use bearer authentication over TLS, not per-body HMAC. No claim of this stricter service-to-service control. |
| FC-PAY-08 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No paid subscription. |
| FC-PAY-09 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No card payments or disputes. |
| FC-PAY-10 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No completed monetary payments requiring receipts. |

## secrets_supply_chain

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-SECRET-01 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Run the production build and grep the output for connection-string patterns, `sk_`, `service_role`, private hostnames and every value in the server `.env`; confirm a `server-only` (or equivalent) import guard exists in each server module and that importing one from a client component breaks the build. |
| FC-SECRET-02 | PASS | app/src/lib/rotation/server.ts:11; git check-ignore app/.env.local returned app/.env.local — Credentials read from server-only WPR environment; env file mode600 and ignored; no literal credential values in new source. |
| FC-SECRET-03 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm `.env*` appears in .gitignore and that `git log --all -- .env` is empty; run `gitleaks detect --log-opts=--all` across the entire history; attempt a commit containing a fake key and confirm the hook rejects it. |
| FC-SECRET-04 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Check the secret manager's last-rotated timestamps against the stated interval; confirm a rotation runbook exists naming each credential, its owner and the steps to rotate and revoke it, including third-party integrations. |
| FC-SECRET-05 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Inspect deployment manifests and container definitions for a per-service env list instead of one blanket set; grep application code for passing `process.env` wholesale into modules, SDK clients or templates. |
| FC-SECRET-06 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm CI runs `npm ci` / `pnpm install --frozen-lockfile` rather than `npm install`, and that a tampered lockfile hash fails the job; run the audit over the full dependency tree and review the flagged list; confirm install scripts are disabled by default or explicitly allowlisted. |
| FC-SECRET-07 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Runtime rotation stack does not load external model artifacts, skills or MCP tools. |

## encryption_data

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-CRYPTO-01 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Check each storage provider's configuration for encryption at rest (RDS `StorageEncrypted`, bucket default encryption, disk encryption) and confirm backup and export destinations are covered as well as the primary volume. |
| FC-CRYPTO-02 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: In the CDN dashboard or API confirm the SSL mode is Full (strict) or equivalent; from the proxy's network request the origin over plain HTTP and confirm it refuses or redirects; confirm the origin certificate is valid and not self-signed without pinning. |
| FC-CRYPTO-03 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No PHI or regulated customer financial account data is stored; paper balances are synthetic. |
| FC-CRYPTO-04 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No native mobile client in scope. |
| FC-CRYPTO-05 | FAIL | app/src/lib/rotation/server.ts:54,69 — Workshop requests use HTTPS plus bearer credentials; mutualTLS is not configured in the application fetch path. |
| FC-CRYPTO-06 | PASS | app/src/lib/rotation/server.ts:57,69,73,108 — Tokens travel in Authorization headers and HttpOnly cookies. Password grant uses POSTbody. Client session response returns only id/email/demo. |

## audit_incident

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-AUDIT-01 | FAIL | supabase/migrations/202610130002_rotation_owner_reads_audit.sql; security-evidence/server-verification.json — Append-only actor/time/action/revision trail works and transactional mutation audit is proven, but source-address fields and defined retention are not implemented. |
| FC-AUDIT-02 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No PHI or comparable regulated records in this synthetic workshop. |
| FC-AUDIT-03 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No runtime model generations or agent tool calls. |
| FC-AUDIT-04 | FAIL | docs/operations/rotation-workshop.md Incident and recovery boundaries — Operational containment/recovery note exists; no complete severity/oncall/customer-notification/breach-clock runbook with owner-confirmed contacts. |

## observability_resilience

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-OBS-01 | PASS | app/src/lib/rotation/server.ts:19; app/src/lib/rotation/engine.ts:18; security-evidence/post-review-verification.json — Unexpected errors return a generic500/503 message and correlationID; server logs only safe type/status/correlation metadata. Only deliberate ApiError and typed RotationValidationError messages are exposed. Source boundary inspected; runtime proves safe typed400 and protected401 correlation. An injected unexpected500 was not exercised; deployed behavior still requires release verification. |
| FC-OBS-02 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm an error tracker is initialised on both server and client with its DSN set in production; trigger an error and find the event with its stack and request context; open the issue list and confirm grouping with event and affected-user counts. |
| FC-OBS-03 | FAIL | app/src/lib/rotation/server.ts:18,119; wpr_audit live schema — Audit rows identify actor/actions, but request IDs do not propagate through responses/auth/database calls or structured telemetry. |
| FC-OBS-04 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm an external multi-region monitor targets a path that exercises the database rather than a static page, and that a /health endpoint exists and is consumed by the load balancer or scheduler; break a dependency in staging and confirm both react. |
| FC-OBS-05 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No paying users; no production SLO claim. |
| FC-OBS-06 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm hourly counters and alert rules exist for each metric; suppress a payment code path in staging and confirm the alert fires; query the metric store for the last 24 hours and confirm continuous data rather than gaps. |
| FC-OBS-07 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No revenue-critical customer flow; interactive paper QA evidence retained separately. |
| FC-OBS-08 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No rotation background queue; public data calls have explicit request timeouts. |
| FC-OBS-09 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Run EXPLAIN on the queries behind the top endpoints and confirm index scans rather than sequential scans on large tables; confirm `pg_stat_statements` or the equivalent slow-query log is enabled and surfaced; list the slowest statements of the last week and confirm someone has looked at them. |
| FC-OBS-10 | FAIL | app/src/lib/rotation/server.ts:57,71; docs/operations/rotation-workshop.md — Outbound15s timeouts are explicit; there is no per-dependency circuit breaker or aggregate request budget. PostgREST/host pool sizing was not changed or validated here. |
| FC-OBS-11 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: List cache keys and TTLs by data class; confirm price, inventory and permission keys are event-invalidated or under 60 seconds; confirm a lock or single-flight wraps the refresh path; change a price and re-read through the cache to confirm the new value appears within the stated bound. |
| FC-OBS-12 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm the backup schedule and PITR setting for each datastore (`wal_level`, `archive_mode`, or the provider's PITR flag) and check the backup destination's account and region against the primary's; list the most recent successful backup timestamp for each. |
| FC-OBS-13 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Open the runbook and the restore-test log; confirm the last test falls within the quarter and records elapsed time plus a data-integrity check; confirm RTO and RPO values are documented and that the measured restore time meets the RTO. |
| FC-OBS-14 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No paying users or customer status-page commitment. |
| FC-OBS-15 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — No application replica reads; PostgREST uses workshop primary. |

## edge_infra

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-EDGE-01 | PASS | security-evidence/local-headers-updated.txt; app/next.config.ts — Fresh local /rotation200 response carries HSTS, X-Frame-Options DENY, nosniff and Referrer-Policy. Scoped configuration covers /rotation and /api/rotation routes. Local HTTP HSTS is header evidence, not browser TLS enforcement; deployed HTTPS headers require separate verification. |
| FC-EDGE-02 | FAIL | security-evidence/local-headers-updated.txt; app/next.config.ts — An enforced partial CSP now limits frame ancestors, objects, base URI and form actions. It does not restrict script sources, so the strict script-allowlist control remains FAIL. Production header verification remains separate. |
| FC-EDGE-03 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm the WAF is enabled with managed OWASP rules plus custom rules for injection and traversal patterns; send a burst of requests to the login endpoint and confirm a 429 or challenge; confirm rate-limit counters are keyed by user and endpoint in middleware as well as at the edge. |
| FC-EDGE-04 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: From an arbitrary host connect directly to the origin IP on 80/443 and confirm refusal; check firewall and security-group rules against the CDN's published ranges; look the domain up in a passive-DNS service and inspect an outbound email's Received headers for the origin address. |
| FC-EDGE-05 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: `sshd -T | grep -E 'passwordauthentication|permitrootlogin'`; `ufw status verbose` or `iptables -L` for a default DROP policy; `nmap -Pn -p <db port> <public ip>` from off-host; confirm unattended-upgrades is installed and enabled. |
| FC-EDGE-06 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Server fetch URLs are authored constants/config, never supplied by browser. |
| FC-EDGE-07 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Enumerate the zone's CNAME and A records, resolve each target and check whether the destination is still claimed by you; confirm a scheduled scan exists with a recent report; confirm the documented action is removal rather than parking. |
| FC-EDGE-08 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Compare connection strings and API keys across environment configurations and confirm no value is shared; from the staging environment attempt to connect to the production database and confirm network or credential refusal. |
| FC-EDGE-09 | N/A | Scoped inventory: app/src/app/api/rotation; app/src/app/rotation/about/page.tsx; docs/operations/rotation-workshop.md — Rotation does not send mail; seeded and synthetic users are confirmed through GoTrue admin. |

## testing_release

| Control | Verdict | Evidence and limitation |
|---|---|---|
| FC-TEST-01 | FAIL | gh api repos/danman60/wolfpack/branches/main/protection returned404 Branch not protected — Default branch permits direct pushes. Repository rule change requires explicit owner workflow decision. |
| FC-TEST-02 | FAIL | rg --files .github returned directory absent; pathlib .github/workflows.exists() false — No repository CI workflow exists to enforce the specified test/lint/build/security gates. Local checks are not merge protection. |
| FC-TEST-03 | FAIL | tests/agent/flow-rotation-paper.md; tests/agent/rotation-paper-qa.py; .github/workflows exists false — Feature browser QA exists, but no percommit enforced minimum coverage gate. |
| FC-TEST-04 | FAIL | tests/agent/rotation-paper-qa.py; docs/operations/rotation-workshop.md — QA uses explicitly scoped disposable identities in real workshop, preserving evidence. It does not recreate an empty isolated database perCI run. |
| FC-TEST-05 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Locate the authorization tests; confirm cases exist per endpoint for wrong-user access (403/404), prohibited field writes (rejected or stripped) and a tenant-A-then-tenant-B leakage check; delete an ownership check locally and confirm the suite goes red. |
| FC-TEST-06 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm the platform creates a per-PR preview URL with its own database or seeded data; read the pipeline for a staging gate before the production job; perform a rollback to the previous deployment and time it. |
| FC-TEST-07 | FAIL | supabase/migrations/202610130001_rotation_workshop.sql through004; security-evidence/db-security.txt — Additive migrations applied transactionally and recorded; no migration rehearsal on a production copy or rollback script was part of this paper-workshop change. |
| FC-TEST-08 | UNVERIFIED | Audit scope: working tree rooted at git60cccd72 and livewpr workshop only; deployed rotation release was not available at snapshot. — Settle with: Confirm an axe or pa11y step in CI with a failing threshold and run it against the main flows; tab through signup and checkout without a mouse and confirm every control is reachable with a visible focus ring. |
