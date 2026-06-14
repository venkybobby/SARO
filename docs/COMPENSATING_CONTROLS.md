# SOC 2 Compensating Controls — Solo-Founder / Small-Team Model

> **Status:** v1.0 · CANONICAL · Owner: Venky (Lead) · 2026-06-12 · PT-004
> Documents compensating controls where the small team cannot fully segregate duties. Per SOC 2
> readiness discipline, the constraint is stated explicitly and mitigated — never hidden.

## Constraint

SARO operates with a small team (see CLAUDE.md). A single person (Lead) may hold approval authority
across engineering, security, and compliance decisions. Full segregation of duties is not always
achievable. The following compensating controls reduce the resulting risk.

## Compensating controls

| Risk from limited SoD | Compensating control | Evidence |
|---|---|---|
| Self-approval of code changes | Independent automated review gates: `reviewer` + `security-auditor` agents must approve; CI quality-gates (ratchet, regression manifest, migrations) must pass before merge | `.github/workflows/ci.yml`, `quality-gates.yml`, `docs/engineering-standards.md` |
| Unilateral change to production | All changes flow through PR + CI; deploy is GitHub-Actions-driven (`deploy.yml`), not manual; health smoke gate post-deploy | `deploy.yml` |
| Tampering with audit evidence | Hash-chained TRACE + immutable QCO registry (append-only, DB-trigger protected); export hash covers provenance (PT-008) | `routers/audit_chain.py`, `routers/trace_export.py`, EVF migrations |
| Unlogged privileged action | Every authz denial logged with tenant/user/role/endpoint (PT-009); structured logging on privileged paths | `auth._log_authz_denial` |
| Single point of knowledge | Continuity plan with backup operational coverage + escrow (PT-012) | `VENDOR_CONTINUITY_PLAN.md`, `ESCROW_AGREEMENT.md` |
| Weakening a test to pass | Quality ratchet never goes backward; regression manifest is itself a CI-enforced test; no test deletion without recorded approval | `quality/baseline.json`, `tests/regression/test_manifest_integrity.py` |

## Shared-responsibility inheritance

Host, hypervisor, physical security, and managed-DB backup controls are inherited from Fly.io and
Supabase provider attestations (see `ARCHITECTURE.md` shared-responsibility split). SARO documents
the split rather than claiming controls it does not operate.

## Review

Reviewed at each SOC 2 readiness checkpoint and when team size changes. The auditor receives this
document alongside the readiness roadmap; compensating controls are presented, not concealed.
