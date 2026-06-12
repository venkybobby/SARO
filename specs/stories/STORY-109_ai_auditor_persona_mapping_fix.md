# STORY-109: Fix AI Auditor Persona Mapping — Add Transparency Artifacts, Resolve Read-Only Contradiction
Status: ready
Screen/Area: RBAC / Persona→Tab Mapping (`Sidebar.jsx`, `auth.py:223`)

## Goal
The deal-killer persona cannot see How SARO Reasons, Claims Matrix, or the citation inventory — the exact artifacts built to survive auditor interrogation — while it CAN see Upload & Scan despite `auth.py:223` declaring ai_auditor "a read-only persona." Both directions are wrong. Give the auditor the transparency surfaces; remove (or formally justify) the write-capable surface.

GRC mapping: EU AI Act Art. 13 (transparency to those assessing the system); ISO/IEC 42001 A.8; Epic 9 PER-00x persona matrix integrity; least-privilege (SOC 2 CC6.x).

## Acceptance Criteria (Given/When/Then)
- AC-1: Given a user with role `ai_auditor`, When they load the sidebar, Then `how_saro_reasons`, `claims_matrix`, and the citation inventory page are visible and accessible.
- AC-2: Given role `ai_auditor`, When they attempt any route or API endpoint with write semantics (upload, scan trigger, edit), Then the backend returns 403 — enforcement at API layer, not just nav hiding.
- AC-3: Given the Upload & Scan tab decision, When resolved, Then EITHER it is removed from ai_auditor's mapping OR an ADR documents the written justification and `auth.py`'s "read-only" declaration is amended to match — code and declaration may not contradict.
- AC-4: Given the Persona→Tab Mapping Matrix (Epic 9 doc), When updated, Then the doc, `Sidebar.jsx`, and backend authorization rules all agree, verified by an RBAC parity test.
- AC-5: Given the regression suite, When run, Then per-persona route-access tests cover every (persona, tab) pair in the matrix.

## Edge Cases
- TRACE View deep links shared by other personas to an auditor → must respect auditor read-only scope.
- Citation inventory page may not exist as a standalone route yet → if so, scope here is mapping only; page creation gets its own story.

## Out of Scope
- Trust Center consolidation (STORY-112) — apply this mapping fix to current pages; re-map after consolidation.

## Non-Functional Requirements
- All denied write attempts by ai_auditor logged to the immutable audit trail. Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
