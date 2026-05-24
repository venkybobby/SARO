# Skill: SARO QA Framework

## Test Structure

```
tests/
├── unit/           # FR-001 to FR-018 unit coverage
├── integration/    # API + DB integration
├── e2e/            # Playwright browser tests
├── performance/    # Locust load tests
├── security/       # OWASP checks
└── fixtures/       # 35+ fixture files with real ML outputs
```

## Fixture Data — Real ML Models (not mocked)

| Vertical | Model |
|----------|-------|
| Finance | GradientBoostingClassifier |
| Healthcare | RandomForestClassifier |
| Technology | NLP content moderation model |
| Government | Full NIST AI RMF assessment output |

## Requirements Coverage

- Functional: FR-001 through FR-018
- Non-functional: NFR-001 through NFR-007

## Running Tests (Windows / PowerShell)

```powershell
# Activate conda env
conda activate saro-env

# Unit tests
pytest tests/unit/ -v

# Integration
pytest tests/integration/ -v

# E2E (requires Playwright)
pytest tests/e2e/ -v

# Performance
locust -f tests/performance/locustfile.py --headless -u 50 -r 5 -t 60s

# Full suite
pytest tests/ -v --tb=short
```

## When Writing New Tests

1. Use real model outputs from fixtures — no random mocks
2. Test against FR/NFR IDs — tag each test with `@pytest.mark.requirement("FR-XXX")`
3. Async tests require `pytest-asyncio` with `@pytest.mark.asyncio`
4. Security tests follow OWASP Top 10 checklist
5. Performance baseline: API p95 < 500ms under 50 concurrent users

## Phase 3 Hard Gate — QA Sign-off Criteria

Before advancing past Phase 3:
- [ ] All 180 tests passing
- [ ] No P0/P1 security findings open
- [ ] Locust p95 < 500ms at 50 users
- [ ] Sam and Taylor both sign off
- [ ] OWASP scan clean
