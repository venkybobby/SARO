# STORY-111: Remove duplicate navigation/route aliases

**Status:** ready (⚠ removes alias routes/tabs; verify no live links break)
**Screen/Area:** frontend/src Sidebar/nav + routers/rule_packs.py API aliases

## Goal
Both the React nav and the API carry alias entries — multiple tab IDs/paths that render or return the same thing. Remove the redundant aliases, keeping one canonical entry each, so navigation and the API surface are unambiguous.

## Context (file:line)
- React `frontend/src/components/Sidebar.jsx` TAB_REGISTRY aliases (different tab ID → same page component):
  - `evidence_export` → `trace_view` page (dup of `trace_view`).
  - `vendor_risk` → `risk_summary` page (dup of `risk_summary`).
  - `dpa_governance` and `ir_plan` → both `governance_docs` page.
  - `demo_requests` registry entry appears orphaned (not in any persona tab list) — verify.
- Backend `routers/rule_packs.py` path aliases:
  - `/api/v1/rules/packs` vs `/api/v1/rule-packs` (`get_rule_packs_alias`, ~95-101).
  - `/api/v1/rules/drift-alerts` vs `/api/v1/drift/alerts` (`get_drift_alerts_alias`, ~104-110).
  - `/api/v1/rules/drift-alerts` vs `/api/v1/rules/drift-check` (Streamlit-compat dup, ~80-86).
- `main.py:56` registers the alias router.

## Decision Required (resolve at Definition-of-Ready)
Confirm the canonical keeper for each pair, and whether `vendor_risk`/`risk_summary` survives at all (STORY-113 merges Risk Summary into Risk Register — coordinate so 111 doesn't keep an alias 113 will delete). **Default canonicals:** keep `trace_view`, keep `risk_register` target (per 113), keep one `governance_docs` entry, keep `/api/v1/rules/packs` and `/api/v1/rules/drift-alerts`.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given the React nav, When this story completes, Then each page is reachable by exactly one tab ID; `evidence_export`, `vendor_risk`, and the duplicate of `dpa_governance`/`ir_plan` are removed (one canonical kept), and any persona referencing a removed alias is updated to the canonical.
- **AC-2:** Given the backend, When inspected, Then each logical endpoint has one canonical path; removed aliases (`/api/v1/rule-packs`, `/api/v1/drift/alerts`, `/api/v1/rules/drift-check`) no longer route, OR — if any client depends on them — they remain only as explicit, documented compat redirects, decided per alias.
- **AC-3:** Given the React API client (`frontend/src/.../saro.js`), When grepped, Then it calls only canonical paths (no removed alias).
- **AC-4:** Given the full suites, When `pytest tests/ -q` and `npm run build`/frontend tests run, Then nothing references a removed alias and all pass.

## Edge Cases
- An orphaned `demo_requests` registry entry — confirm reachability before deleting (coordinate with STORY-114).
- Removing a backend path that an external/integration client still calls — prefer keeping a documented redirect over a hard 404 where evidence of external use exists.

## Out of Scope
- Trust Center consolidation (STORY-112) and Risk Summary→Register merge (STORY-113), though both delete some of these same nav entries — sequence to avoid double-work/conflict.

## Non-Functional Requirements
- security-auditor review (touches routers/). Follow `.claude/skills/api-conventions`. No endpoint behavior change beyond alias removal.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_evidence_export_nav_alias_removed` | components/Sidebar.jsx |
| AC-2 | `test_backend_alias_router_removed`, `test_main_no_longer_registers_alias_router` | routers/rule_packs.py, main.py |
| AC-3 | `test_react_client_uses_canonical_rule_paths` | RulePacks.jsx, DriftAlerts.jsx, Dashboard.jsx |
| AC-4 | full unit/regression + p2 drift tests (repointed to canonical) + frontend build/94 tests | tests/, frontend/ |

**Status:** done (last in the batch). Most aliases were already removed by 112/113/114 (vendor_risk, dpa_governance, ir_plan, demo_requests). Removed the remaining `evidence_export` nav orphan; deleted the Streamlit-only `/drift-check` and the React-compat `_alias_router` (`/api/v1/rule-packs`, `/api/v1/drift/alerts`) + its main.py registration. **Chose full consolidation** (not keep-as-redirect): repointed the React client (RulePacks/DriftAlerts/Dashboard) and the backend drift tests to the canonical `/api/v1/rules/packs` and `/api/v1/rules/drift-alerts`. App imports cleanly (169 routes). Branch `story/STORY-111_remove_nav_aliases` (stacked on 114).
