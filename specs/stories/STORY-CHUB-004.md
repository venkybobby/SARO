STORY-CHUB-004: Readiness Checklist — persist state, scope per tenant, back with real status
Status: ready    Screen/Area: Compliance Hub
Epic: GRC-Compliance-Hub · Priority: P1 · Depends on: —

Goal
The Readiness Checklist in `frontend/src/pages/ComplianceHub.jsx` is a hardcoded six-item array held in `useState` with no persistence — every refresh resets all boxes to unchecked, and the list is identical for every tenant and framework. It implies progress tracking that survives exactly zero page loads. Make it real: persist per-tenant checklist state via a backend endpoint, and where a checklist item maps to a known control/document, derive its completion from actual status rather than a manual toggle.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 9 (risk-management readiness items), Article 17 (QMS document items).
- NIST AI RMF: GOVERN (readiness/oversight tracking).
- ISO/IEC 42001: document-lifecycle linking — checklist items that correspond to lifecycle documents reflect their real state.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a new backend route `GET /api/v1/compliance/readiness` (new file `routers/readiness.py`, registered in `main.py`), When a `compliance_lead` of tenant T calls it, Then it returns the checklist items with each item's `completed` boolean for tenant T only.
AC-2: Given `PUT /api/v1/compliance/readiness/{item_key}` with `{completed: bool}`, When a permitted user toggles an item, Then the state persists to a tenant-scoped store and survives reload.
AC-3: Given items that map to a derivable source (e.g. "Incident response plan reviewed" ↔ ADR-004 critical-gap status; "AI systems registered in inventory" ↔ AIMS records), When the list loads, Then those items report `completed` from the real source and are rendered read-only (not user-toggleable), with a tooltip naming the source.
AC-4: Given the checklist in `ComplianceHub.jsx`, When it renders, Then checked state comes from the endpoint (not in-memory `useState` defaults) and the "{n}/{total} complete" counter reflects persisted + derived state.
AC-5: Given the readiness store is empty for a tenant, When loaded, Then all manual items default to unchecked and derived items reflect their true source state.

Edge Cases
- Two browser tabs toggling the same item: last-write-wins, and a reload reconciles to server state.
- A derived item whose source is unavailable renders as "unknown" (not silently checked).
- Tenant with no AIMS/ADR data: derived items show unchecked/unknown, never error the page.

Out of Scope
- Editing the set of checklist items via UI (item catalog stays code-defined for this story).
- Cross-framework checklist variants (single global list this story; per-framework is a follow-up).

Non-Functional Requirements
- Tenant isolation: no readiness state leaks across tenants (security-auditor review required — touches `routers/`).
- Endpoint p95 < 300ms for a 6–20 item list.

Test Requirements
- Integration (`tests/integration`): GET returns tenant-scoped items; PUT persists across a fresh request; cross-tenant GET shows no foreign state.
- Unit: derived-item resolver maps source status → completed/unknown correctly.
- Frontend unit (`ComplianceHub.test.jsx`): checked state hydrates from endpoint; derived items render read-only with source tooltip; counter reflects combined state.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	test_chub004 test_route_get_returns_tenant_checklist	routers/readiness.py (GET), services/readiness_service.py (get_readiness)
AC-2	test_chub004 test_route_put_persists_and_is_tenant_scoped / test_set_readiness_persists_across_fresh_query	routers/readiness.py (PUT), services/readiness_service.py (set_readiness), models.py ComplianceReadinessItem, migrations/026
AC-3	test_chub004 test_empty_store..._derived_from_source / test_derived_completed_when_aims_records_exist; ComplianceHub.test.jsx "AC-3: derived items are read-only with a source tooltip"	services/readiness_service.py (_resolve_aims_inventory), frontend ComplianceHub.jsx
AC-4	ComplianceHub.test.jsx "AC-4: checked state hydrates from the endpoint" + "completion counter reflects..."	frontend/src/pages/ComplianceHub.jsx (readiness fetch + render)
AC-5	test_chub004 test_empty_store_manual_unchecked_derived_from_source (empty store defaults) + test_derived_resolver_unknown_on_source_error	services/readiness_service.py
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
