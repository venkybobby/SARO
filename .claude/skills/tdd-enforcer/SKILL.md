---
name: tdd-enforcer
description: Enforces test-driven development for all SARO implementation tasks. Triggered when implementing new features, fixing bugs, or modifying engine.py, routers/, or schemas.py.
---

Follow the Red-Green-Refactor cycle strictly. Do not write production code before a failing test exists.

## TDD Cycle

### Step 1 — Red (write the failing test first)
- Create or extend the appropriate test file in `tests/`
- Test must fail before any implementation exists
- Name: `test_<feature>_<scenario>` following existing conventions
- Use pytest fixtures from `conftest.py` — do not duplicate setup
- Run `pytest tests/test_<file>.py::test_<name> -q` and confirm it fails

### Step 2 — Green (minimal implementation)
- Write the smallest amount of code that makes the test pass
- No over-engineering at this stage
- Run `pytest tests/test_<file>.py::test_<name> -q` and confirm it passes

### Step 3 — Refactor
- Clean up without changing behaviour
- Run the full suite: `pytest tests/ -q --tb=short`
- All tests must remain green

## Test Structure for SARO

**Unit tests** (engine, scoring, schemas):
```python
def test_<function>_<scenario>(mock_db_session):
    # Arrange
    # Act
    # Assert — one logical assertion per test
```

**Integration tests** (routers):
```python
def test_<endpoint>_<scenario>(test_client, auth_headers):
    response = test_client.post("/api/v1/...", json={...}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["risk_score"] in range(0, 101)
```

**Drift / KS-test tests**: see drift-sentinel skill for thresholds.

## Coverage Minimums
- New engine logic: unit + integration test required
- New endpoint: integration test required
- Bug fix: regression test required (test that would have caught the bug)

## Never
- Skip tests because "it's a small change"
- Write tests after implementation is complete
- Use `# type: ignore` or `assert True` as placeholder tests
