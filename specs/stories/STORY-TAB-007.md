# STORY-TAB-007: AIMS tab — stop rendering fabricated model metadata; show only real registry fields

**Status:** ready
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
