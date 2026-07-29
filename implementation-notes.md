# FND-088 / FND-089 — demo tenant misconfig fails silently; rotation ledger stale
Stage: trivial

## Lifecycle
- [x] discover   (skipped — well-trodden: routers/demo.py, secrets-runbook.md)
- [x] shape      (skipped — fix already specified from red-team QA review)
- [ ] preview    (skipped — backend-only + docs, no UI surface)
- [x] plan       (see below)
- [x] build
- [ ] verify      (trivial task; regression tests are the verification)
- [ ] sell — n/a

## Plan
FND-088: `routers/demo.py::get_demo_token` trusts `SARO_DEMO_TENANT_ID` on
presence alone — a stale/wrong UUID (confirmed live: pointed at a tenant that
doesn't exist in `tenants`) issues a token for a phantom tenant, and every
subsequent read comes back empty with no distinguishing error. Fix: validate
the env var resolves to an actual `Tenant` row before minting the token;
return 503 with a clear detail otherwise. Pinned by
`tests/regression/test_fnd_088_demo_token_validates_tenant.py`.

FND-089: `docs/security/secrets-runbook.md` §6 (rotation log) and
`RB-006-live-demo-verification.md` §G (rotation gate checklist) were never
updated after the FND-003 `super_admin` credential rotation — user confirmed
completion 2026-07-28, but the repo's own ledger still shows it open/unrotated.
Docs-only fix, no regression test (not a code behavior).

## Deviations
None yet.
