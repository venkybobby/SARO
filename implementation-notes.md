# STORY-TAB-005 — Drift Alerts renders the real drift response

Stage: standard

## Lifecycle
- [x] discover   (skipped — endpoint + consumer audited this session; premise table in specs/stories/STORY-TAB-005.md)
- [x] shape      (interview skipped — autonomous session; decisions defaulted + logged below)
- [x] preview    (skipped — same card grid; bindings corrected, dead sections removed)
- [x] plan
- [x] build      (implemented; gates green -- see PR)
- [x] verify     (batch change-debrief.html for STORY-TAB-001..007 -- committed on story/STORY-TAB-001, PR #128)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| `GET /api/v1/rules/drift-alerts` → `{alerts, alert_count, current_versions:{fw:ver}, latest_known_versions:{fw:ver}, checked_at}` | yes | routers/rule_packs.py:46-77; live probe 2026-07-23 |
| Alert dict: `{framework, current_version, latest_version, alert_type, message}` — no what_changed / affected_rule_packs | yes | services/rule_service.py:59-72 |
| Frontend reads `data.framework_versions` (array) → grid never renders; alert cards reference the two phantom lists | yes | frontend/src/pages/DriftAlerts.jsx:20,37-52,71-86 |

## Decision Log

(format: question → defaulted answer → architectural consequence)

| Question | Answer (defaulted) | Architectural consequence |
|---|---|---|
| Grid source | Merge keys of `latest_known_versions` ∪ `current_versions` → one card per framework: current pack version (or "no pack"), latest shown when it differs. | Tracked-but-packless frameworks (AIGP, ISO-42001 on the live deployment) become visible instead of silently absent — that IS the coverage signal. |
| Alert card body | Render `message` + framework/current→latest line; delete the what_changed / affected_rule_packs blocks (fields have never existed). | No dead code paths; no implied change-analysis capability the backend doesn't have. |
| "No drift" freshness | Green state renders `checked_at` ("Last checked …") so the reassurance is evidently a fresh computation, not static copy. | Anti-overclaim: an unverifiable green state is the FND-030 class. |

## Deviations
None yet.
