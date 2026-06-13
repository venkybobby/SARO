# STORY-113: Merge Risk Summary into the Risk Register

**Status:** ready
**Screen/Area:** frontend/src — RiskSummary.jsx, RiskRegister.jsx + nav

## Goal
"Risk Summary" and "Risk Register" are two separate React pages covering overlapping ground. Merge Risk Summary's board-level view (KPIs, trend, top findings, vendor risk) into the Risk Register as a summary header/section above the existing register table, then retire the standalone Risk Summary page and its nav entries.

## Context (file:line)
- `RiskSummary.jsx` (route `risk_summary`, nav "Risk Summary" Sidebar.jsx:46 + alias "Vendor Risk" Sidebar.jsx:47) — KPI cards (Overall RAG, 90-day trend, remediation %, open findings, avg risk score), Top Findings table, Vendor Risk grid, Board PDF export; APIs `/api/v1/risk_dashboard`, `/api/v1/audits`, `/api/v1/vendor-risk`, `/api/v1/risk/board-export`.
- `RiskRegister.jsx` (route `risk_register`, nav Sidebar.jsx:64) — searchable/filterable/sortable risk table, bulk actions, pagination; APIs `/api/v1/risks`, `/api/v1/risks/bulk`, `/api/v1/risks/{id}`; links to `risk_detail`/`risk_form`.
- Access: both risk_officer, admin, super_admin.

## Decision Required (resolve at Definition-of-Ready)
Confirm layout. **Default:** Risk Register gains a collapsible summary band at the top (KPIs + trend + board export), Top Findings and Vendor Risk become sections/tabs within the Register; the register table remains the primary interaction. The `risk_summary` route is removed (redirect to `risk_register`).

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given Risk Summary's content, When merged, Then the Risk Register page renders the KPI cards, 90-day trend, remediation %, open findings, avg risk score, Top Findings, Vendor Risk, and Board PDF export — all calling the same APIs — alongside the existing register table.
- **AC-2:** Given the nav, When merged, Then the `risk_summary` tab and the "Vendor Risk" alias entry are removed from `TAB_REGISTRY`/`PERSONA_TABS`, and `risk_register` is the single entry.
- **AC-3:** Given any deep-link or `onNavigate("risk_summary", …)` call, When invoked, Then it resolves to the Risk Register (no fall-through to Dashboard — guard against FND-007), and `App.jsx` `PAGE_COMPONENTS` drops `risk_summary`/lazy import.
- **AC-4:** Given persona access, When a risk_officer/admin/super_admin loads the page, Then they see the merged Register with the summary band; nobody loses access they had.
- **AC-5:** Given the frontend suite/build, When run, Then it passes with `RiskSummary.jsx` removed (or absorbed) and existing Register tests still green.

## Edge Cases
- Board PDF export (`/api/v1/risk/board-export`) must still work from its new location.
- The "Vendor Risk" alias is also targeted by STORY-111 — coordinate so removal happens once.
- Preserve the Register's existing search/filter/bulk/sort/pagination behavior unchanged.

## Out of Scope
- Trust Center consolidation (STORY-112).
- Backend risk API changes.

## Non-Functional Requirements
- Preserve mobile/responsive behavior (the Register has card-based mobile layout). Keep accessibility intact.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `RiskRegister.test.jsx` STORY-113 test (board band + Export Board PDF + Overall RAG render) | RiskRegister.jsx, RiskSummary.jsx |
| AC-2 | Sidebar TAB_REGISTRY/PERSONA_TABS no longer list risk_summary/vendor_risk | components/Sidebar.jsx |
| AC-3 | App PAGE_COMPONENTS maps `risk_summary → RiskRegister` (redirect, guards FND-007) | App.jsx |
| AC-4/AC-5 | full vitest suite 90 passed + `vite build` green | frontend/ |

**Status:** done. RiskSummary embedded as a collapsible board-view band atop RiskRegister (added `embedded` prop to drop page chrome); preserves KPIs, 90-day sparkline, Top Findings, Vendor Risk, and Board PDF export with the same APIs. Removed the standalone route + nav entries (incl. the `vendor_risk` alias). Branch `story/STORY-113_merge_risk_summary_into_register` (stacked on 106).
