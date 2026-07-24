# STORY-TAB-004: Evaluations tab — make nav visibility, trigger button, and backend RBAC agree

**Status:** ready
**Screen/Area:** Evaluations tab (frontend/src/pages/Evaluations.jsx, frontend/src/components/Sidebar.jsx ↔ routers/evaluations.py)

## Premise verification

| Referenced artifact | Evidence |
|---|---|
| `GET /api/v1/evaluations` requires `role in (super_admin, operator)` | routers/evaluations.py:230-234 (`require_role("super_admin", "operator")`) |
| `POST /api/v1/evaluations/trigger` requires `role == super_admin` | routers/evaluations.py:156-160 |
| Sidebar shows the tab to compliance_lead, admin, super_admin personas | frontend/src/components/Sidebar.jsx:12-38 (PERSONA_TABS) |
| Trigger button shown for personas ai_auditor/admin/super_admin | frontend/src/pages/Evaluations.jsx:28-29 |
| Result: admin and compliance_lead users get a bare "⚠ 403" | live probe 2026-07-23: demo token → 403; role gate excludes `admin` |

## Goal
Users who can see the Evaluations tab mostly can't use it: the backend admits only `super_admin`/`operator` roles while the sidebar shows the tab to compliance_lead and admin, so the page renders a bare 403 error. After this story, everyone who can see the tab can list runs, the trigger button appears only for users the backend will actually accept, and anyone else never sees a dead tab.

Decision (least-privilege): narrow the frontend to match the backend, with one backend addition — `admin` may list runs (read-only visibility for the operations owner), since the admin persona already surfaces the tab and run listings are read-only, non-tenant QA metadata. Trigger stays `super_admin`-only.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given a user whose account `role` is `admin`, `super_admin`, or `operator`, When they open Evaluations, Then `GET /api/v1/evaluations` returns 200 and runs render. (`admin` added to the list gate's allowed roles; trigger gate unchanged.)
- AC-2: Given the sidebar personas, Then `evaluations` is removed from the `compliance_lead` persona tab list (their role would 403) and remains for `admin`/`super_admin` personas.
- AC-3: Given the Evaluations page, Then the "+ Trigger Eval Run" button renders only when the user's account `role` (not persona) is `super_admin` — matching the backend trigger gate.
- AC-4: Given a user somehow reaches the page without list permission (deep link, stale persona), When the API returns 403, Then the page explains "your role does not have access to evaluation runs" instead of the raw "⚠ 403".
- AC-5: Given an authorized super_admin triggers a run, Then the existing trigger flow still works end-to-end (regression guard).

## Edge Cases
- Persona-switched super_admin (persona=compliance_lead, role=super_admin): backend admits by role → page must key its gating off `user.role`, never `persona_role`.
- `user` prop missing/undefined → no trigger button, friendly 403 handling still works.

## Out of Scope
- Widening trigger rights beyond super_admin.
- Moving Evaluations under Admin Settings / Trust Center summary card (STORY-TAB-008).

## Non-Functional Requirements
- Backend change touches an authz gate → security-auditor review required (per repo rule for routers/ + auth-adjacent changes).
- pytest: role-matrix test for the list endpoint (admin 200, compliance_lead 403, operator 200, super_admin 200); vitest: trigger-button visibility and 403 messaging.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
