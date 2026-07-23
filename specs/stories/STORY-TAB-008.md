# STORY-TAB-008: Tab consolidation — fold 5 thin tabs into their natural homes (7 → 2 top-level entries)

**Status:** draft
**Screen/Area:** Sidebar navigation + affected pages (frontend/src/components/Sidebar.jsx, App page router)

> **Draft — needs product sign-off before /story will run.** This restructures navigation
> for every persona; the contract-fix stories (STORY-TAB-001..007) are prerequisites so
> content being moved actually works at its destination.

## Premise verification

| Referenced artifact | Evidence |
|---|---|
| Admin persona currently exposes 19 tabs | frontend/src/components/Sidebar.jsx:24-31 (PERSONA_TABS.admin) |
| Drift Alerts and Rule Packs share a router and data source | routers/rule_packs.py (both endpoints) |
| Coverage Gap is a rollup of the Compliance Hub's matrix rows | routers/compliance_matrix.py:119-207 |
| Remediation list = open fail/warn AuditTraces (TRACE data) | routers/remediation.py:513-589 |
| Onboarding is a one-time 4-step checklist | routers/onboarding.py:68-105 |
| Evaluations list/trigger restricted to super_admin/operator | routers/evaluations.py:156-234 |

## Goal
Reduce nav sprawl and eliminate "empty tab" impressions for prospects/admins: five of the seven audited tabs are filters or sub-views of surfaces that already exist. Target end-state: **Rule Packs** (absorbs Drift Alerts) and **Model Inventory** (renamed AIMS) remain top-level; Coverage Gap, Remediation, Onboarding, and Evaluations move into Compliance Hub, TRACE View, Dashboard first-run, and Admin Settings respectively.

## Proposed moves (each independently shippable)
1. Drift Alerts → status banner/section inside Rule Packs; tab removed from all personas.
2. Coverage Gap → "Coverage" view inside Compliance Hub; tab removed.
3. Remediation → "Open findings" filter + remediate action inside TRACE View; Dashboard card "N open remediations" deep-links there; tab removed (operator persona keeps a direct entry point via TRACE View).
4. Onboarding → dismissible Dashboard first-run checklist shown until `onboarding_complete`; tab removed.
5. Evaluations → section under Admin Settings (role-gated per STORY-TAB-004); latest completed run surfaces as a "detection quality evidence" card in Trust Center. NOTE (security-auditor, STORY-TAB-004): `GET /evaluations/latest` and `GET /evaluations/{run_id}` remain super_admin/operator-only — if this consolidation adds a run-detail drill-down for admin, widen those gates in the same change or the FND-077 visible-but-403 class recurs.
6. AIMS → rename label to "Model Inventory"; keep top-level.

## Acceptance Criteria (to be finalized at sign-off)
- AC-1: Given any persona, Then the sidebar no longer lists drift_alerts, coverage_gap, remediation, onboarding, or evaluations as top-level tabs, and every relocated capability is reachable in ≤2 clicks from its new home.
- AC-2: Given the admin persona, Then the sidebar has ≤13 entries.
- AC-3: Given a tenant with incomplete onboarding, Then the Dashboard shows the checklist banner; given `onboarding_complete`, it never renders.
- AC-4: Given existing tests referencing removed tabs, Then they are updated with the relocation (no weakened assertions).

## Out of Scope
- New backend endpoints; visual redesign of destination pages beyond hosting the moved content.

## Non-Functional Requirements
- Playwright E2E for the relocated remediation flow (flow change → E2E required per testing gate).
- STORY-412 demo-tab census must stay green (demo whitelist unaffected).

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
