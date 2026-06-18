STORY-CHUB-006: Compliance Hub actions — export, board report, and drill-throughs
Status: ready    Screen/Area: Compliance Hub
Epic: GRC-Compliance-Hub · Priority: P1 · Depends on: STORY-CHUB-001, STORY-CHUB-002

Goal
The Compliance Hub is a read-only status wall: nothing is clickable, and the persona's core jobs — export evidence, generate a board report, drill into a framework or audit — have no entry point, even though the endpoints already exist (`GET /api/v1/compliance-matrix/export` CSV; `GET /api/v1/risk/board-export`). Add an actions row and drill-through navigation so the screen becomes a workspace, not a poster.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 17 (export of record-keeping/QMS evidence).
- NIST AI RMF: MEASURE/MANAGE (acting on coverage and findings).
- ISO/IEC 42001: document-lifecycle linking (navigation from coverage → matrix rows).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the Compliance Hub header in `frontend/src/pages/ComplianceHub.jsx`, When it renders, Then it shows an "Export matrix (CSV)" action that triggers `GET /api/v1/compliance-matrix/export` and downloads the file.
AC-2: Given the same header, When it renders, Then it shows a "Generate board report" action that triggers the existing board-export endpoint (`GET /api/v1/risk/board-export`) and downloads the PDF.
AC-3: Given a framework card in the EVF Validation Status section, When clicked, Then it navigates to the Compliance Matrix view filtered to that framework (via the existing `onNavigate`/router pattern used elsewhere).
AC-4: Given a row in Recent Audits, When clicked, Then it navigates to that audit's TRACE/detail view by audit id.
AC-5: Given an export action fails (non-200), When it returns, Then a visible inline error is shown and no empty/corrupt file is downloaded.

Edge Cases
- Matrix export over the server row limit returns 413 — surface the server's "apply filters" message, do not download.
- Board export when there is "No data" (per `get_board_summary`) → disable the action with a tooltip rather than producing an empty PDF.
- TRACE drill-through respects the ADR-004 TRACE gate (the "How SARO Reasons" doc requirement) — link is present but the destination enforces its own gate; this story does not bypass it.

Out of Scope
- Building the Compliance Matrix filtered view itself (assumed to exist / separate screen).
- New export formats.

Non-Functional Requirements
- Actions use the existing auth header pattern; downloads stream (no full-buffer in memory on the client).
- Buttons use the shared design-system button (aligns with STORY-CHUB-007).

Test Requirements
- Frontend unit (`ComplianceHub.test.jsx`): export click issues the correct request; 413 → message, no download; framework click calls navigate with framework filter; audit click calls navigate with audit id; board "No data" → disabled.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	ComplianceHub.test.jsx "AC-1: Export matrix (CSV) issues GET /compliance-matrix/export"	frontend/src/pages/ComplianceHub.jsx (downloadFile + actions row)
AC-2	ComplianceHub.test.jsx "AC-2: Generate board report issues GET /risk/board-export"	frontend/src/pages/ComplianceHub.jsx
AC-3	ComplianceHub.test.jsx "AC-3: clicking a framework card navigates..."	frontend/src/pages/ComplianceHub.jsx (onNavigate coverage_gap + {framework}); destination filtered view out of scope per story
AC-4	ComplianceHub.test.jsx "AC-4: clicking an audit row navigates to its TRACE view"	frontend/src/pages/ComplianceHub.jsx (onNavigate trace_view, auditId); trace gate enforced by destination
AC-5	ComplianceHub.test.jsx "AC-5 / 413: export failure shows inline error and downloads nothing"	frontend/src/pages/ComplianceHub.jsx (downloadFile non-200 path); board disabled-on-no-data edge tested
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
