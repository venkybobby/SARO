STORY-CHUB-009: Compliance Hub — remove or wire dead query params (window/sort/tenant_id)
Status: ready    Screen/Area: Compliance Hub
Epic: GRC-Compliance-Hub · Priority: P2 · Depends on: —

Goal
The Compliance Hub sends query params the backend ignores: `?tenant_id=…&window=30d` to `/compliance-matrix/coverage` (endpoint takes none; tenant derives from token) and `?tenant_id=…&limit=10&sort=desc` to `/api/v1/audits` (honors only `limit`/`offset`; tenant from token; no `sort`). Decorative params that imply controls which do nothing erode trust. Either wire each param to a real backend behavior or remove it from the request.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 13 (no UI affordance should imply behavior the system does not perform).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given `frontend/src/pages/ComplianceHub.jsx`, When it requests `/compliance-matrix/coverage`, Then `tenant_id` and `window` are removed unless a corresponding backend behavior is implemented; if `window` is kept, the endpoint must filter by it and a test must prove the result changes with the window.
AC-2: Given the audits request, When issued, Then `tenant_id` and `sort` are removed (tenant comes from the token; ordering is fixed `created_at desc` server-side), keeping only `limit`/`offset`.
AC-3: Given any param that is kept, When the page renders a control for it, Then changing the control measurably changes the data (no inert controls remain).

Edge Cases
- If `window` is implemented backend-side, default remains 30d and an invalid window value is rejected with 400, not silently ignored.

Out of Scope
- Adding new filtering features beyond reconciling existing params.

Non-Functional Requirements
- No change to tenant scoping (token-derived) — params must never become a tenant override.

Test Requirements
- Integration: request without the removed params returns identical data to the prior call (proves they were inert); if `window` kept, two windows return different aggregates.
- Frontend unit (`ComplianceHub.test.jsx`): outgoing requests contain only the params the backend honors.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
