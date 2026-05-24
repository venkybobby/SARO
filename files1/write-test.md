# Command: /saro:write-test

Generate a test for a SARO feature following the 180-test framework structure.

## Usage

```
/saro:write-test [test-type] [FR or NFR ID] [feature description]
```

Examples:
- `/saro:write-test unit FR-019 "new compliance report generation endpoint"`
- `/saro:write-test e2e FR-015 "TRACE view renders SHAP scores for Finance vertical"`
- `/saro:write-test performance NFR-008 "Drift Sentinel API under load"`

## Test Types

| Type | Framework | Location |
|------|-----------|----------|
| `unit` | pytest | `tests/unit/` |
| `integration` | pytest + httpx | `tests/integration/` |
| `e2e` | Playwright | `tests/e2e/` |
| `performance` | Locust | `tests/performance/` |
| `security` | pytest + OWASP checklist | `tests/security/` |

## Rules When Generating Tests

1. **Tag every test** with `@pytest.mark.requirement("FR-XXX")` or `@pytest.mark.requirement("NFR-XXX")`
2. **Use real fixture data** — import from `tests/fixtures/`. Never use `random` or hardcoded prediction values.
   - Finance: `fixtures/finance_gradientboosting_outputs.json`
   - Healthcare: `fixtures/healthcare_randomforest_outputs.json`
   - Technology: `fixtures/technology_nlp_outputs.json`
   - Government: `fixtures/government_nist_assessment.json`
3. **Async tests**: use `@pytest.mark.asyncio` + `pytest-asyncio`
4. **Performance baseline**: Locust scenarios target p95 < 500ms at 50 users
5. **No `time.sleep()`** in async test contexts
6. Show only the new test code — do not output unchanged test files

## Output Format

```python
# tests/[type]/test_[feature].py
# FR/NFR: [ID] — [description]

import pytest
# ... imports

@pytest.mark.requirement("[FR/NFR-XXX]")
[async] def test_[descriptive_name](...):
    # Arrange
    ...
    # Act
    ...
    # Assert
    ...
```

End with:
```
FILES CHANGED: tests/[type]/test_[feature].py — new test for [FR/NFR-XXX]
FILES NOT TOUCHED: [list]
CONCERNS: [any fixture gaps, missing test data, or coverage notes]
```
