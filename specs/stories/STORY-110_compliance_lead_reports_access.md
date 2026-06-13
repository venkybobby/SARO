# STORY-110: Give Compliance Lead access to Reports (align backend authz with frontend nav)

**Status:** ready
**Screen/Area:** RBAC — routers/reports.py, frontend/src React Sidebar persona tabs

## Goal
The Reports feature's API enforces `require_role("super_admin","operator")` on every endpoint, but the persona model and the React nav do not consistently surface Reports to the personas that need it — notably **Compliance Lead**. Make Reports access coherent: a Compliance Lead who should see Reports gets both the nav entry and a non-403 API response, and the backend/ frontend agree on who is allowed.

## Context (file:line)
- `routers/reports.py:60,155,181,196,211,226,291,423,524,565` — all gated by `require_role("super_admin","operator")` (role-based, not persona-based).
- React nav: `frontend/src/components/Sidebar.jsx` TAB_REGISTRY includes a `reports` tab; `PERSONA_TABS` controls which personas see it.
- Role↔persona: per investigation, role `operator` ↔ `compliance_lead` persona, role `super_admin` ↔ `admin` persona.
- NOTE: the legacy Streamlit `frontend/app.py` reports wiring is being removed by STORY-105 — treat React as the only frontend here.

## Decision Required (resolve at Definition-of-Ready)
Confirm the intended Reports allow-list. **Default:** Compliance Lead **is** allowed Reports (read). Then the fix is to ensure (a) the React `PERSONA_TABS` lists `reports` for `compliance_lead`, and (b) the backend authorizes the role/persona a Compliance Lead actually carries. If the Compliance Lead's role is already `operator`, the API already permits them and only the nav needs fixing — `/story` must verify the real role mapping before changing authz.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given a Compliance Lead user, When they load the app, Then the Reports tab appears in their sidebar (React `PERSONA_TABS` includes `reports` for `compliance_lead`).
- **AC-2:** Given that same user, When they call the Reports endpoints, Then they receive a successful (non-403) response — i.e. the backend authz (`require_role`/persona check) admits the role a Compliance Lead carries.
- **AC-3:** Given a persona NOT intended to see Reports, When they load the app or call the endpoints, Then they neither see the tab nor get a 200 (no over-broadening; least privilege preserved).
- **AC-4:** Given the backend allow-list and the frontend `PERSONA_TABS`, When compared by a test, Then they agree on Reports visibility for every persona (no frontend-shows / backend-403 mismatch, and vice-versa).

## Edge Cases
- Avoid widening `require_role` to a broad set just to fit one persona — prefer a persona/permission check that names exactly the intended personas.
- Verify the actual `user.role`/`user.persona_role` a Compliance Lead is provisioned with before assuming a 403 exists.

## Out of Scope
- The ai_auditor seed fix (STORY-109).
- New report content or export features.

## Non-Functional Requirements
- security-auditor review required (touches routers/ + authz). Follow `.claude/skills/api-conventions`. No privilege escalation beyond the approved allow-list.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_frontend_nav_grants_compliance_lead_reports` | frontend/src/components/Sidebar.jsx |
| AC-2 | `test_compliance_lead_persona_is_allowed_reports` | routers/reports.py |
| AC-3 | `test_unprivileged_persona_and_role_is_denied`, `test_legacy_roles_still_allowed` (additive, fail-closed) | routers/reports.py |
| AC-4 | `test_reports_persona_allowlist_matches_frontend_tab_personas` | routers/reports.py, Sidebar.jsx |

**Status:** done. Root cause was two authz axes: backend gated on `role`, frontend on `persona_role`. Introduced `_require_reports_access` (allow if Reports `role` OR Reports `persona`) on all 10 endpoints — additive, no one loses access — and added `reports` to compliance_lead's nav. Independent `security-auditor`: APPROVE (persona_role not attacker-controllable; tenant scoping intact; demo-viewer bounded to demo tenant; fail-closed). Fixed Finding B (generic 403, no role echo); logged Finding A as **FND-015** (pre-existing iso-annex write endpoint lacks `require_write_access`). Branch `story/STORY-110_compliance_lead_reports_access` (stacked on 109).
