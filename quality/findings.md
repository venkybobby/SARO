# SARO Findings Ledger

Every review/incident/audit finding gets an `FND-###` ID here. A finding is **closed only
when a regression test pins it** (listed in `tests/regression/manifest.yaml`).
Workflow: log here → root-cause → fix → write `tests/regression/test_fnd_###_*.py` → update manifest.

| ID | Title | Source | Discovered | Root Cause | Status |
|---|---|---|---|---|---|
| FND-001 | Redis session management broken (legacy audit) | audit | 2026-03 | session state not invalidated server-side | verify-pinned |
| FND-002 | Missing DELETE /auth/logout endpoint (legacy audit) | audit | 2026-03 | endpoint never registered | verify-pinned |
| FND-003 | Hardcoded JWT secret (legacy audit) | audit | 2026-03 | secret committed instead of env var | verify-pinned |
| FND-004 | TraceView: undefined `h` causes ReferenceError on audit-meta fetch | eslint flat-config rollout | 2026-06 | `frontend/src/pages/TraceView.jsx:86` referenced an undeclared `h` instead of an `Authorization` headers object | pinned |
| FND-005 | RiskRegister: undefined `toast` causes ReferenceError on bulk/delete actions | eslint flat-config rollout | 2026-06 | `frontend/src/pages/RiskRegister.jsx` called `toast?.success`/`toast?.error` but `toast` was never destructured from props | pinned |

**`verify-pinned`** = fix believed shipped, but no regression test confirms it stays fixed.
First task of any auth story: convert these to `pinned` by writing the tests.
