# Rotation security evidence

Sourced: 2026-10-12T23:08:12-04:00 Eastern. Scoped audit completed against local source/runtime and live workshop database; production deployment verification remains separate.

107 controls: {'N/A': 42, 'UNVERIFIED': 27, 'FAIL': 21, 'PASS': 17}.

- [Complete control matrix](../../audits/2026-10-12-rotation-security-audit.md)
- [Machine-readable107 controls](../../audits/2026-10-12-rotation-security-audit.json)
- [Authenticated server workflow](security-evidence/server-verification.json)
- [Direct owner RLS](security-evidence/rls-verification.json)
- [Atomic approval and tamper refusal](security-evidence/approval-verification.json)
- [Post-review runtime checks](security-evidence/post-review-verification.json)
- [Protected handler inventory](security-evidence/protected-route-inventory.json)
- [Updated local headers](security-evidence/local-headers-updated.txt)
- [Live DB grants/policies/functions](security-evidence/db-security.txt)

Server verifies real GoTrue identity and app membership. OwnerJWT/RLS protects reads. Trusted server-only mutation access uses the shared workshop service role; this is recorded as a strict-checklist failure, not hidden behind a passing RLS test. CAS, preview expiry and one-time consumption are enforced in PostgreSQL.

Public demo visitors receive separate synthetic identities, bounded by durable provisioning counters. No live order integration, real funds or exchange credentials exist in this scope. Consumer lifecycle/legal/retention/operational gates remain explicit.

Three controls changed from FAIL to PASS after inspected fixes: FC-AUTH-01, FC-OBS-01 and FC-EDGE-01. FC-EDGE-02 remains FAIL because script sources are not allowlisted. These are local source/runtime findings; deployed checks remain separate.
