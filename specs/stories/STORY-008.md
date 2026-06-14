STORY-008: Persona RBAC Enforcement — Epic 9 Execution (PER-001..PER-004)
Status: ready    Screen/Area: Auth / Navigation / All Tabs

Goal
Execute Implementation Plan v3 Epic 9 exactly as specified: backend RBAC, persona-aware navigation, Compliance Lead Portal, Risk Officer dashboard. v3 is authoritative; this story tracks completion. Closes FB-011.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a compliance_lead user, When GET /auth/me is called, Then the response includes persona_role, allowed_tabs, and allowed_actions populated from PersonaPermission
AC-2: Given a risk_officer user, When the main navigation renders, Then AIMS, Rule Packs, and Raw Scan tabs are absent from the DOM and TRACE defaults to read-only Executive mode
AC-3: Given an ai_auditor user, When TRACE opens, Then Technical mode is the default and Rule Packs is visible
AC-4: Given a user without the required persona, When a restricted endpoint is called directly, Then the API returns 403 regardless of frontend state
AC-5: Given all three personas, When the persona journey E2E suite runs, Then all three Playwright journeys pass and the existing 153-test suite remains green

Edge Cases
- Legacy persona names (Forecaster/Autopsier/Enabler/Evangelist) remain unmapped — do not wire them; buyer personas only.
- Operator users with no persona_role: safe default deny on restricted tabs.

Out of Scope
- New features beyond the v3 Epic 9 spec.
- React migration.

Non-Functional Requirements
RBAC enforced at API layer, not only UI. allowed_tabs values match a single shared constants source.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
