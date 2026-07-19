# FND-058 — ensure_demo_user() silently reassigned tenant_id/role/password on any user matched by email
Stage: trivial

Single-file fix (`scripts/seed_demo_tenant.py`) + its regression test — gates stand down per the lifecycle skill's trivial-finding path. Steps 1-7 below are the build stage.

## Root cause (5 whys)
1. Why did the security-auditor flag `ensure_demo_user()`? — It reassigns `tenant_id`, escalates `role` to `super_admin`, and resets the password on any row matched by email, with no check the row already belongs to the demo tenant or role.
2. Why does that matter? — If the demo email were ever matched to an unrelated real account, the script would silently hijack it (privilege escalation + password reset) instead of failing loudly.
3. Why could an unrelated account match? — `email` is globally unique (`models.User.email`), so in practice this can't happen today — but the lookup itself (`SELECT id FROM users WHERE email = :email`) makes no assumption about *why* the match happened, so nothing in the code enforces that invariant.
4. Why wasn't this caught earlier? — PR #119 introduced `ensure_demo_user()` to fix demo login (JSON vs form-encoded auth body); the security-auditor review of that PR flagged this as a non-blocking follow-up, not a blocker, since the caller already needs `DATABASE_URL` access (highest privilege) to run the script.
5. Why fix it anyway? — Defense-in-depth: a loud abort costs nothing on the legitimate path (same tenant, already `super_admin`) and turns a silent-hijack failure mode into a fail-closed one.

## Fix
`ensure_demo_user()` now selects `id, tenant_id, role` (was `id` only). Before the
UPDATE, if the matched row's `tenant_id` is non-null and either differs from the
target tenant or its `role` isn't already `'super_admin'`, it raises `RuntimeError`
instead of overwriting. UUID comparison goes through `uuid.UUID(str(...))` rather
than raw string equality — SQLite returns dash-less hex from a raw-SQL `SELECT`
(bypasses the ORM's UUID type decorator) while Postgres/the ORM use dashed form;
comparing as `uuid.UUID` objects normalizes both.

## Tests
- `tests/regression/test_fnd_058_ensure_demo_user_tenant_guard.py` (real SQLite DB,
  ORM-built fixtures): different-tenant hijack refused, same-tenant-non-admin
  escalation refused, legitimate same-tenant/already-super_admin reset still works.
  Ran against pre-fix code first — the two hijack tests failed with "DID NOT RAISE"
  (silent hijack confirmed red), then passed after the fix (green).
- `tests/test_s000_seed.py::TestEnsureDemoUser` — extended `_make_session` to return
  a 3-column `(id, tenant_id, role)` row (was `id` only, via a `__getitem__` lambda
  that couldn't distinguish columns); added the two guard-rejection unit tests
  alongside the existing create/reset-password tests.
- `quality/findings.md` + `tests/regression/manifest.yaml`: FND-058 logged as
  `status: pinned` in both (ledger-consistency test covers this).

## Verify (post-rebase onto origin/main @ 565fe96)
- `pytest tests/regression/test_fnd_058_ensure_demo_user_tenant_guard.py tests/test_s000_seed.py::TestEnsureDemoUser -q` — 7 passed
- `pytest tests/regression -q` — 118 passed (manifest/ledger consistency included)
- `pytest tests/ -q` — 1759 passed, 3 skipped, 0 failed
- `ruff check scripts/seed_demo_tenant.py tests/test_s000_seed.py tests/regression/test_fnd_058_ensure_demo_user_tenant_guard.py` — all checks passed
- Independent `security-auditor` review of the diff (vs `origin/fix/seed-demo-tenant-login`): **PASS, no blocking findings**. Confirmed the guard's boolean logic via mutation testing (flipping `or`→`and`, `!=`→`==` both fail the new tests), confirmed `tenant_id IS NULL` branch is schema-unreachable today (`users.tenant_id` NOT NULL), confirmed no info-leak/DoS/injection introduced, confirmed tests use a real SQLite+ORM session (not mocks) so the UUID-normalization fix is meaningfully exercised. One optional (non-blocking) hardening idea logged: treat `existing_tenant_id is None` as "also refuse" rather than silently falling through, in case a future migration ever relaxes the NOT NULL constraint. (Review ran against the FND-055-numbered version of the diff — content identical, only the finding ID/filenames changed in the rebase, so the verdict still applies.)

## Deviations
- **Renumbered FND-055 → FND-058 mid-task.** Originally logged this as FND-055 on a
  branch forked from `origin/fix/seed-demo-tenant-login` (PR #119) before checking
  whether that PR had merged. It had — PR #119 merged as `89bd7d6` on 2026-07-17,
  and a separate PR #120 (STORY-408) merged on top of that as `565fe96`, claiming
  FND-055/FND-056 for its own (unrelated) findings and adding FND-057. Discovered
  this when the user flagged "a new PR is hanging in git" (PR #121, a stray
  duplicate of the already-merged #120 — same branch name
  `story-408-cross-account-log-pull`, appears to be a re-push of already-merged
  work, not something this task should touch). Rebased: stashed uncommitted work,
  `git reset --hard origin/main`, popped the stash, resolved manifest.yaml/
  findings.md/implementation-notes.md conflicts by renumbering to FND-058 (next
  free ID after main's FND-057) and renaming the regression test file. No logic
  changed, only IDs/filenames.

## Branch note
Built on branch `fix/seed-demo-user-tenant-guard`. Originally forked from
`origin/fix/seed-demo-tenant-login` (PR #119) while that PR was still open and
already checked out in the primary worktree; after discovering PR #119 had since
merged to `main` (see Deviations), rebased onto current `origin/main`. This is
follow-up hardening on top of PR #119's `ensure_demo_user()`, landed as its own
PR against `main` rather than added to #119 (which is closed).
