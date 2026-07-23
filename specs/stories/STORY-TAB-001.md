# STORY-TAB-001: Remediation tab — fix response-contract mismatch so open findings actually render

**Status:** in-progress
**Screen/Area:** Remediation tab (frontend/src/pages/Remediation.jsx ↔ routers/remediation.py)

## Premise verification

| Referenced artifact | Evidence |
|---|---|
| `GET /api/v1/remediation` returns `{traces: [...], total, page, page_size, pages}` | routers/remediation.py:513-589 |
| Frontend reads `d.items` and therefore always renders the empty state | frontend/src/pages/Remediation.jsx:21 |
| "Mark Complete" PATCHes `/api/v1/remediation/{id}/complete` — no such route exists | frontend/src/pages/Remediation.jsx:35; canonical route is PATCH `/api/v1/remediation/traces/{trace_id}/remediate` (routers/remediation.py:168) |
| Live deployment confirms shape (`{"traces": [], "total": 0, ...}`) | probed 2026-07-23 with demo token |

## Goal
The Remediation tab currently shows "✓ No open remediation actions" unconditionally, because the page reads a response key the API never returns, and its Mark Complete button calls a nonexistent endpoint. After this story, the tab lists the tenant's open (unremediated) fail/warn traces with the fields the API actually provides, and Mark Complete drives the canonical remediate endpoint.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given `GET /api/v1/remediation` returns one or more entries in `traces`, When the Remediation tab loads, Then each trace renders as a card (the empty state is NOT shown).
- AC-2: Given a rendered trace card, Then it displays the API's real fields: `check_name` (title), `reason` (description), `remediation_hint` (guidance), `result` (severity badge: fail→high styling, warn→medium styling, other open results→neutral), `effort_estimate`, and `regulation_ref` when present.
- AC-3: Given the user clicks "Mark Complete" on a trace, When the request is issued, Then it calls `PATCH /api/v1/remediation/traces/{id}/remediate` (with whatever body that endpoint requires) and on success the list reloads and the trace no longer appears.
- AC-4: Given `traces` is empty (`total === 0`), Then the existing "no open remediation actions" empty state is shown.
- AC-5: Given the API responds non-2xx, Then the error banner is shown (no silent empty state).

## Edge Cases
- Trace missing `remediation_hint` / `regulation_ref` / `effort_estimate` → card renders without those rows, no "undefined" text.
- Remediate PATCH fails → surface an error (banner or inline), do not remove the card, button re-enables.
- Pagination: API returns `page_size=50`; if `total > traces.length`, show a count indicator ("showing X of Y") — full pagination UI is out of scope.

## Out of Scope
- Backend changes (the API contract is treated as canonical; frontend conforms to it).
- Jira issue creation flow, bulk remediation.
- Moving the tab under TRACE View (STORY-TAB-008).

## Non-Functional Requirements
- Vitest contract-pin test: mock fetch with the real response shape from routers/remediation.py and assert cards render — this test must fail against the pre-fix component.
- Standard project rules (no new hardcoded severity colors beyond the existing SEV_COLOR map).

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `Remediation.test.jsx`: "AC-1 / FND-073: renders a card per trace and no empty state when traces is non-empty" | Remediation.jsx, Remediation.test.jsx |
| AC-2 | `Remediation.test.jsx`: "AC-2: shows reason, guidance, result badge, effort, and regulation ref" + "warn result renders a WARN badge" | Remediation.jsx, Remediation.test.jsx |
| AC-3 | `Remediation.test.jsx`: "AC-3: Mark Complete reveals a note input; confirm PATCHes /traces/{id}/remediate and reloads" + "does not PATCH while the note is blank" (note is required by the backend — RemediateTraceIn) | Remediation.jsx, Remediation.test.jsx |
| AC-4 | `Remediation.test.jsx`: "AC-4: total === 0 renders the empty state" | Remediation.jsx, Remediation.test.jsx |
| AC-5 | `Remediation.test.jsx`: "AC-5: non-2xx renders the error banner, not the empty state" | Remediation.jsx, Remediation.test.jsx |

**Edge cases covered:** sparse trace (null optional fields) renders without
"undefined"/"null" and omits optional rows; failed PATCH keeps the card and
surfaces "Failed to mark as remediated"; `total > traces.length` shows
"Showing N of M open items" — all in `Remediation.test.jsx`.

**Finding:** FND-073 (quality/findings.md) — pinned by `frontend/src/pages/Remediation.test.jsx`
(red-first: 8/10 failed pre-fix), manifest entry `status: pinned`.
