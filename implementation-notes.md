# STORY-TEN-001 — Tenant Isolation: Policies, Proof, and the Isolation Report
Stage: standard

## Lifecycle
- [x] discover   (recon: isolation is enforced APP-LAYER via .filter(Model.tenant_id ==
                  current_user.tenant_id); RLS is INERT at runtime — nothing sets
                  app.current_tenant, service-role pooler bypasses RLS (policy_service.py note,
                  test_tenant_isolation.py). Live inventory: 12 tenant-scoped tables have policies,
                  7 tenant-scoped tables have RLS-enabled-but-ZERO-policies; rules/evf_*/snapshots
                  are global (no tenant_id) by design.)
- [x] shape      (skipped brainstorm — STORY has ACs; interview -> Decision Log below)
- [x] preview    (skipped — the deliverable IS a report doc; no interactive UI surface)
- [x] plan
- [x] build
- [x] verify    (change-debrief.html generated; the SELL artifact is docs/TENANT_ISOLATION.md)
- [x] sell       (docs/TENANT_ISOLATION.md is the diligence artifact)

## Decision Log
Q1 architecture (AC-4, stop-and-ask before (b))? → (a) FastAPI-only, owner-locked. Browser talks
  only to FastAPI; the Supabase publishable key is NOT used for tenant-scoped browser reads. RLS is
  defense-in-depth, not the certified control. (b) direct-Supabase is explicitly NOT implemented.

Q2 primary isolation control? → API-layer .filter(tenant_id == current_user.tenant_id) on every
  tenant-scoped query, independent of RLS (AC-2 defense-in-depth). Fail-closed: no authenticated user
  -> 401; a user with tenant_id=None filters to zero rows (== None matches nothing), never a leak.

Q3 the 7 zero-policy tenant-scoped tables (AC-1 "no table may rely on RLS-enabled-zero-policies")? →
  migration 032 adds tenant-isolation RLS policies (USING + WITH CHECK on tenant_id vs
  app.current_tenant) mirroring the existing 12, so the inventory shows a policy on EVERY
  tenant-scoped table. Inert at runtime like the rest (service-role bypass) but closes the gap and is
  correct if RLS ever becomes load-bearing. Global tables (no tenant_id) stay policy-free WITH
  rationale in the report.

Q4 cross-tenant proof (AC-3)? → tests/test_ten001_cross_tenant_isolation.py seeds TENANT-A + TENANT-B
  and drives the FastAPI access path (the only sanctioned path under posture (a)): audits list/detail,
  TRACE timeline, evidence-criteria (RPV-002). Asserts zero leakage + generic 404 for a foreign id
  (no existence oracle) + fail-closed on absent tenant context. Runs in CI (marked, under tests/).

Q5 report (AC-5)? → docs/TENANT_ISOLATION.md: access-path architecture, recorded (a) decision, policy
  inventory table (per-table: rls / policies / tenant-scoped-or-global + rationale), test matrix
  (path × operation × table-class), run provenance, and honest residual risks (RLS inert at runtime;
  integer-PK volume signal on legacy tables — UUID migration is follow-on, not this story).

## Deviations
None (no plan reversal). Review-driven hardening applied in-PR (below).

## Review outcomes (both agents)
- Reviewer VERDICT: APPROVE (mutation-tested the suite — dropping a tenant filter fails it).
- Security-auditor VERDICT: PASS (no exploitable leak; verified every tenant-scoped read path).
- Fixes applied in-PR:
  - SF (both): report's "== None matches nothing" was technically wrong (SQLAlchemy renders IS NULL).
    Reworded to the true invariant (users/audits.tenant_id NOT NULL -> filter yields own-or-empty).
    Also added nullable=False to Audit.tenant_id (aligns ORM with live NOT NULL; hardens the invariant).
  - SF (both): "EVERY access path" over-claim removed. Report §3 now scopes to the FastAPI path (the only
    sanctioned path under posture (a)), lists other handlers as covered-by-pattern (code-audited), and
    pins posture (a) with a frontend-no-Supabase-client guard test. Added the most sensitive path
    (GET /output/{id} verbatim prompt+raw output) to the suite.
  - NH (security): aims.py get_evidence_pack now rechecks audit.tenant_id (the one Audit fetch lacking it).
  - NH (both): schema-driven guard test (test_every_tenant_scoped_model_is_accounted_for) fails CI if a
    new tenant-scoped ORM table appears unregistered -> AC-1 stays enforced, not a point-in-time claim.
  - Info (security, pre-existing, outside diff): hardcoded default EXPORT_HMAC_secret -> logged FND-044 (open).
  - Marker note: suite uses `integration` to match the repo convention for TestClient/DB-backed tests
    (test_rpv_*_api, test_chub011 all do); pytest.ini's "live Supabase" wording is already loose repo-wide.
