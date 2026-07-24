# STORY-TAB-007 — AIMS honest fields (no fabricated model metadata)

Stage: standard

## Lifecycle
- [x] discover   (skipped — endpoint/model/consumer audited this session; premise table in specs/stories/STORY-TAB-007.md)
- [x] shape      (interview skipped — autonomous session; decisions defaulted + logged below)
- [x] preview    (skipped — same card grid; fabricated badges removed, real fields bound)
- [x] plan
- [ ] build
- [ ] verify
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| `GET /api/v1/aims/models` hardcodes `risk_tier:"high"`, `lifecycle_stage:"production"` | yes | routers/aims.py:76-77 |
| `framework_coverage` is ALSO a hardcoded constant `["ISO-42001","EU-AI-ACT-2024"]` | yes | routers/aims.py:78 — story AC-2 listed it as renderable; it is fabricated too |
| AIMSDocument has NO status/lifecycle/risk column (id, tenant_id, title, version, effective_date, owner_email, linked_audit_ids, created_at, updated_at) | yes | models.py:1065-1095 |
| Frontend reads `vendor`/`risk_category`/`last_audit_date` — never returned | yes | frontend/src/pages/Aims.jsx:56-63 |
| Note string mojibake on live deployment (`â€"`) | yes | live probe 2026-07-23; routers/aims.py:87 em-dash literal |

## Decision Log

(format: question → defaulted answer → architectural consequence)

| Question | Answer (defaulted) | Architectural consequence |
|---|---|---|
| `lifecycle_stage` from stored data? | No column exists → omit the field entirely (AC-1's verify-in-BUILD branch). No default badge of any kind renders. | Adding a real lifecycle model = follow-up story with a migration (story Out of Scope). |
| `framework_coverage` — AC-2 says render as tags, but it's a hardcoded constant | Remove from the response too (same fabricated-evidence class as risk_tier/lifecycle_stage). AC-2's tag rendering becomes conditional: renders only if the API ever returns real data. | Deviation from AC-2's letter, aligned with the story's stated goal ("SARO's compliance posture forbids presenting fabricated values as evidence"). Logged under Deviations. |
| Mojibake fix | Replace the em-dash in the `note` literal with an ASCII hyphen (AC-5). | Deployment-encoding-proof. |

## Deviations
- `framework_coverage` removed from the API response (AC-2 listed it as a real
  renderable field; premise check showed it is a hardcoded constant — the exact
  defect class this story exists to remove). Frontend renders coverage tags
  only when the field is present, so a future real implementation lights up
  without a frontend change.
