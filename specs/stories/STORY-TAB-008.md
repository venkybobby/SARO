# STORY-TAB-008: Tab consolidation — fold 5 thin tabs into their natural homes

**Status:** in-progress
**Screen/Area:** Sidebar navigation + host pages (Sidebar.jsx, AppShell.jsx, RulePacks, ComplianceHub, TraceView, Dashboard, AdminSettings, TrustCenter)

> Product sign-off: owner invoked `/story STORY-TAB-008` on 2026-07-23 after the
> TAB-001..007 contract fixes (prerequisites) were implemented and reviewed.
> Pattern follows STORY-112 (Trust Center consolidation): host pages embed the
> original components unchanged, preserving content, data sources, access
> control, and every existing FND pin on those components.

## Premise verification

| Referenced artifact | Evidence |
|---|---|
| Admin persona exposes 19 tabs pre-story | frontend/src/components/Sidebar.jsx PERSONA_TABS.admin (18 after TAB-004 removed nothing from admin; count verified in Sidebar.test.jsx PERSONA_EXPECTED.admin = 19 labels) |
| Drift Alerts + Rule Packs share routers/rule_packs.py | routers/rule_packs.py |
| ComplianceHub ALREADY fetches /compliance-matrix/coverage (demo-census-safe) | frontend/src/pages/ComplianceHub.jsx:366-372; tests/regression/test_story_412_demo_tab_endpoint_census.py |
| Remediation list = open fail/warn traces (GET gated by get_current_user only) | routers/remediation.py:513-520 |
| PATCH /remediation/traces/{id}/remediate has NO require_write_access — read-only demo token could reach a write | routers/remediation.py:168-174; auth.py:238-257 (helper exists; FND-015 class) |
| Onboarding status endpoint + existing first-login wizard | routers/onboarding.py; AppShell.jsx OnboardingWizard (fixed in TAB-002) |
| Evaluations list gate admits admin/operator/super_admin; /latest + /{run_id} stay super_admin/operator | routers/evaluations.py (TAB-004) |
| STORY-112 embed-unchanged precedent | frontend/src/pages/TrustCenter.jsx:7-16 |
| DEMO_TABS whitelist (dashboard, trace_view, compliance_hub, reports) | frontend/src/config/demoTabs.json |

## Goal
Five of the seven audited tabs are filters or sub-views of surfaces that already exist. Fold them in: **Rule Packs** absorbs Drift Alerts; **Compliance Hub** absorbs Coverage Gap; **TRACE View** absorbs the Remediation queue; **Dashboard** absorbs Onboarding as a first-run banner; **Admin Settings** absorbs Evaluations (with a detection-quality card in Trust Center for roles the backend admits). AIMS is renamed "Model Inventory". Admin sidebar shrinks 19 → 14.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given any persona, When the sidebar renders, Then `drift_alerts`, `coverage_gap`, `remediation`, `onboarding`, and `evaluations` are no longer top-level tabs, and each relocated capability renders inside its new host (Rule Packs / Compliance Hub / TRACE View / Dashboard / Admin Settings respectively) — the embedded component is the original one (existing pins stay valid).
- AC-2: Given the admin persona, Then the sidebar has ≤14 entries (from 19); given super_admin, ≤12 (from 17).
- AC-3: Given a tenant with `onboarding_complete: false`, When an admin/super_admin opens the Dashboard, Then a dismissible setup checklist renders (the TAB-002 API-driven component); given `onboarding_complete: true` or a prior dismissal, it never renders.
- AC-4: Given the Dashboard, Then an "open remediations" count card (from `GET /api/v1/remediation` `total`) deep-links to TRACE View; on fetch failure the card is absent (fail-silent, no fake zero).
- AC-5: Given a demo session (`role=demo_viewer`) on TRACE View or Compliance Hub, Then the embedded remediation queue does NOT render (demo surface unchanged); given any `read_only` user, Mark Complete is not offered (FND-054 pattern). Backend: `PATCH /remediation/traces/{id}/remediate` gains `require_write_access` (FND-085) so the UI gate is defense-in-depth, not the control.
- AC-6: Given Trust Center, Then a "Detection quality" evidence card shows the latest completed evaluation run via the LIST endpoint, rendered ONLY for account roles the backend admits (admin/operator/super_admin) — other viewers see no card and no 403.
- AC-7: Given existing tests referencing removed tabs (Sidebar.test.jsx PERSONA_EXPECTED), Then they are updated to the new sets with exact-count assertions intact (no weakened assertions); the STORY-412 demo census and demo-tab tests stay green.
- AC-8: Given the sidebar, Then the AIMS tab label reads "Model Inventory" (page unchanged).

## Edge Cases
- Persona `ai_auditor` loses `coverage_gap` (its new host, Compliance Hub, is a compliance-persona surface) — deliberate least-surface decision, logged; their core surfaces (TRACE, Rule Packs incl. drift, Remediation-in-TRACE) remain.
- Operator keeps the remediation queue via TRACE View (already in their tabs).
- Onboarding banner dismissal persists per browser (localStorage), keyed separately from the first-login wizard's dismissal.
- Embedded sections fail independently: a drift-endpoint error inside Rule Packs must not blank the packs list (and vice versa).
- Deep links / stale `activePage` values for removed page keys fall back to Dashboard (existing AppShell `|| Dashboard` behavior).

## Out of Scope
- New backend endpoints; visual redesign of host pages beyond hosting the moved content.
- Widening `/evaluations/latest` or `/{run_id}` gates (Trust Center card uses the list endpoint; see TAB-004 security note).
- Removing the page component files (they are the embedded implementations).

## Non-Functional Requirements
- Vitest integration coverage for every embed + the Sidebar set changes; pytest pin for the FND-085 write-gate. Live Playwright E2E of the relocated remediation flow is deferred with the existing documented limitation (no /app login automation — tests/e2e covers the /demo surface only); tracked as follow-up, not silently dropped.
- STORY-412: demo census unaffected (no new endpoint on demo tabs — the remediation embed is hidden for demo sessions; coverage was already fetched by Compliance Hub).

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
