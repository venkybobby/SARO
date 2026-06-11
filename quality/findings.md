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
| FND-007 | `risk_detail` navigation silently falls through to Dashboard | SARO_AIInsights_Stories implementation | 2026-06 | `RiskRegister` (and now AIInsights) call `onNavigate("risk_detail", …)` but `PAGE_COMPONENTS` in `frontend/src/App.jsx` never registered the key and never wired RiskDetail's `riskId` prop, so `PAGE_COMPONENTS[activePage] \|\| Dashboard` rendered Dashboard instead | pinned |
| FND-008 | Bad merge left duplicate JSX in RiskForm.jsx and a non-compiling RiskForm.test.jsx, masking 13 tests | SARO_AIInsights_Stories gate run | 2026-06 | A merge of PR #61/#67 kept both old and new versions of lines: duplicate `id="*-error"` divs (one `#ef4444`, one `var(--color-critical)`) in `RiskForm.jsx`, plus duplicate imports and two unterminated blocks in `RiskForm.test.jsx`. The test file failed esbuild transform, so the whole file (13 tests incl. STORY-RISKFORM-001/002 coverage) never ran and the entire frontend suite was red | pinned |
| FND-009 | Insights action authz is a persona denylist, not an allowlist | security-auditor (SARO_AIInsights_Stories) | 2026-06 | `routers/insights.py` blocks only `ai_auditor` from POST /api/v1/insights/{id}/action; `User.persona_role` is nullable, so NULL or future personas default to write access. Convert to an allowlist (`auth.persona_required(...)`) once the persona taxonomy stabilizes; note `routers/risks.py` mutating endpoints have no persona check at all today | open |
| FND-010 | LIKE wildcard injection in routers/risks.py risk-id prefix lookup | security-auditor (SARO_AIInsights_Stories) | 2026-06 | `_find_audit_with_meta` strips `R-` and passes user input into `cast(Audit.id, String).like(f"{prefix}%")` unescaped — `%`/`_` wildcards match arbitrary same-tenant audits nondeterministically on read/PATCH/DELETE paths. Same hole was fixed in `routers/insights.py` via `_safe_prefix()` hex validation; port that fix and pin it | open |

**`verify-pinned`** = fix believed shipped, but no regression test confirms it stays fixed.
First task of any auth story: convert these to `pinned` by writing the tests.
