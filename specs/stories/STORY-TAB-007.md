# STORY-TAB-007: AIMS tab — stop rendering fabricated model metadata; show only real registry fields

**Status:** done
**Screen/Area:** AIMS tab (frontend/src/pages/Aims.jsx ↔ routers/aims.py)

## Premise verification

| Referenced artifact | Evidence |
|---|---|
| `GET /api/v1/aims/models` hardcodes `risk_tier: "high"` and `lifecycle_stage: "production"` for every model | routers/aims.py:76-77 (comment admits "default — override once risk_tier column added") |
| API returns `model_id, name, version, effective_date, owner_email, linked_audit_count, framework_coverage, created_at` | routers/aims.py:64-81 |
| Frontend reads `vendor`, `risk_category`, `last_audit_date` — none returned; renders hardcoded stage as if real | frontend/src/pages/Aims.jsx:56-63 |
| Live deployment confirms shape (`models: []` for demo tenant) | probed 2026-07-23 with demo token |

## Goal
AIMS is an ISO 42001 evidence surface; SARO's compliance posture forbids presenting fabricated values as evidence. Today every registered model would display "PRODUCTION" stage and an implied high risk tier that no one ever recorded. After this story, the API stops emitting hardcoded classification fields, and the tab renders exactly the lifecycle facts that exist: version, effective date, owner, linked audit evidence count, and framework coverage tags.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the models endpoint, Then `risk_tier` and `lifecycle_stage` are removed from the response (not defaulted). If AIMSDocument has a real status/lifecycle column, it may be surfaced under `lifecycle_stage` — only from stored data, never a constant. (Verify the model's columns in BUILD; if none exists, omit the field.)
- AC-2: Given a rendered model card, Then it shows `name`, `version`, `owner_email`, `effective_date`, `linked_audit_count` ("N linked audit(s)"), and `framework_coverage` as tags — and no longer references `vendor`, `risk_category`, or `last_audit_date`.
- AC-3: Given a model with no stored lifecycle value, Then no stage badge renders (no default badge of any kind).
- AC-4: Given zero models, Then the existing empty state renders, and it names the concrete next action (register via AIMS documents API / Compliance Hub) rather than a bare "register via the API".
- AC-5: Given the endpoint's `note` string, Then its text renders/transports without mojibake (replace the em-dash literal that currently arrives as `â€"` on the live deployment with plain ASCII).

## Edge Cases
- `framework_coverage` empty/missing → no tag row.
- `effective_date` null → row omitted.

## Out of Scope
- Adding a real risk_tier/lifecycle column + migration (needs product definition of the lifecycle model — follow-up story).
- AIMS document CRUD UI.

## Non-Functional Requirements
- Compliance-guard: response and UI copy must stay evidence-language-only (no certification claims) — the existing "Audit evidence for ISO 42001 document lifecycle review" footer is retained.
- pytest: pin the models response contains no hardcoded classification fields; vitest: card renders real fields, no "undefined"/fabricated badges.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_tab007_aims_models_honest_fields.py::test_no_fabricated_classification_fields` — AIMSDocument verified to have NO status/lifecycle column (models.py:1065-1095), so the fields are omitted, never defaulted | routers/aims.py, tests/test_tab007_aims_models_honest_fields.py |
| AC-2 | backend `test_real_fields_survive`; frontend `Aims.test.jsx` "shows name, version, owner, effective date, and linked-audit count" + "renders NO stage badge and no vendor/risk-category/last-audit rows" | routers/aims.py, Aims.jsx, both test files |
| AC-3 | `Aims.test.jsx`: no stage badge for models without stored lifecycle data (badge logic renders only from a present field) | Aims.jsx, Aims.test.jsx |
| AC-4 | `Aims.test.jsx`: empty state names POST /api/v1/aims/documents / Compliance Hub | Aims.jsx, Aims.test.jsx |
| AC-5 | backend `test_note_has_no_mojibake_prone_chars` (note is ASCII-only) | routers/aims.py, tests/test_tab007_aims_models_honest_fields.py |

**Edge cases covered:** sparse model (null dates, 0 audits) renders cleanly, no
"undefined"/"null"; tenant scoping regression-guarded
(`test_tenant_scoping_unchanged`). Compliance-guard NFR: ISO 42001
evidence-language footer retained (pinned in `Aims.test.jsx`).

**Logged deviation:** `framework_coverage` was ALSO a hardcoded constant
(routers/aims.py:78) — removed with the other fabricated fields; the frontend
renders coverage tags only if the API ever returns real data. See
implementation-notes.md ## Deviations.

**Finding:** FND-082 (quality/findings.md) — pinned red-first (backend 2/4,
frontend 4/6 failed pre-fix); two manifest entries (backend + frontend halves).
