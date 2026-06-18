STORY-CHUB-002: Recent Audits — grant compliance_lead read access (fix role gate)
Status: ready    Screen/Area: Compliance Hub
Epic: GRC-Compliance-Hub · Priority: P0 · Depends on: —

Goal
The Compliance Hub "Recent Audits" table calls `GET /api/v1/audits`, which resolves to `list_audits` in `routers/scan.py:329`, gated `require_role("super_admin", "operator", "demo_viewer")`. The persona this page is built for — `compliance_lead` — is not in that list, so the request returns 403, the frontend swallows it (`.catch(() => {})`), and the table always shows "No audits yet." The compliance lead can never see audit evidence on their own landing page. Grant the read access required for the personas that land on this screen, without weakening tenant isolation.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 17 (quality-management / record-keeping — compliance owner must be able to read audit records as evidence).
- NIST AI RMF: GOVERN (role-appropriate access to oversight artifacts), MEASURE (visibility into audit results).
- ISO/IEC 42001: document-lifecycle linking only.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given `list_audits` in `routers/scan.py`, When the role gate is evaluated, Then `compliance_lead` (and `risk_officer`, `admin`) are permitted to read the audit list, in addition to the existing `super_admin`/`operator`/`demo_viewer`.
AC-2: Given a `compliance_lead` user with tenant T, When they request `/api/v1/audits`, Then they receive only tenant T's audits (existing `Audit.tenant_id == current_user.tenant_id` filter unchanged) and a 200 response.
AC-3: Given a user whose role is not in the permitted set, When they request `/api/v1/audits`, Then they still receive 403.
AC-4: Given the Compliance Hub loads as `compliance_lead`, When `/api/v1/audits` succeeds, Then the "Recent Audits" table populates (no silent empty state) in `frontend/src/pages/ComplianceHub.jsx`.
AC-5: Given the audits fetch fails for any reason, When the table renders, Then a visible error row is shown (not a swallowed `.catch(() => {})`).

Edge Cases
- A tenant with zero audits still renders the legitimate "No audits yet." empty state (distinct from an access-denied failure).
- `demo_viewer` access is preserved exactly — no regression to the demo path.

Out of Scope
- The risk-score field mapping fix (STORY-CHUB-003).
- Adding write/delete on audits.
- A new compliance-scoped audit endpoint (reuse `/api/v1/audits`; only the role set changes).

Non-Functional Requirements
- Tenant isolation invariant from STORY-015 must remain green — no cross-tenant rows for any added role.
- Change touches a `routers/` file with role gating → security-auditor agent review is mandatory (per /story step 5).

Test Requirements
- Integration (`tests/integration`): `compliance_lead` → 200 + own-tenant rows only; unauthorized role → 403; cross-tenant request → 403/empty.
- Regression (`tests/regression`): assert `demo_viewer` still reads audits.
- Frontend unit (`ComplianceHub.test.jsx`): 403 path renders visible error, not empty-state.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	test_fnd_025 test_guard_grants_compliance_lead_persona	auth.py (require_role_or_persona), routers/scan.py (list_audits gate)
AC-2	test_fnd_025 test_audits_readable_by_permitted_role_or_persona[viewer/compliance_lead]	routers/scan.py (tenant filter unchanged) → 200 + own-tenant rows
AC-3	test_fnd_025 test_audits_forbidden_for_unauthorised_persona	auth.py require_role_or_persona (403 path)
AC-4	ComplianceHub.test.jsx CHUB-002 "a successful empty audits fetch still shows empty state"	frontend/src/pages/ComplianceHub.jsx
AC-5	ComplianceHub.test.jsx "AC-5: a failed audits fetch (403) shows a visible error"	frontend/src/pages/ComplianceHub.jsx (auditsError state)
Regression: demo_viewer preserved	test_fnd_025 [demo_viewer/None] case	tests/regression/test_fnd_025_audits_compliance_lead_access.py
