# FND-090 — tenants.settings_json missing from prod schema, demo/token 500s
Stage: trivial

## Lifecycle
- [x] discover   (found live, mid-verification of FND-088's deploy)
- [x] shape      (skipped — root cause is a one-line ALTER TABLE)
- [ ] preview    (skipped — backend/DB only)
- [x] plan       (see below)
- [x] build
- [ ] verify      (trivial task; regression test + live verification are the verification)
- [ ] sell — n/a

## Plan
Live verification of PR #153's FND-088 fix surfaced a pre-existing, unrelated
schema drift: production's `tenants` table lacks `settings_json`, which
`models.Tenant` has declared since migration 000's current file content
(evidently added to the file after 000 was already applied to prod, with no
follow-up incremental migration). `db.get(Tenant, id)` — used by the FND-088
fix — selects every mapped column, so the missing column turned a graceful
"demo tenant misconfigured" 503 into an unhandled 500 on every call to
`GET /api/v1/demo/token`. This is currently live-broken (worse than the
original FND-088 bug: total endpoint outage vs. an empty-tenant experience).

Fix: `migrations/043_tenants_settings_json.sql` — `ALTER TABLE tenants ADD
COLUMN IF NOT EXISTS settings_json JSON`. Auto-applied by
`apply_pending_migrations()` on next backend restart (main.py:170).

## Deviations
None yet.
