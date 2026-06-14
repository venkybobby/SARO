STORY-010: Scoring Methodology Evidence + FP Baseline (S-1103)
Status: ready    Screen/Area: Docs / Audit Engine / CI

Goal
Publish the scoring methodology and measure detection precision so the risk score is defensible to an audit committee. Includes VERIFY V-5 as AC-1. Closes FB-005.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the actual _compute_confidence implementation, When the methodology doc is written (V-5: read code first), Then docs/how-saro-reasons.md documents the formula, domain-weight table with rationale, 0.80 cap justification, and Bayesian parameters, and an automated test asserts doc constants equal code values
AC-2: Given tests/fixtures/fp_baseline/ with 100+ labeled positive and negative samples per domain, When tests/test_fp_baseline.py runs, Then per-domain precision and recall are computed and written to docs/metrics/detection-baseline.md
AC-3: Given a code change that drops any domain's precision by more than 5 percentage points, When CI runs, Then the pipeline fails
AC-4: Given any generated report, When its footer renders, Then it links the methodology document

Edge Cases
- Known keyword traps must appear in negative fixtures: 'fail-safe design', 'life hack', 'hackathon', 'failed authentication' — the published precision must reflect them honestly.
- Baseline regeneration is explicit (committed file), never silent in CI.

Out of Scope
- Changing detection logic to improve the numbers — measure first, publish honestly.
- Configurable weights (parked SARO-003).

Non-Functional Requirements
Baseline suite runs under 2 minutes in CI. Fixture licensing: synthetic or openly licensed text only.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
