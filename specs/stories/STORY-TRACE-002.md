STORY-TRACE-002: Tenant-scope the trace timeline endpoint (close cross-tenant leak)
Status: ready    Screen/Area: TRACE View / Security
Epic: GRC-TRACE-View · Priority: P0 · Depends on: —

Goal
`routers/trace_view.py`'s `_get_audit_or_404(db, audit_uuid)` filters only on `Audit.id` with no tenant predicate, so any authenticated user can read any tenant's full TRACE (reasoning + findings) by UUID via `GET /api/v1/audit/{id}/trace` and its export variants. This is a cross-tenant data leak and a hard blocker for STORY-TRACE-001, which repoints the UI to this endpoint. Add tenant scoping consistent with the already-correct `/api/v1/traces/{id}` path (`routers/traces.py` uses `_get_audit_or_404(audit_id, current_user.tenant_id, db)`).

Framework mapping (per ADR-004 scope locks)
- ISO/IEC 42001: tenant data segregation for trace/document artifacts.
- EU AI Act: Article 9 (integrity of per-tenant risk records).
- Ties to STORY-015 (Tenant Isolation Evidence Pack).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given `_get_audit_or_404` in `routers/trace_view.py`, When it loads an audit, Then it filters by both `Audit.id` and `current_user.tenant_id`.
AC-2: Given a user of Tenant B, When they request `GET /api/v1/audit/{A}/trace` for an audit owned by Tenant A, Then they receive 404 (no existence disclosure) and zero trace data.
AC-3: Given the export endpoints `/api/v1/audit/{id}/trace/export`, `/export/json`, `/export/pdf` (same router), When called cross-tenant, Then they are equally scoped and return 404.
AC-4: Given a user of the owning tenant, When they request their own audit's trace, Then it returns 200 with full data (no regression).

Edge Cases
- A nonexistent UUID and a foreign-tenant UUID must both return 404 with identical responses (no timing/message oracle distinguishing them).
- Service/system roles (if any) that legitimately need cross-tenant access must be allow-listed explicitly, not via the missing filter.

Out of Scope
- Frontend changes (STORY-TRACE-001).
- Role-based access (STORY-TRACE-003).

Non-Functional Requirements
- Security-auditor agent review mandatory (touches `routers/` + data access).
- Must not regress the STORY-015 isolation suite or its <10min runtime.

Test Requirements
- Integration/Security (`tests/integration`, `tests/regression`): cross-tenant request to `/audit/{id}/trace` and all three export variants → 404, zero data; same-tenant → 200; foreign-UUID vs nonexistent-UUID responses identical.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
