# FND-093 (was FND-092) — users.role has no DB-level CHECK constraint
Stage: trivial

## Lifecycle
- [x] discover   (Phase 1 analysis of a pasted generic auth-remediation prompt; verified against
      actual repo state, not the prompt's generic assumptions)
- [x] shape      (skipped — user picked "file /finding for the role CHECK constraint" via AskUserQuestion)
- [ ] preview    (skipped — backend/DB only, no UI)
- [x] plan       (see below)
- [x] build
- [x] verify      (regression test pinned; full suite green (2420 passed, 26 skipped) +
      ruff/mypy/bandit clean on touched files + independent reviewer (APPROVE) and
      security-auditor (PASS) both no-blocker)
- [ ] sell — n/a

## Plan
`models.User.role` is `String(50)` with only a code comment ("Roles:
super_admin | operator") documenting the two valid values — no DB-level
CheckConstraint or enum. Verified safe to add: grepped every `role=`/`role =`
site in the tree; the only other role-shaped literals ("viewer", "admin",
"demo_viewer") appear exclusively in `MagicMock(spec=User)` /
`SimpleNamespace` test doubles that never reach the database. The one
production write path taking a caller-supplied role (`routers/clients.py`
client-onboarding enrollment) is already Pydantic-restricted to the two
literals (`schemas.UserEnrollmentIn.role: Literal["super_admin", "operator"]`)
before it ever reaches the ORM.

Fix:
- `models.py` — add `CheckConstraint("role IN ('super_admin', 'operator')",
  name="ck_users_role_valid")` to `User.__table_args__`.
- `migrations/044_users_role_check.sql` — idempotent
  (`DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT`) so existing environments
  (whose `schema_migrations` already recorded `000` before this constraint
  existed in the model) catch up, matching the migration-drift lesson from
  FND-090/091.

Regression test: `tests/regression/test_fnd_093_users_role_check_constraint.py`
— red-first (confirmed: insert with `role="supper_admin"` succeeded
pre-fix, `DID NOT RAISE IntegrityError`), follows the isolated-SQLite-engine
pattern from `test_fnd_058_ensure_demo_user_tenant_guard.py`.

## Deviations
1. **ID renumbering (FND-092 → FND-093):** this fix was built and reviewed as
   FND-092. Before push, `origin/main` was found to have independently landed
   an unrelated FND-092 (`GET /api/v1/demo/token` missing from the rate
   limiter's `_AUTH_STRICT_PREFIXES`) while this fix was in progress — a real
   ledger collision per CLAUDE.md's ledger rule. Rebased onto latest
   `origin/main` (new branch `fix/fnd-093-users-role-check`), took main's
   FND-092 row as-is, and renumbered this fix's entry to FND-093 (next
   available ID, confirmed free — `migrations/044` was also still free).
   Renamed `test_fnd_092_users_role_check_constraint.py` →
   `test_fnd_093_users_role_check_constraint.py` and updated every in-repo
   `FND-092` reference belonging to this fix (`models.py` comment, the
   migration file header, the test file itself) to `FND-093`. Both prior
   independent reviews (security-auditor PASS, reviewer APPROVE) were
   performed against the FND-092-numbered content; the underlying diff is
   otherwise unchanged, so those verdicts still apply to FND-093's content.
