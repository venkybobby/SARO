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
| AC-1 | `test_provisioning_creates_tenant_admin_and_placeholder`, `test_reprovisioning_the_same_slug_writes_nothing`, `test_reprovisioning_does_not_reset_the_admin_password`, `test_existing_admin_email_is_refused_not_adopted` | `services/tenant_provisioning.py`, `cli.py` (`tenant provision`) |
| AC-2 | `test_new_tenant_sees_no_other_tenants_rows`, `test_isolation_check_reports_when_it_cannot_prove_anything` | `verify_isolation`, `cli.py` (`tenant verify-isolation`) |
| AC-3 | `test_provisioning_refuses_without_baa_confirmation`, `test_baa_refusal_names_the_artifact_to_check`, `test_playbook_documents_invocation_verification_and_rollback` | `docs/ops/tenant-onboarding.md` |
| AC-4 | `test_provisioning_writes_an_admin_audit_event`, `test_audit_metadata_never_contains_the_generated_password` | STORY-366 audit write on the SYSTEM chain |

## Design notes
- **Idempotency = inert, not re-applied.** A re-run against an existing slug
  writes nothing and reports what exists; it does NOT reconcile drift. FND-058
  is the cautionary case — matching a weak key and silently reassigning
  tenant/role/password. Operators re-run when unsure, so "safe" must mean inert.
- **BAA gate in code.** `provision` refuses without `--baa-confirmed`, naming
  the artifact to check. INV-6 as a checklist item gets skipped under pressure.
- **Generated password shown once**, never stored/logged/serialized — absent
  from `--json`, from the audit metadata, and from `summary()`. Pinned by test.
- **Email collision refused, not adopted** — again FND-058's lesson.
- **Isolation check reports when it cannot prove anything** (`meaningful: false`
  for a lone tenant) rather than passing vacuously.
- **No `tenant delete` command** — destroying evidence should require thought,
  not a flag; the playbook's rollback stops if any audit records exist.

## Human gates surfaced (in the playbook, not blocking this story)
FND-067 (no tenant security-contact field), the unset backup responder, and
SLA counsel review — all listed in §6 of the playbook as onboarding-affecting
open items.
