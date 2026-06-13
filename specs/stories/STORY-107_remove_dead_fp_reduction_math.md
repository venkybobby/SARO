# STORY-107: Remove dead false-positive-reduction computation in Gate 3

**Status:** ready
**Screen/Area:** engine.py — Gate 3 Risk Classification

## Goal
Gate 3 computes `false_positive_reduction` and stores it as `false_positive_reduction_rate` in `gate3_details`, but the value is never read anywhere (routers, services, frontend, reports, tests). The non-hybrid branch is a no-op identity (`len(set)/max(1,len(set))` ≡ 1.0). Remove the dead computation and its unused detail field.

## Context (file:line)
- `engine.py:1389-1393` — `false_positive_reduction = round(...)` computation (nonsense non-hybrid branch).
- `engine.py:1431` — `"false_positive_reduction_rate": false_positive_reduction if hybrid_mode else 0.0` in `gate3_details`.
- Grep proof: `false_positive_reduction_rate` appears only at the definition site; no consumer in routers/services/frontend/tests.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given Gate 3, When this story completes, Then the `false_positive_reduction` computation (`engine.py:1389-1393`) and the `false_positive_reduction_rate` key (`engine.py:1431`) are removed, and a repo grep for `false_positive_reduction` returns no live hits.
- **AC-2:** Given any code/test/schema that reads `gate3_details`, When inspected, Then none depended on `false_positive_reduction_rate` (verified before removal); all gate gates stay green.
- **AC-3:** Given identical inputs, When Gate 3 runs before vs after the change, Then `status`, `score`, and every other `gate3_details` field are unchanged (only the dead key is gone).

## Edge Cases
- A snapshot/contract test that asserts the exact shape of `gate3_details` — update it to the reduced shape if one exists.
- Keep `llm_calls_made`, `llm_parse_failures`, `hybrid_mode`, and `llm_classification` intact.

## Out of Scope
- Fixing the LLM judge input (STORY-101) or the external-model claim (STORY-102) — though all three touch the same Gate-3 block; coordinate ordering.

## Non-Functional Requirements
- Follow `.claude/skills/risk-scoring`: no change to score/status math.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_engine_source_has_no_false_positive_reduction` | engine.py |
| AC-2 | (grep-verified no consumers; full gate3 suite green) | engine.py |
| AC-3 | `test_gate3_details_has_no_false_positive_reduction_rate` (asserts kept keys remain) | tests/test_sar012_llm_classification.py |

**Status:** done — engine.py 6-line deletion + 2 unit pins. Gates green (ruff/mypy/unit/regression/ratchet 66.01%≥65.08%/bandit). Branch `story/STORY-107_remove_dead_fp_reduction_math` (stacked on `story/SARO_AIInsights_Stories`).
