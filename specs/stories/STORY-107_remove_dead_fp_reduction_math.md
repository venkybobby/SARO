# STORY-107: Remove Dead/Misleading False-Positive-Reduction Math in Non-Hybrid Branch (G-7)
Status: ready
Screen/Area: Scoring Engine / `engine.py:1393–1397`

## Goal
The non-hybrid branch computes `x/max(1,x)` — always 1.0 when flags exist — then discards it. Harmless functionally, but it is exactly the line a code-level auditor screenshots as evidence of fabricated-looking metrics. Delete the dead computation; ensure the metric simply does not exist outside hybrid mode (aligns with STORY-101 AC-3).

GRC mapping: code-as-evidence hygiene; NIST AI RMF MEASURE function credibility.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given hybrid mode is off, When a scan executes, Then no `false_positive_reduction` value is computed, logged, or persisted anywhere in the code path.
- AC-2: Given the diff, When reviewed, Then only the dead branch is touched — no orthogonal refactoring of `engine.py` (scope discipline).
- AC-3: Given the test suite, When run, Then a test asserts the metric is absent from `AuditTrace.detail_json` for non-hybrid scans and present only for genuine hybrid runs.

## Edge Cases
- Downstream report templates or dashboards referencing the metric unconditionally → render "N/A (hybrid disabled)" rather than erroring on a missing key.

## Out of Scope
- The Gate-3 input fix (STORY-101); metric redefinition.

## Non-Functional Requirements
- Standard project rules; minimal diff.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
