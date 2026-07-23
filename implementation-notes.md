# STORY-TAB-003 — Coverage Gap field alignment with the coverage API

Stage: standard

## Lifecycle
- [x] discover   (skipped — endpoint + consumer audited this session; premise table in specs/stories/STORY-TAB-003.md)
- [x] shape      (interview skipped — autonomous session; decisions defaulted + logged below)
- [x] preview    (skipped — same card/list layout; only field bindings + a summary row change)
- [x] plan
- [ ] build
- [ ] verify
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| `GET /api/v1/compliance-matrix/coverage` → `{frameworks:[{framework,total_rules,covered,partial,not_covered,coverage_pct,last_updated}], overall_coverage_pct, framework_count, total_rules}` | yes | routers/compliance_matrix.py:174-207; live probe 2026-07-23 (AIGP 0%, ISO 42001 0%) |
| Frontend reads `fw.name`/`fw.gaps`/`fw.gaps_count`/`fw.controls_covered`/`fw.controls_total` — none exist | yes | frontend/src/pages/CoverageGap.jsx:47,56,62,77-98 |
| ComplianceHub already consumes this endpoint correctly (`fw.framework`) — reference implementation | yes | frontend/src/pages/ComplianceHub.test.jsx:36-45 (COVERAGE_3FW fixture) |

## Decision Log

(format: question → defaulted answer → architectural consequence)

| Question | Answer (defaulted) | Architectural consequence |
|---|---|---|
| "Gap" semantics without a per-rule gap endpoint | `not_covered` (and `partial`) counts ARE the gap signal: detail shows "N of M rules not covered" + a covered/partial/not-covered breakdown. No fabricated per-control gap list. | Honest rendering of what the API measures; per-rule drill-down stays a backend follow-up (story Out of Scope). |
| Selection state keyed how? | By `fw.framework` string (stable, unique per response). | Fixes the pre-fix `key={fw.name}` = undefined duplicate-key bug. |
| Overall summary | One row above the list: overall_coverage_pct across framework_count frameworks / total_rules rules (AC-4). | Surfaces the API's own rollup; nothing recomputed. |

## Deviations
- Reviewer round (TAB-002+003 batch, both APPROVE) — NITs applied post-commit:
  FND-075 manifest now carries a second entry for the AppShell wizard pin file;
  CoverageGap error banner wording matched to the sibling pages.
