# SARO Findings Ledger

Every review/incident/audit finding gets an `FND-###` ID here. A finding is **closed only
when a regression test pins it** (listed in `tests/regression/manifest.yaml`).
Workflow: log here → root-cause → fix → write `tests/regression/test_fnd_###_*.py` → update manifest.

| ID | Title | Source | Discovered | Root Cause | Status |
|---|---|---|---|---|---|
| FND-001 | Redis session management broken (legacy audit) | audit | 2026-03 | session state not invalidated server-side | verify-pinned |
| FND-002 | Missing DELETE /auth/logout endpoint (legacy audit) | audit | 2026-03 | endpoint never registered | verify-pinned |
| FND-003 | Hardcoded JWT secret (legacy audit) | audit | 2026-03 | secret committed instead of env var | verify-pinned |

**`verify-pinned`** = fix believed shipped, but no regression test confirms it stays fixed.
First task of any auth story: convert these to `pinned` by writing the tests.
