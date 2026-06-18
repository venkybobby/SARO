STORY-TRACE-006: Add signed evidence export actions (JSON + PDF)
Status: ready    Screen/Area: TRACE View
Epic: GRC-TRACE-View · Priority: P1 · Depends on: STORY-TRACE-002, STORY-TRACE-003

Goal
The signed evidence bundle is the AI Auditor's actual deliverable, and the endpoints exist — `GET /api/v1/audit/{id}/export/json` and `/export/pdf` (`routers/trace_view.py:148,189`), producing an HMAC-signed, timestamped export — but the TRACE View has no way to trigger them. Add export actions so the auditor can pull evidence for the audit file directly from the screen.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 17 (export of record-keeping / QMS evidence).
- NIST AI RMF: MANAGE (evidence retained for the audit file).
- ISO/IEC 42001: document-lifecycle linking (exported artifact tied to its audit).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a loaded trace in `TraceView.jsx`, When the header renders, Then "Export JSON" and "Export PDF" actions are shown.
AC-2: Given "Export PDF" is clicked, When it succeeds, Then the signed PDF from `/api/v1/audit/{id}/export/pdf` downloads with its server-provided filename.
AC-3: Given "Export JSON" is clicked, When it succeeds, Then the signed JSON (including `_signature`/timestamp) from `/export/json` downloads.
AC-4: Given an export returns non-200 (e.g. 403/404), When it returns, Then a visible inline error is shown and no empty/corrupt file is saved.
AC-5: Given no trace is loaded, When the screen renders, Then export actions are disabled.

Edge Cases
- Cross-tenant/forbidden audit → 404/403 surfaced as a message, never a download (relies on STORY-TRACE-002/003).
- Large exports stream to download rather than buffering fully in memory.

Out of Scope
- Changing the export payload or signing mechanism.
- Bulk/multi-audit export.

Non-Functional Requirements
- Uses the existing auth-header fetch pattern; consistent with the shared design-system buttons (aligns with STORY-TRACE-009).

Test Requirements
- Frontend unit (`TraceView.test.jsx`): JSON/PDF actions issue correct requests; 403/404 → message, no download; no-trace → disabled.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
