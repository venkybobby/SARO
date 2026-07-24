# STORY-TAB-003: Coverage Gap tab — align field names with the coverage API (no more blank frameworks / "undefined")

**Status:** done
**Screen/Area:** Coverage Gap tab (frontend/src/pages/CoverageGap.jsx ↔ routers/compliance_matrix.py)

## Premise verification

| Referenced artifact | Evidence |
|---|---|
| `GET /api/v1/compliance-matrix/coverage` returns `frameworks: [{framework, total_rules, covered, partial, not_covered, coverage_pct, last_updated}]` plus `overall_coverage_pct`, `framework_count`, `total_rules` | routers/compliance_matrix.py:174-207 |
| Frontend reads `fw.name`, `fw.gaps`, `fw.gaps_count`, `fw.controls_covered`, `fw.controls_total` — none exist → blank labels, "No gaps identified for undefined" | frontend/src/pages/CoverageGap.jsx:47,56,62,77-98 |
| Live deployment confirms shape | probed 2026-07-23 with demo token |

## Goal
Coverage Gap renders progress bars with blank framework names and a nonsense "No gaps identified for undefined" detail pane, because every field it reads differs from what the API returns. After this story the tab shows each framework by name with its real coverage breakdown (covered / partial / not covered out of total rules), plus the overall coverage summary the API already computes.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the API returns framework entries, Then the framework list renders `fw.framework` as the visible name and React key, with `coverage_pct` and its color band as today.
- AC-2: Given a framework is selected, Then the detail pane shows `covered`/`partial`/`not_covered` counts against `total_rules` and `last_updated` — the "gaps"/"controls" fields that don't exist are no longer referenced anywhere in the component.
- AC-3: Given a framework has `not_covered > 0`, Then the detail pane presents that as the gap signal ("N of M rules not covered"); given `not_covered === 0` and `partial === 0`, a positive "fully covered" state is shown naming the actual framework.
- AC-4: Given the top-level response, Then an overall summary row shows `overall_coverage_pct` across `framework_count` frameworks and `total_rules` rules.
- AC-5: Given the API returns non-2xx or an empty `frameworks` array, Then an error banner or an explicit "no coverage data" state renders (never a blank page).

## Edge Cases
- `coverage_pct` of exactly 0 → bar renders at 0 width with the framework name still visible.
- `last_updated` null → row omitted, no "null" text.

## Out of Scope
- Backend changes to add per-rule gap detail (a real "which rules are uncovered" drill-down needs a new endpoint — candidate follow-up, not this story).
- Merging into Compliance Hub (STORY-TAB-008).

## Non-Functional Requirements
- Vitest contract-pin test with the live response shape (including a 0%-coverage framework, matching current deployed data); must fail against the pre-fix component.
- Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `CoverageGap.test.jsx`: "renders each framework's name and coverage_pct — including a 0% one" (asserts no 'undefined' text; selection keyed by `framework`) | CoverageGap.jsx, CoverageGap.test.jsx |
| AC-2 | `CoverageGap.test.jsx`: "selected framework shows covered/partial/not-covered against total_rules and last_updated" (phantom-field artifacts asserted absent) | CoverageGap.jsx, CoverageGap.test.jsx |
| AC-3 | `CoverageGap.test.jsx`: "1 of 8 rules not covered" gap signal + "fully covered framework shows a positive state naming it" | CoverageGap.jsx, CoverageGap.test.jsx |
| AC-4 | `CoverageGap.test.jsx`: "renders overall coverage across frameworks and rules" | CoverageGap.jsx, CoverageGap.test.jsx |
| AC-5 | `CoverageGap.test.jsx`: "non-2xx renders the error banner" + "empty frameworks array renders an explicit no-data state" | CoverageGap.jsx, CoverageGap.test.jsx |

**Edge cases covered:** 0% framework renders with visible name; `last_updated`
null → row omitted, no "null" text — both in `CoverageGap.test.jsx`.

**Finding:** FND-076 (quality/findings.md) — pinned red-first (6/7 failed
pre-fix), manifest entry `status: pinned`.
