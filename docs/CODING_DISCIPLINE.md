# SARO Coding Discipline v1.0

> Adapted from Karpathy's four LLM coding principles (https://github.com/multica-ai/andrej-karpathy-skills).
> These apply to all contributors and to Claude Code sessions in this repo.
> Also enforced via `.cursor/rules/karpathy-guidelines.mdc` for Cursor IDE users.

---

## The Four Principles

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

**SARO-specific danger zones where silent assumptions cause real harm:**

| Task phrasing | Hidden risk |
|---|---|
| "Add a compliance check" | Could mean UI copy, API field, or scoring rule — different regulatory implications |
| "Update the risk score" | Which component: DIR, SHAP weight, KS-test threshold, rule pack? |
| "Improve the audit trail" | TRACE immutability is a hard constraint — "improve" can accidentally break hash-chain integrity |
| Any compliance language | Must be validated against `docs/COMPLIANCE_CLAIMS_MATRIX.md` before writing |

---

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios (trust FastAPI/SQLAlchemy/Pydantic guarantees).
- If you write 200 lines and it could be 50, rewrite it.

**SARO anti-patterns to avoid:**

```python
# ❌ Over-engineering a rule check
class RuleEvaluatorFactory:
    def __init__(self, strategy: RuleStrategy, fallback=None, cache=None): ...

# ✅ What was actually asked
def evaluate_rule(prompt: str, output: str, rule: dict) -> bool:
    return rule["pattern"] in output
```

The scoring engine (`engine.py`) has DIR formula, SHAP, KS-test, and rule packs already. Do not add sub-systems unless explicitly scoped in a story.

---

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style: async/await, Pydantic v2 validators, SQLAlchemy session patterns.
- If you notice unrelated dead code or a bug — **mention it, don't fix it silently.**

When your changes create orphans:
- Remove imports/variables/functions that **your** changes made unused.
- Don't remove pre-existing dead code unless explicitly asked.

**Test:** every changed line traces directly to the stated task.

**SARO example — fixing a TRACE event ordering bug:**

```diff
  # ❌ Wrong: rewrites surrounding event logic "while you're in there"
- events = [build_event(e) for e in raw_events]
+ events = sorted([build_event(e) for e in raw_events], key=lambda x: x.timestamp)
+ events = [e for e in events if e.event_type in VALID_TYPES]  # added cleanup

  # ✅ Right: only fix the reported ordering issue
- events = [build_event(e) for e in raw_events]
+ events = sorted([build_event(e) for e in raw_events], key=lambda x: x.timestamp)
```

---

### 4. Goal-Driven Execution

**Define verifiable success criteria. Loop until verified.**

Transform vague tasks into testable goals:

| Vague | Verifiable |
|---|---|
| "Fix the scoring bug" | "Write pytest fixture with prompt X + output Y — score must be ≤ 30. Make it pass." |
| "Add drift detection" | "KS-test p < 0.05 triggers `DRIFT_DETECTED` event in TRACE. Existing 7-event order still holds." |
| "The UI looks wrong" | "`data-testid='risk-score'` visible within 10s on Playwright golden path. No console errors." |
| "Improve remediation text" | "Remediation field non-empty for score ≥ 50. `human validation required` phrase present. No compliance claims." |

For multi-step tasks, state a plan with explicit verification steps:

```
1. Write a failing test that reproduces the bug → verify: pytest shows the failure
2. Fix the root cause in engine.py → verify: that specific test passes
3. Run full suite → verify: no regressions (pytest tests/ -q, all green)
```

Strong success criteria let Claude (and humans) loop independently without constant clarification.

---

## Anti-Pattern Quick Reference

| Principle | Anti-Pattern | Correct Behaviour |
|---|---|---|
| Think Before Coding | Assumes "export data" means all users as JSON | Lists assumptions, asks about scope/format/fields |
| Simplicity First | Strategy pattern for a single rule evaluation | One function until complexity is actually needed |
| Surgical Changes | Reformats quotes, adds type hints while fixing a bug | Only changes lines that fix the reported issue |
| Goal-Driven Execution | "I'll review and improve the scoring logic" | "Test: score for this fixture must be 74 ± 1. Make it pass." |

---

## For SARO-Specific Scoring Work

When working in `engine.py`, `services/risk_service.py`, or rule packs, the Goal-Driven principle is critical because:

- The DIR formula has invariants (see `.claude/skills/risk-scoring/SKILL.md`)
- SHAP values must remain explainable and bounded
- KS-test thresholds are calibrated — arbitrary changes cause false positives/negatives
- TRACE event order is contractual — clients parse it programmatically

Success criteria for scoring changes must always include:
1. A specific input fixture (prompt + raw_output + vertical)
2. An expected score range or TRACE event
3. Explicit "no regression" check against existing test suite

---

*Owner: Venky (Lead) | Last updated: 2026-05-22*
*Source: https://github.com/multica-ai/andrej-karpathy-skills (MIT)*
