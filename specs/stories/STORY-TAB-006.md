# STORY-TAB-006: Rule Packs tab — fetch pack detail so rules actually display (no more "0 rules")

**Status:** done
**Screen/Area:** Rule Packs tab (frontend/src/pages/RulePacks.jsx ↔ routers/rule_packs.py, services/rule_service.py)

## Premise verification

| Referenced artifact | Evidence |
|---|---|
| `GET /api/v1/rules/packs` list items carry `rule_count` but NOT a `rules` array | services/rule_service.py:17-38 |
| `GET /api/v1/rules/packs/{framework}` returns the full pack including `rules` | routers/rule_packs.py:33-43, services/rule_service.py:41-46 (`get_pack_by_name`) — NOTE: get_pack_by_name currently returns the same summary dict as the list; the full-pack load path must be verified/added in BUILD |
| Frontend renders `pack.rules?.length || 0` → every pack shows "0 rules", detail pane never lists rules | frontend/src/pages/RulePacks.jsx:50,83-101 |
| Live deployment: packs exist (EU AI Act rule_count=3, NIST rule_count=6) but UI would show 0 | probed 2026-07-23 with demo token |

## Goal
Rule Packs is SARO's transparency surface — an auditor should see exactly which rules a pack applies. Today every pack shows "0 rules" and an empty detail pane because the list endpoint intentionally returns only `rule_count`, while the UI expects inline `rules`. After this story the list shows the real `rule_count`, and selecting a pack fetches its detail (including the rules array) from the per-pack endpoint.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the pack list response, Then each list card shows `rule_count` ("N rules") from the API field, not `rules.length`.
- AC-2: Given the user selects a pack, When the detail loads, Then the component fetches `GET /api/v1/rules/packs/{framework}` and renders the pack's rules (id, severity, description) from that response. If the backend's `get_pack_by_name` does not currently include `rules`, extend it to return the full loaded pack (read-only change; no schema/YAML edits).
- AC-3: Given the detail fetch is in flight, Then the pane shows a loading state; given it fails, an error state (list stays usable).
- AC-4: Given a pack, Then the detail header shows name, version, framework, `status`, and `last_updated`; the changelog entries returned by the API are rendered (version, date, changes).
- AC-5: Given a rule without a `severity`, Then it renders with the existing "medium" default (regression guard on current behavior).

## Edge Cases
- Pack YAML fails to load server-side (list skips it) → detail 404 → error state, no crash.
- Rapid selection switching → stale responses must not overwrite the newer selection (guard by selected framework id).

## Out of Scope
- Rule pack editing/versioning UI.
- Absorbing Drift Alerts into this tab (STORY-TAB-008).

## Non-Functional Requirements
- rule_packs/ YAML files untouched (rule-pack-edit skill constraints not triggered).
- Vitest: list shows rule_count; detail fetch renders rules (mocked two-endpoint flow). pytest: if `get_pack_by_name` changes, pin that `/packs/{framework}` includes `rules`.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `RulePacks.test.jsx`: "renders 'N rules' from rule_count, never 0-from-missing-array"; backend `test_list_endpoint_stays_light` | RulePacks.jsx, RulePacks.test.jsx, tests/test_tab006_rule_pack_detail.py |
| AC-2 | `RulePacks.test.jsx`: "fetches /rules/packs/{framework} and lists rule ids + severities"; backend `test_get_pack_by_name_includes_rules` + `test_detail_endpoint_serves_rules` | services/rule_service.py, RulePacks.jsx, both test files |
| AC-3 | `RulePacks.test.jsx`: "detail failure shows an error in the pane; the list stays usable" (+ loading state rendered while in flight) | RulePacks.jsx, RulePacks.test.jsx |
| AC-4 | `RulePacks.test.jsx`: header shows name/version/framework/status/last_updated; changelog entries rendered | RulePacks.jsx, RulePacks.test.jsx |
| AC-5 | `RulePacks.test.jsx`: "a rule without severity renders the medium default" | RulePacks.jsx, RulePacks.test.jsx |

**Edge cases covered:** stale-response guard on rapid selection switching
(slow EU response never overwrites the newer NIST detail) in `RulePacks.test.jsx`;
detail 404/500 → error state without crashing (same AC-3 case).

**Finding:** FND-081 (quality/findings.md) — pinned red-first (backend 2/3,
frontend 5/5 failed pre-fix); two manifest entries (frontend + backend halves).
