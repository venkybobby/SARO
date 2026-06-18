STORY-TRACE-007: Fix Recent Traces (role gate + risk-score field) in TRACE View
Status: ready    Screen/Area: TRACE View
Epic: GRC-TRACE-View · Priority: P1 · Depends on: STORY-TRACE-003
Overlap: shares the audits-list role gate with STORY-CHUB-002 / STORY-TRACE-003 (backend), and the `overall_risk_score` field issue with STORY-CHUB-003 (but in a different file — `TraceView.jsx` has its own copy of the bug).

Goal
The TRACE View "Recent Traces" strip calls `/api/v1/audits?limit=10&sort=desc` and reads `a.risk_score`. Two defects: (1) the audits endpoint is role-gated so the `ai_auditor` persona gets an empty list (resolved at the backend by STORY-TRACE-003); (2) the score chips read `a.risk_score`, but the endpoint returns `overall_risk_score`, so chips show no score. Fix the field mapping in `TraceView.jsx` and confirm the recent list populates for the auditor once access is granted.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 17 (accurate display of audit records).
- NIST AI RMF: MEASURE (risk metric shown truthfully).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a recent-trace chip in `frontend/src/pages/TraceView.jsx`, When it renders a score, Then it reads `a.overall_risk_score` (with `a.risk_score` retained only as a defensive fallback).
AC-2: Given a score present, When the chip renders, Then the color thresholds match the rest of the screen (≥70 red, ≥40 amber, else green).
AC-3: Given an `ai_auditor` (post STORY-TRACE-003), When the screen loads, Then Recent Traces populates with that tenant's audits (no silent empty).
AC-4: Given the audits request fails, When the strip renders, Then it degrades gracefully (the strip is a convenience feature) without breaking the rest of the page.

Edge Cases
- Null score → chip omits the number (no "0" or "NaN").
- Empty tenant → legitimate "no recent traces" state, distinct from an access failure.

Out of Scope
- Backend role-gate change (STORY-TRACE-003).
- Compliance Hub's own copy of the field bug (STORY-CHUB-003).

Non-Functional Requirements
- No double-scaling of `overall_risk_score` (0–1 → ×100 once).

Test Requirements
- Frontend unit (`TraceView.test.jsx`): `overall_risk_score=0.55` → "55" amber; null → no number; legacy `risk_score` fallback works; fetch failure leaves the page functional.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
