# STORY-TAB-001 — Remediation tab response-contract fix

Stage: standard

## Lifecycle
- [x] discover   (skipped — subsystem audited end-to-end earlier this session; premise/evidence tables in specs/stories/STORY-TAB-001.md)
- [x] shape      (interview skipped — autonomous session per owner instruction "move to the contract fixes"; decisions defaulted + logged below)
- [x] preview    (skipped — no visual/design change: existing card layout retained; only data binding, field mapping, and the endpoint are corrected)
- [ ] plan
- [ ] build
- [ ] verify
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| `GET /api/v1/remediation` → `{traces, total, page, page_size, pages}` | yes | routers/remediation.py:513-589 |
| Trace fields: id, check_name, gate_name, result, reason, remediation_hint, regulation_ref, effort_estimate, domain, created_at | yes | routers/remediation.py:569-581 |
| `PATCH /api/v1/remediation/traces/{id}/remediate` requires body `{remediation_note}` (422 if blank) | yes | routers/remediation.py:168-186 (`RemediateTraceIn`) |
| Frontend reads `d.items`; PATCHes nonexistent `/remediation/{id}/complete` | yes | frontend/src/pages/Remediation.jsx:21,35 |
| Vitest + testing-library present; fetch-mock pattern in repo | yes | frontend/package.json:10, frontend/src/pages/ComplianceHub.test.jsx:13-34 |
| Story index gate scans `specs/stories/*INDEX*.md` (closed vocabulary, SHA evidence) | yes | scripts/check_story_index.py:25,39-41,164 |
| Prior open findings on Remediation.jsx | none found | quality/findings.md (grep "Remediation" — only backend/other-surface rows) |

## Decision Log

| Question | Answer (defaulted) | Architectural consequence |
|---|---|---|
| Backend requires a non-blank `remediation_note`; UI has no note input — collect one or change the backend? | Collect in UI. Clicking "Mark Complete" reveals an inline note textarea + Confirm/Cancel; PATCH sends `{remediation_note}`. Backend untouched. | Preserves the HITL evidence posture (note is audit evidence — an AuditEvent is written server-side); story stays frontend-only, no authz surface change → no security-auditor requirement triggered by backend edits. |
| Severity display: API has `result` (fail/warn/flagged/triggered), not `severity` | Map result→badge: fail→red (#dc2626), warn→amber (#ca8a04), flagged/triggered→neutral gray. Colors reused from the pre-existing palette. | Pure presentation mapping; no fabricated severity claim (badge shows the actual result word, color only groups it). |
| Pagination (page_size=50) | Indicator only: "showing N of M" when total > traces.length. No pager UI. | Matches story Out of Scope; avoids new API params. |
| Where does the story index row live? | New `specs/stories/STORY-TAB-INDEX.md` covering TAB-001..008 (SPECIFIED), TAB-001 → IMPLEMENTED w/ SHA in this PR. | Satisfies check_story_index.py + FM-4 (row changes in the implementing PR). |
| Regression pinning for the two bugs (always-empty list; dead endpoint) | Vitest contract-pin tests in Remediation.test.jsx + FND rows in quality/findings.md, pinned-by-frontend-test (precedent: FND-021/029/031/052). | Frontend bugs pin in vitest (fast tier); tests/regression/ stays backend-only per existing convention. |

## Deviations
- /story step-2 "wait for confirmation before implementing" and the 1b interview
  are collapsed into defaulted decisions above — autonomous session; owner
  pre-authorized proceeding to contract fixes. Conservative option chosen
  everywhere (frontend conforms to backend; no backend edits).
