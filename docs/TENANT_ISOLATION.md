# SARO Tenant Isolation Report

> **Status:** v1.0 · STORY-TEN-001 · Owner: Jordan Lee (Backend/Infra) · Reviewer: Venky (Lead)
> Provenance: generated 2026-07-06 against Supabase project `fktfhtygvwqlmoazmhdf`; cross-tenant
> suite `tests/test_ten001_cross_tenant_isolation.py` (CI, every PR touching data access).

This is a diligence artifact for a CISO evaluating SARO for a multi-tenant deployment. It records the
architecture decision, the per-table policy inventory, the test matrix that demonstrates (not asserts)
isolation, and the honest residual risks.

## 1. Access-path architecture (recorded decision — AC-4)

**Decision: (a) FastAPI-only.** The browser reaches tenant data **only** through the FastAPI
application. The Supabase publishable (anon) key is **not** used for tenant-scoped browser reads;
there is no sanctioned direct-PostgREST path for tenant data. Direct-Supabase access (posture (b)) is
explicitly **not** implemented and would require a documented exception with customer notice.

```
Browser (React) ──HTTPS──> FastAPI (authz + tenant filter) ──service-role pooler──> Supabase Postgres
                                        │
                                        └── the enforced isolation boundary
```

**Enforced control:** every tenant-scoped query filters
`.filter(Model.tenant_id == current_user.tenant_id)` at the API layer, independent of RLS (defense in
depth, AC-2). `current_user` comes from an authenticated JWT; an unauthenticated request is rejected
(401) before any query. An authenticated user **always** carries a non-null `tenant_id` (`users.tenant_id`
and `audits.tenant_id` are `NOT NULL`), so the filter of a tenant with no data yields **zero rows** — a
tenant sees its own data or nothing, never another tenant's. **Fail-closed.** (Note: the filter is a
value equality, not a NULL check; the invariant is that the value is always a real tenant id.)

**RLS posture (honest disclosure):** RLS is enabled on every table, but it is **inert at runtime** —
the application connects via the Supabase service-role pooler, which bypasses RLS, and nothing sets
`app.current_tenant`. RLS is therefore defense-in-depth that becomes load-bearing only under posture
(b). The API-layer filter is the certified control today.

## 2. Policy inventory (AC-1)

Tenant-scoped tables (carry a `tenant_id` column). After STORY-TEN-001 (migration 032) **every**
tenant-scoped table has a tenant-isolation policy — no table relies on "RLS enabled, zero policies".

| Table | tenant-scoped | RLS policy | Enforced by |
|---|---|---|---|
| audits | ✔ | ✔ (2) | API filter + RLS (DiD) |
| audit_traces | ✔ | ✔ | API filter (+ audit join) |
| scan_reports | ✔ | ✔ | API filter |
| grc_evidence_records | ✔ | ✔ | API filter |
| grc_registry_entries / grc_registry_audit | ✔ | ✔ | API filter |
| registered_ai_systems | ✔ | ✔ | API filter |
| notifications | ✔ | ✔ | API filter |
| insight_actions | ✔ | ✔ | API filter |
| compliance_readiness_items | ✔ | ✔ | API filter |
| policies | ✔ | ✔ | API filter |
| users | ✔ | ✔ | API filter |
| **ai_systems, aims_documents, audit_events, client_configs, github_integrations, hf_sample_queue, tenant_risk_configs** | ✔ | **✔ (added by migration 032 — were zero-policy)** | API filter + RLS (DiD) |
| dispositions | ✔ | ✔ (migration 034) | API filter + RLS (DiD) |
| disposition_transitions | child (scoped via parent disposition) | — (no tenant_id; API scopes the parent) | API filter (parent) |

Global / reference tables (**no** `tenant_id` — intentionally shared, single copy for all tenants,
so RLS policies are deliberately absent):

- Regulation text & mappings: `eu_ai_act_rules`, `governance_rules`, `nist_ai_rmf_controls`,
  `aigp_principles`, `mit_risks`, `ai_incidents`, `sample_findings`, `control_framework_mappings`.
- Product/versioning state: `rule_pack_snapshots` (STORY-RPV-001 — published rule-pack versions are
  global product data), `evf_*` (external-validation state is a single product-level fact per
  framework — see COMPLIANCE_CLAIMS_MATRIX EVF section).
- `tenants` itself is the tenancy root (no self-referential tenant_id).

## 3. Test matrix (AC-3) — the sanctioned access path

Under posture (a) the **only** sanctioned tenant-data path is FastAPI. The direct-PostgREST /
publishable-key path is defended by *absence* — the React frontend ships **no** Supabase client
(no `@supabase/supabase-js` / `createClient` import; pinned by
`test_frontend_has_no_direct_supabase_client`), so there is no browser→DB path to test. This matrix
demonstrates isolation on the FastAPI path with synthetic TENANT-A and TENANT-B
(`tests/test_ten001_cross_tenant_isolation.py`); it does not claim to exercise a PostgREST path that
does not exist.

| FastAPI path | Read own tenant | Read foreign id | Absent tenant ctx |
|---|---|---|---|
| `GET /api/v1/audits` (list) | ✅ only own rows | — | ✅ empty (fail-closed) |
| `GET /api/v1/audits/{id}` (detail) | ✅ | ✅ generic 404 | — |
| `GET /api/v1/audit/{id}/trace` (TRACE) | ✅ | ✅ generic 404 | — |
| `GET /api/v1/output/{id}` (verbatim prompt + raw output) | ✅ | ✅ generic 404 | — |
| `GET /api/v1/evidence/{id}/criteria` (RPV-002) | ✅ | ✅ generic 404 | — |

Foreign-id reads return a **generic 404** identical to a nonexistent id — no existence oracle.
**Covered-by-pattern (verified by code audit, not each individually tested):** all other tenant-scoped
read handlers (`dashboard`, `traces`, `remediation`, `output_audit`, `github_integration`,
`audit_chain`, `insights`, `controls`, `compliance_hub`, `systems`, `reports`, `trace_export`, `aims`)
enforce the same `.filter(tenant_id == current_user.tenant_id)` (directly or via a tenant-gated parent
audit). A schema-completeness guard (`test_every_tenant_scoped_model_is_accounted_for`) fails CI if a
new tenant-scoped table is added without being registered here. The suite runs in CI on every PR that
touches data access.

## 4. Residual risks (honest gaps)

- **RLS inert at runtime.** The added policies are defense-in-depth only until/unless posture (b) is
  sanctioned; the API-layer filter is the enforced control. Documented, not hidden.
- **Integer-PK volume signal.** Legacy tables with sequential integer PKs can leak row-count/volume
  signals across tenants via id ranges. Migration to UUID PKs is follow-on work, **not** this story.
- **SSO persona trust boundary** (FND-043): a privileged `persona_role` from a SAML assertion is not
  yet allow-list-validated; tracked separately.
- **Storage buckets / edge functions:** none in use for tenant data at this time; re-audit if added.

## 5. Change control

Any move to posture (b) (direct browser→Supabase) requires: a documented exception, customer notice,
promotion of RLS to the certified control (with `app.current_tenant` set per request), and an update
to the AC-3 test matrix to exercise the publishable-key path directly. Until then, this report is the
source of truth for SARO's tenant-isolation posture.
