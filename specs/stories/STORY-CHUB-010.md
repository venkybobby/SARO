STORY-CHUB-010: Verify tenant scoping on /coverage and EVF validation-status
Status: ready    Screen/Area: Compliance Hub / Security
Epic: GRC-Compliance-Hub · Priority: P2 · Depends on: —

Goal
`/api/v1/compliance-matrix/coverage` builds its result from `get_matrix_rows(db)` and `/api/v1/evf/validation-status` builds from `get_all_framework_statuses(db)` — both called with only `db`, no explicit tenant argument, despite `current_user` being available. Confirm the intended scope of each data set and prove there is no cross-tenant leakage for any tenant-scoped data, adding a regression test analogous to STORY-015's isolation evidence.

Framework mapping (per ADR-004 scope locks)
- ISO/IEC 42001: tenant data segregation for document-lifecycle artifacts.
- EU AI Act: Article 9 (risk-management data integrity per tenant).
- Ties to STORY-015 (Tenant Isolation Evidence Pack).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given `get_matrix_rows` and `get_all_framework_statuses`, When their data model is reviewed, Then it is documented in the story's technical notes whether each row set is (a) global rule/framework definitions (tenant-agnostic by design) or (b) tenant-scoped — with the determining column cited from `database.py`/`models.py`.
AC-2: Given any data found to be tenant-scoped, When `/coverage` or `/validation-status` is called, Then it filters by `current_user.tenant_id`, and a request as Tenant B never returns Tenant A's rows.
AC-3: Given data confirmed global-by-design, When the endpoint returns it, Then a code comment + test documents the intentional cross-tenant visibility so it is not mistaken for a leak later.
AC-4: Given the isolation suite, When run, Then a new case covers `/coverage` and `/validation-status` for cross-tenant access, consistent with STORY-015's evidence approach.

Edge Cases
- A framework defined globally but with tenant-specific QCO/expiry records: the global definition is shared, but per-tenant QCO data must be tenant-filtered — test both layers separately.
- Empty tenant (no matrix rows) must not fall through to another tenant's rows.

Out of Scope
- Re-architecting the matrix storage model.
- Frontend changes.

Non-Functional Requirements
- Security-auditor agent review mandatory (touches `routers/` + data access).
- Any added filter must not regress the STORY-015 isolation suite or the <10min runtime.

Test Requirements
- Integration/Security (`tests/integration`, `tests/regression`): Tenant B request to `/coverage` and `/validation-status` returns zero Tenant A tenant-scoped rows; global definitions (if any) explicitly asserted as shared-by-design.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	(documented) test docstring + endpoint comments cite determining columns	models.py:323 (EUAIActRule), :340 (NISTControl), :793 (SMEEngagement), :894 (QCORegistry), :991 (QCOExpiryNotification) — none declare tenant_id → global-by-design
AC-2	N/A — moot: no tenant-scoped data exists in either path (verified by security-auditor at ORM+migration+call-graph)	—
AC-3	test_chub010 test_coverage_identical_across_tenants / test_validation_status_identical_across_tenants	routers/compliance_matrix.py (get_coverage_summary comment), routers/evf_sprint3.py (get_all_validation_statuses comment)
AC-4	tests/test_chub010_tenant_scoping.py (cross-tenant /coverage + /validation-status cases, no tenant_id leak)	tests/test_chub010_tenant_scoping.py
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
