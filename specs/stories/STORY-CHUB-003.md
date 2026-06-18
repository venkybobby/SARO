STORY-CHUB-003: Recent Audits — fix risk-score field mapping (always "—" bug)
Status: ready    Screen/Area: Compliance Hub
Epic: GRC-Compliance-Hub · Priority: P0 · Depends on: STORY-CHUB-002

Goal
In the Compliance Hub "Recent Audits" table, each row reads `a.risk_score`, but the `/api/v1/audits` response (`AuditListItemOut` in `schemas.py`, populated in `routers/scan.py:list_audits`) exposes the field as `overall_risk_score`. The key never matches, so `RiskBadge` never renders and the Risk Score column shows "—" for every row even when data exists. Map the correct field.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 17 (accurate record-keeping display).
- NIST AI RMF: MEASURE (risk metrics must be truthfully surfaced).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given an audit row in `frontend/src/pages/ComplianceHub.jsx`, When the Risk Score cell renders, Then it reads `a.overall_risk_score` (with `a.risk_score` retained only as a defensive fallback), and passes it to `RiskBadge`.
AC-2: Given an audit with `overall_risk_score = 0.41`, When rendered, Then `RiskBadge` shows 41 with amber styling per the existing thresholds (≥70 red, ≥40 amber, else green).
AC-3: Given an audit with a null/absent risk score, When rendered, Then the cell shows "—" (legitimate empty), not a zero badge.

Edge Cases
- `overall_risk_score` of exactly 0 (genuine, computed) renders a green "0" badge — distinct from null → "—".
- Score already in 0–1 range is multiplied ×100 once (existing `RiskBadge` behavior) — confirm no double-scaling.

Out of Scope
- Backend changes to `/api/v1/audits` (frontend mapping only).
- Role-gate fix (STORY-CHUB-002).

Non-Functional Requirements
- No change to `RiskBadge` thresholds or color tokens.

Test Requirements
- Frontend unit (`ComplianceHub.test.jsx`): `overall_risk_score=0.41` → "41" amber; null → "—"; 0 → "0" green; legacy `risk_score` fallback still works.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	ComplianceHub.test.jsx "AC-1: legacy a.risk_score fallback still renders"	frontend/src/pages/ComplianceHub.jsx (score = a.overall_risk_score ?? a.risk_score)
AC-2	ComplianceHub.test.jsx "AC-2: overall_risk_score=0.41 renders 41 (amber)"	frontend/src/pages/ComplianceHub.jsx
AC-3	ComplianceHub.test.jsx "AC-3: null/absent → '—'" + "edge: genuine 0 → '0' badge"	frontend/src/pages/ComplianceHub.jsx
