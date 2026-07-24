# STORY-TAB-005: Drift Alerts tab — render the framework-version grid from the real drift response

**Status:** ready
**Screen/Area:** Drift Alerts tab (frontend/src/pages/DriftAlerts.jsx ↔ routers/rule_packs.py)

## Premise verification

| Referenced artifact | Evidence |
|---|---|
| `GET /api/v1/rules/drift-alerts` returns `{alerts, alert_count, current_versions: {fw: ver}, latest_known_versions: {fw: ver}, checked_at}` | routers/rule_packs.py:46-77 |
| Alert objects carry `framework`, `current_version`, `latest_version`, `alert_type`, `message` — no `what_changed` / `affected_rule_packs` | services/rule_service.py:59-72 |
| Frontend reads `data.framework_versions` (array) → version grid never renders | frontend/src/pages/DriftAlerts.jsx:20,37-52 |
| Live deployment confirms shape (grid absent, alerts empty) | probed 2026-07-23 with demo token |

## Goal
The "Current Framework Versions" grid on Drift Alerts never renders because the page reads a key the API doesn't return. After this story the grid is built by merging `latest_known_versions` (all frameworks SARO tracks) with `current_versions` (frameworks that have an active rule pack), so the tab always shows meaningful state — including which tracked frameworks have no pack at all — and alert cards render only fields that exist.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the API response, Then one version card renders per framework in `latest_known_versions`, showing the pack's `current_versions` entry (or "no pack" when absent) and the latest known version when it differs.
- AC-2: Given `alerts` contains entries, Then each alert card renders `message` (or the framework/current/latest composition) without referencing `what_changed` / `affected_rule_packs` (those blocks are removed, not left as dead code).
- AC-3: Given `alerts` is empty and the request succeeded, Then the "no drift" state renders together with `checked_at` ("last checked ...") so the green state is evidently fresh, not static.
- AC-4: Given the API returns non-2xx, Then the error banner renders and no stale "no drift" reassurance is shown.

## Edge Cases
- Framework present in `current_versions` but not in `latest_known_versions` → still shown in the grid (no silent drops).
- Empty `latest_known_versions` → neutral empty state, not a blank section.

## Out of Scope
- Making FRAMEWORK_VERSIONS dynamic (live regulatory feeds) — separate product decision.
- Merging Drift Alerts into Rule Packs (STORY-TAB-008).

## Non-Functional Requirements
- Vitest contract-pin test with the exact backend shape (incl. a framework with no pack); must fail pre-fix.
- Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
