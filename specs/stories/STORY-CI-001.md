# STORY-CI-001: Fix CI ruff lint failures and fresh-Postgres migration chain

**Status:** in-progress
**Screen/Area:** CI / Quality Gates (no user-facing UI change)

## Goal
CI on `main` (commit ~575b16a, also affecting open PRs #62, #63, #65, #66) fails on
two unrelated jobs:

1. **Lint & Type Check / `test` (ruff)** — 25 `ruff check .` errors (F541, E402, F401)
   matching `quality/baseline.json`'s `ruff_errors: 25` (seeded in PR #66).
2. **Migrations Apply Cleanly (fresh Postgres)** — `psql:migrations/001_add_rls_policies.sql:2:
   ERROR: relation "audits" does not exist`, because `001_add_rls_policies.sql` assumes
   ORM-managed tables already exist (true in production via `create_all_tables()` before
   `apply_pending_migrations()` runs), but the CI job applies `migrations/*.sql` via raw
   `psql` against a genuinely empty database.

Fix both so CI passes again on `main` and rebased PRs, without weakening any tests or
moving the quality ratchet backward.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given `ruff check .` is run against the repo, When the 25 listed lint errors in
  `services/sales_notification_service.py`, `tests/test_404_fixes_batch2.py`,
  `tests/test_live005_live006.py`, `tests/test_p2_stories_009_010_014_016.py`,
  `tests/test_risk_register_audit_fixes.py`, and `tests/test_tenant_isolation.py` are
  fixed, Then `ruff check .` reports 0 errors.
- AC-2: Given `quality/baseline.json` previously recorded `ruff_errors: 25`, When the
  ratchet is updated via `scripts/update_quality_baseline.py`, Then
  `python scripts/check_quality_ratchet.py` passes with `ruff_errors: 0` and
  `coverage_pct`/`mypy_errors` unchanged or improved (never regressed).
- AC-3: Given a fresh, empty Postgres 16 database, When all files in `migrations/*.sql`
  are applied in alphabetical order via `psql -v ON_ERROR_STOP=1`, Then every file
  applies with exit code 0 (idempotent NOTICEs are acceptable).
- AC-4: Given the existing modified test files, When run via
  `pytest tests/test_404_fixes_batch2.py tests/test_live005_live006.py
  tests/test_p2_stories_009_010_014_016.py tests/test_risk_register_audit_fixes.py
  tests/test_tenant_isolation.py -q`, Then all tests still pass (no behavior change,
  only import/lint cleanup).
- AC-5: Given `tests/regression/`, When run via `pytest tests/regression -q`, Then all
  regression tests continue to pass.

## Edge Cases
- `tests/test_404_fixes_batch2.py` references `Audit`/`ClientConfig` only via
  `model.__name__` string comparisons in app code under test — removing the unused
  direct imports must not break those checks.
- `migrations/000_create_core_tables.sql` must sort before
  `000_schema_migrations_tracking.sql` and `001_add_rls_policies.sql`
  (`"000_c" < "000_s" < "001_"`).
- `scan_reports` and `audit_traces` need a `tenant_id` column (with FK to `tenants`)
  in the new baseline migration, ahead of `002_add_tenant_id_columns.sql`, because
  `001_add_rls_policies.sql` creates RLS policies referencing `tenant_id` on those
  tables.
- `persona_permissions` must NOT be created by the new baseline migration —
  `004_add_persona_permissions.sql` creates it with its own (older) schema and seeds
  it via `INSERT ... ON CONFLICT DO NOTHING`, which would fail against the
  `models.py`-derived shape.

## Out of Scope
- The "Claude Code Review" CI check failure (Anthropic API key billing/"Credit balance
  too low") — separate, non-code issue.
- `pytest tests/ -m unit -q` currently selects 0 tests (no tests carry the `unit`
  marker) — pre-existing condition, not introduced by this change, not fixed here.
- Pre-existing `mypy` errors (4, matches baseline) — unchanged, out of scope.
- Reconciling `persona_permissions` schema drift between `models.py` and
  `004_add_persona_permissions.sql` — flagged but not resolved here.

## Non-Functional Requirements
- Quality ratchet (`quality/baseline.json`) must only improve or hold — never regress.
- Conventional Commits format, scope `ci`.
- Independent `reviewer` and `security-auditor` agent approval required before merge.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1, AC-2 | `ruff check .`, `python scripts/check_quality_ratchet.py` | `services/sales_notification_service.py`, `tests/test_404_fixes_batch2.py`, `tests/test_live005_live006.py`, `tests/test_p2_stories_009_010_014_016.py`, `tests/test_risk_register_audit_fixes.py`, `tests/test_tenant_isolation.py`, `quality/baseline.json` |
| AC-3 | manual `psql -f` chain against fresh `postgres:16` container | `migrations/000_create_core_tables.sql` |
| AC-4, AC-5 | `pytest tests/test_404_fixes_batch2.py tests/test_live005_live006.py tests/test_p2_stories_009_010_014_016.py tests/test_risk_register_audit_fixes.py tests/test_tenant_isolation.py -q`, `pytest tests/regression -q` | (all files above) |
