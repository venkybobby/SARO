---
name: test-patterns
description: Triggered when writing or editing tests. Enforces SARO test conventions including pytest fixtures, Playwright E2E patterns, Locust performance tests, and OWASP security checks.
---

# Test Patterns Skill

## Trigger Conditions
Activate for any file under `tests/`, `saro-data-framework/tests/`, or files containing `pytest`, `playwright`, `locust`, `TestClient`, or `conftest`.

## pytest — Backend

### Fixtures (from `tests/conftest.py`)

```python
import pytest
from httpx import AsyncClient
from main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def auth_headers(client):
    # POST /api/v1/auth/token with test credentials
    ...
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def sample_scan_payload():
    return {
        "prompt": "Summarise this contract for a retail bank customer.",
        "raw_output": "You should invest all your savings in crypto immediately.",
        "vertical": "finance"
    }
```

### Test Structure

```python
# tests/test_scan.py
class TestScanEndpoint:
    async def test_risk_score_range(self, client, auth_headers, sample_scan_payload):
        resp = await client.post("/api/v1/scans", json=sample_scan_payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert 0 <= data["risk_score"] <= 100
        assert isinstance(data["risk_score"], int)

    async def test_trace_event_order(self, client, auth_headers, sample_scan_payload):
        resp = await client.post("/api/v1/scans", json=sample_scan_payload, headers=auth_headers)
        events = [e["event_type"] for e in resp.json()["trace"]]
        expected = ["SCAN_INITIATED","RULES_APPLIED","SCORE_COMPUTED","SHAP_EXPLAINED","DRIFT_CHECKED","REMEDIATION_GEN","SCAN_COMPLETE"]
        assert events == expected
```

### Naming Convention

- Unit tests: `test_<module>_<behaviour>.py`
- Integration tests: `test_integration_<flow>.py`
- Parametrize edge cases: `@pytest.mark.parametrize`
- Mark slow tests: `@pytest.mark.slow` (excluded from default CI run, included in nightly)

## Playwright — E2E

```python
# tests/e2e/test_scan_flow.py
from playwright.sync_api import Page, expect

def test_scan_golden_path(page: Page):
    page.goto("http://localhost:5173")  # React/Vite dev port
    page.fill("[data-testid='prompt-input']", "Test prompt")
    page.fill("[data-testid='output-input']", "Test output")
    page.select_option("[data-testid='vertical-select']", "finance")
    page.click("[data-testid='submit-scan']")
    expect(page.locator("[data-testid='risk-score']")).to_be_visible(timeout=10_000)
    score_text = page.locator("[data-testid='risk-score']").inner_text()
    assert 0 <= int(score_text) <= 100
```

## Locust — Performance

```python
# tests/perf/locustfile.py
from locust import HttpUser, task, between

class ScanUser(HttpUser):
    wait_time = between(0.5, 2)

    @task
    def submit_scan(self):
        self.client.post("/api/v1/scans", json={
            "prompt": "Perf test prompt",
            "raw_output": "Perf test output",
            "vertical": "technology"
        }, headers={"Authorization": f"Bearer {self.token}"})

# Thresholds (enforced in CI):
# p50 < 500ms, p95 < 2000ms, p99 < 3000ms, error_rate < 1%
```

## OWASP Security Patterns

```python
# tests/security/test_owasp.py

def test_sql_injection_rejected(client):
    payload = {"prompt": "'; DROP TABLE scans; --", "raw_output": "x", "vertical": "finance"}
    resp = client.post("/api/v1/scans", json=payload, headers=auth_headers)
    assert resp.status_code in (201, 422)  # processed or validated, never 500

def test_jwt_required(client):
    resp = client.post("/api/v1/scans", json={...})
    assert resp.status_code == 401

def test_oversized_payload_rejected(client, auth_headers):
    payload = {"prompt": "x" * 33_000, "raw_output": "y", "vertical": "finance"}
    resp = client.post("/api/v1/scans", json=payload, headers=auth_headers)
    assert resp.status_code == 422
```
