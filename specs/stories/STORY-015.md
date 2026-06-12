STORY-015: Tenant Isolation Evidence Pack (S-1107)
Status: ready    Screen/Area: Security / CI / Trust Page

Goal
Produce runnable, exportable proof of tenant isolation as interim evidence until an external pen test is funded. References Critical Review section 6.1 test SEC-002 (distinct from Plan v3 story SEC-002). Closes FB-020; interim for FB-028.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a user of Tenant B, When Tenant A's traces, samples, and reports endpoints are requested, Then every request returns 403 with no data leakage
AC-2: Given 50 concurrent scans across 50 tenants, When the suite runs, Then zero cross-tenant rows appear in any tenant's results (Critical Review PERF-004)
AC-3: Given every registered router, When an unauthenticated request sweep runs, Then each protected endpoint returns 401
AC-4: Given scripts/generate_security_evidence.py, When it executes, Then a signed PDF with date, commit hash, and pass/fail table is written to docs/evidence/
AC-5: Given the CI configuration, When the weekly schedule triggers, Then the suite runs and the Trust page serves the latest evidence PDF

Edge Cases
- Public endpoints (health, /demo read-only route) are explicitly allow-listed in the sweep, not skipped silently.
- Concurrency test must use distinct DB sessions per thread — shared-session false positives invalidate the evidence.

Out of Scope
- External pen test (FB-028 deferred).
- Load beyond 50 tenants.

Non-Functional Requirements
Suite completes under 10 minutes. Evidence PDF includes test code commit hash for reproducibility.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
