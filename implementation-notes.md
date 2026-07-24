# STORY-TAB-006 — Rule Packs detail fetch (rules actually display)

Stage: standard

## Lifecycle
- [x] discover   (skipped — endpoint/service/consumer audited this session; premise table in specs/stories/STORY-TAB-006.md)
- [x] shape      (interview skipped — autonomous session; decisions defaulted + logged below)
- [x] preview    (skipped — same master/detail layout; detail now loads real rules on select)
- [x] plan
- [x] build      (implemented; gates green -- see PR)
- [x] verify     (batch change-debrief.html for STORY-TAB-001..007 -- committed on story/STORY-TAB-001, PR #128)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| List endpoint returns `rule_count`, never `rules` | yes | services/rule_service.py:26-35 |
| Detail endpoint `GET /api/v1/rules/packs/{framework}` exists but `get_pack_by_name` returns the same summary (NO rules) | yes | routers/rule_packs.py:33-43; services/rule_service.py:41-46 |
| `get_pack_by_name`'s only caller is the detail route → adding `rules` is additive and safe | yes | grep: routers/rule_packs.py:40 (sole caller) |
| Frontend renders `pack.rules?.length \|\| 0` → "0 rules" always; detail pane never lists rules | yes | frontend/src/pages/RulePacks.jsx:50,83-101 |
| Live packs exist (EU AI Act rule_count=3, NIST rule_count=6) | yes | live probe 2026-07-23 |

## Decision Log

(format: question → defaulted answer → architectural consequence)

| Question | Answer (defaulted) | Architectural consequence |
|---|---|---|
| Where do rules come from? | Extend `get_pack_by_name` to merge the summary fields with the full pack's `rules` list (read-only; YAML untouched; additive key, sole caller is the detail route). Frontend fetches `/rules/packs/{framework}` on select. | Two-endpoint master/detail; the list stays light. |
| Stale-response race on rapid selection | Detail effect keyed on the selected framework; response applied only if it matches the currently-selected framework (guard). | No stale detail overwrite. |
| Detail failure | Error state in the pane; list stays usable. | AC-3. |

## Deviations
None yet.
