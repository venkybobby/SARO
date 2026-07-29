# FND-091 — tenants missing from database.py startup self-heal
Stage: trivial

## Lifecycle
- [x] discover   (security-auditor review of the FND-090 PR, 2026-07-29)
- [x] shape      (skipped — user picked option (a) via AskUserQuestion: populate the dicts)
- [ ] preview    (skipped — backend/DB only)
- [x] plan       (see below)
- [x] build
- [x] verify      (regression test pinned + full suite green (2417 passed) +
      independent reviewer/security-auditor approval, both no-blocker)
- [ ] sell — n/a

## Plan
`_APP_TABLE_EXPECTED_COLS` (drives drift detection in `ensure_app_schema()`) and
`_SAFE_ALTER_COLS` (the ALTER-COLUMN healer for precious tables) have no
`"tenants"` key/contents, despite the code's own comment claiming coverage for
"precious tables (users, tenants)". `_SAFE_ALTER_COLS["tenants"]` already
exists as an empty dict — already drop-exempt via the Step 2 `table_name not
in _SAFE_ALTER_COLS` check — it just has nothing to ALTER, and `tenants` is
entirely absent from `_APP_TABLE_EXPECTED_COLS` so drift is never even
detected for it.

Decision (user, via AskUserQuestion): option (a) — populate both dicts, same
pattern already used for `users`/`audit_traces`/`audits`/`scan_reports`.

Fix (`database.py`):
- `_APP_TABLE_EXPECTED_COLS["tenants"]` = full current column set from
  `models.Tenant`: `id, name, slug, settings_json, security_contact_email,
  created_at`.
- `_SAFE_ALTER_COLS["tenants"]` = `{"settings_json": "JSON",
  "security_contact_email": "VARCHAR(320)"}` — DDL types matched to
  migrations 043 and 042 respectively.

Regression test: `tests/regression/test_fnd_091_tenants_self_heal_coverage.py`
(manifest already had this FND-091 entry logged at `status: open`) — pins
both dicts, following the existing `TestDatabaseExpectedCols` /
`TestDatabaseSafeAlterCols` patterns in `tests/test_s001_hf_queue.py` /
`tests/test_dc_gaps.py`.

## Deviations
None.
