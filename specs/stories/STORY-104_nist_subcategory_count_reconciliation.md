# STORY-104: Reconcile NIST AI RMF subcategory count claim (code says 72, defines 68)

**Status:** ready
**Screen/Area:** routers/reports.py — NIST AI RMF coverage map; docs/COMPLIANCE_CLAIMS_MATRIX.md

## Goal
The NIST coverage endpoint claims it returns "all 72 NIST AI RMF 1.0 subcategory IDs," but the backing map (`_NIST_COVERAGE_MAP`) defines only 68. The asserted count and the actual data must agree so SARO never overstates framework coverage.

## Context (file:line)
- `routers/reports.py:245` — comment "All 72 NIST AI RMF 1.0 subcategory IDs with their automated coverage status."
- `routers/reports.py:248-288` — `_NIST_COVERAGE_MAP` with 68 entries (GOVERN 17, MAP 18, MEASURE 21, MANAGE 12).
- `routers/reports.py:302` — docstring "Returns coverage status for all 72 NIST AI RMF 1.0 subcategory outcomes."
- `docs/COMPLIANCE_CLAIMS_MATRIX.md:55` — accurate *subset* descriptor (no count claim) — leave as-is.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given the NIST coverage endpoint, When its response and code comments/docstrings are inspected, Then the stated total subcategory count exactly equals the number of entries actually present in `_NIST_COVERAGE_MAP` (no "72" claim over a 68-entry map).
- **AC-2:** Given the chosen reconciliation, When implemented, Then EITHER (a) the comment/docstring/response state 68 and describe it as SARO's mapped subset, OR (b) the map is completed to the full official 72 with the 4 missing subcategories added and correctly statused — **default: (a)**, the lower-risk, no-overclaim option, unless the user wants full 72 coverage.
- **AC-3:** Given a regression test, When it counts `_NIST_COVERAGE_MAP` entries and parses the asserted number in the endpoint response/docstring, Then they are equal (pins the reconciliation).
- **AC-4:** Given compliance-guard rules, When reviewed, Then no statement implies certified/complete NIST conformance.

## Edge Cases
- If option (b) is chosen, the 4 added subcategories must carry an honest status (likely "requires human assessment"), never a fabricated "mapped".
- Any UI surface that renders the count (e.g. coverage page) must reflect the corrected number.

## Out of Scope
- Changing how individual subcategories are statused (mapped/partial/human).
- EU AI Act / ISO / AIGP counts (not flagged).

## Non-Functional Requirements
- Follow `.claude/skills/compliance-guard`. Evidence-support language only.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1/AC-2 | `test_reports_source_does_not_overclaim_72`, `test_nist_coverage_map_has_68_entries` | routers/reports.py |
| AC-3 | same (count map size == asserted 68) | routers/reports.py |
| AC-4 | endpoint already returns `total_subcategories=len(map)`; no certified-conformance language | routers/reports.py |

**Status:** done. The endpoint response was already honest (`total_subcategories=len(_NIST_COVERAGE_MAP)`=68); only the comment (245) + docstring (302) overclaimed "all 72". Chose default: state 68 as SARO's mapped subset. Branch `story/STORY-104_nist_subcategory_count_reconciliation` (stacked on 102).
