# Aggregated Regression Suite

Rules (machine-enforced by `test_manifest_integrity.py`):
1. Every bug fix ships a `test_fnd_###_*.py` here that reproduces the original failure (red first).
2. Every test file here must have a manifest entry; every `pinned` entry must have an existing file.
3. Append-only: deleting/skipping a test requires human approval recorded in the manifest.
4. Flaky tests: mark `@pytest.mark.regression` + set `status: quarantined` with `quarantine_expires` (max 14 days). Expired quarantine fails CI.

Run tiers:
- Standard (pre-commit): `pytest tests/regression -q`
- Full (CI / phase close): `pytest -m regression -q` plus the whole suite.
