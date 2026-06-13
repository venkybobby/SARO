# STORY-112: Consolidate scattered governance/trust pages into one Trust Center

**Status:** ready
**Screen/Area:** frontend/src — Governance, HowSaroReasons, ClaimsMatrix, GovernanceDocs pages + nav

## Goal
Trust/governance content is fragmented across four React pages with four nav entries. Consolidate them into a single "Trust Center" page (tabbed or sectioned) so users find all governance/compliance evidence in one place, with one nav entry, preserving every existing piece of content and its data sources.

## Context (file:line)
- `Governance.jsx` (route `governance`, nav "Governance Trust", Sidebar.jsx:60) — AI governance principles + trust docs; API `/api/v1/governance/trust-documents`.
- `HowSaroReasons.jsx` (route `how_saro_reasons`, Sidebar.jsx:49) — DIR formula, 4-gate pipeline, SHAP, non-negotiables.
- `ClaimsMatrix.jsx` (route `claims_matrix`, Sidebar.jsx:48) — claims boundary matrix + EVF status; API `/api/v1/compliance-matrix/summary`.
- `GovernanceDocs.jsx` (route `governance_docs`/`dpa_governance`, Sidebar.jsx:50) — DPA, sub-processors, retention, IR plan; APIs `/api/v1/governance/docs`, `/api/v1/governance/ir-plan`.
- App wiring: `frontend/src/App.jsx` lazy imports + `PAGE_COMPONENTS`; `Sidebar.jsx` `TAB_REGISTRY` + `PERSONA_TABS`.
- Current access: compliance_lead, admin, super_admin.

## Decision Required (resolve at Definition-of-Ready)
Confirm consolidation shape. **Default:** one `TrustCenter` page with four internal sections/tabs (Governance Principles · How SARO Reasons · Claims Matrix · DPA & Governance), one nav entry `trust_center`, same persona access as today.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given the four pages' content, When consolidated, Then a single `TrustCenter` page renders all of it (principles, reasoning methodology, claims matrix + EVF status, DPA/sub-processors/retention/IR plan) with no content or data source dropped, calling the same APIs.
- **AC-2:** Given the nav, When consolidated, Then there is one `trust_center` tab and the four old entries (`governance`, `how_saro_reasons`, `claims_matrix`, `dpa_governance`/`governance_docs`) are removed from `TAB_REGISTRY` and `PERSONA_TABS`.
- **AC-3:** Given persona access, When a compliance_lead/admin/super_admin loads the app, Then they see `trust_center`; personas that previously couldn't see these pages still cannot.
- **AC-4:** Given the routing, When an old route key is requested, Then it resolves cleanly (redirect to `trust_center` or removed without falling through to Dashboard — guard against the FND-007 fall-through bug), and `App.jsx` `PAGE_COMPONENTS` is updated accordingly.
- **AC-5:** Given the frontend suite/build, When run, Then it passes with the four old page components removed or re-exported as Trust Center sections.

## Edge Cases
- Compliance copy (claims matrix / non-negotiables) must remain exact — no overclaiming introduced during the move (compliance-guard).
- Coordinate with STORY-111 (removes `dpa_governance`/`ir_plan` aliases) and the Knowledge Portal (STORY-114) which references some of the same articles — don't double-delete shared content.

## Out of Scope
- Risk Summary→Register merge (STORY-113).
- Editing the substance of any governance document.

## Non-Functional Requirements
- Follow `.claude/skills/compliance-guard`. Preserve accessibility (focus, headings) from the existing pages.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `TrustCenter.test.jsx` (all 4 sections render; content reused unchanged) | TrustCenter.jsx |
| AC-2 | Sidebar: one `trust_center` nav entry; old 5 governance entries removed | components/Sidebar.jsx |
| AC-3 | PERSONA_TABS updated (compliance_lead/admin/super_admin keep access via trust_center) | components/Sidebar.jsx |
| AC-4 | App redirects governance/how_saro_reasons/claims_matrix/dpa_governance/governance_docs → TrustCenter with initialTab (FND-007 guard); AIInsights→ClaimsMatrix anchor preserved via initialSection forwarding (vitest 90 passed) | App.jsx, TrustCenter.jsx |
| AC-5 | full vitest suite + `vite build` green (TrustCenter bundle created) | frontend/ |

**Status:** done. New `TrustCenter.jsx` renders Governance, HowSaroReasons, ClaimsMatrix, GovernanceDocs as tabbed sections (components reused unchanged → all content/APIs/access preserved). Single nav entry; old route keys redirect to TrustCenter with `initialTab`. The AIInsights→Claims-Matrix `initialSection` anchor is forwarded to the Claims Matrix tab. Branch `story/STORY-112_trust_center_consolidation` (stacked on 113).
