# STORY-373: Tenant Onboarding Playbook + Scripted Provisioning

**Status:** ready
**Screen/Area:** Backend CLI + ops docs (Pack Epic 17)
**Ground truth:** `scripts/seed_demo_tenant.py` is the closest precedent
(idempotent demo-tenant seeding); `cli.py` hosts operator commands; migration 037
added TenantLogSourceConfig. Generalize, don't fork.

## Goal
Onboarding tenant #2 is a single documented, scripted, auditable procedure.

## Acceptance Criteria
- AC-1: Idempotent provisioning CLI (`cli.py provision-tenant`): creates tenant,
  admin user, default role bindings, adapter/log-source placeholders; re-running
  is a no-op (safe), never resets an existing user's password silently.
- AC-2: Automated post-provision isolation check: the new tenant cannot read any
  other tenant's rows (reuses STORY-365 probe helpers).
- AC-3: Playbook doc (`docs/ops/tenant-onboarding.md`): prerequisites with BAA
  gate as an explicit STOP step (INV-6), script invocation, manual steps,
  verification checklist, rollback.
- AC-4: Provisioning actions write to the STORY-366 admin audit log.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
