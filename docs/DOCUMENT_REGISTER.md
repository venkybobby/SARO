# SARO Canonical Document Register

> **Status:** v1.0 · CANONICAL · Owner: Venky (Lead) · 2026-06-12 · PT-005 (also serves PT-004, PT-012)
> Single source of truth for the status of every governance document. Exactly one canonical status
> per gap (IR plan, DPA, SME validation, infrastructure). Superseded documents carry a SUPERSEDED
> header pointing to their canonical replacement. Consistency is checked by
> `tests/test_pt005_doc_register.py`.

## Canonical status per gap

| Gap | Canonical document | Status |
|---|---|---|
| Infrastructure of record | `docs/ARCHITECTURE.md` | CANONICAL (Fly.io + Supabase + Postgres staging) |
| Incident Response plan | `docs/incident-response-plan.md` | CANONICAL |
| Data Processing Agreement | `docs/legal/saro-dpa-template-v1.0.md` | CANONICAL template |
| SME / EVF validation status | `docs/COMPLIANCE_CLAIMS_MATRIX.md` §EVF + QCO Registry API | CANONICAL (all frameworks: Internal Review Only) |
| Framework citations | `docs/CITATION_INVENTORY.md` | CANONICAL |
| NIST coverage | `docs/nist-coverage-rubric.md` + `GET /reports/nist-coverage` | CANONICAL |
| Scoring methodology | `docs/how-saro-reasons.md` | CANONICAL |
| SOC 2 readiness | `docs/soc2-readiness-roadmap-v1.0.md` | CANONICAL (readiness, not attestation) |
| Compensating controls | `docs/COMPENSATING_CONTROLS.md` | CANONICAL |
| Vendor continuity / escrow | `docs/VENDOR_CONTINUITY_PLAN.md`, `docs/ESCROW_AGREEMENT.md` | CANONICAL |
| Sample-evidence retention | `docs/sample-evidence-retention.md` | CANONICAL |

## Full register

| Document | Version | Date | Owner | Status | Supersedes |
|---|---|---|---|---|---|
| ARCHITECTURE.md | 1.0 | 2026-06-12 | Jordan Lee | CANONICAL | deployment-context.md; Railway/Koyeb/Neon refs |
| DOCUMENT_REGISTER.md | 1.0 | 2026-06-12 | Venky | CANONICAL | — |
| CLAIMS_AUDIT_LOG.md | 1.0 | 2026-06-12 | Venky | CANONICAL | — |
| COMPENSATING_CONTROLS.md | 1.0 | 2026-06-12 | Venky | CANONICAL | — |
| VENDOR_CONTINUITY_PLAN.md | 1.0 | 2026-06-12 | Venky | CANONICAL | — |
| ESCROW_AGREEMENT.md | 1.0 | 2026-06-12 | Venky | CANONICAL (terms; signature pending) | — |
| CITATION_INVENTORY.md | 1.0 | 2026-06-12 | Venky | CANONICAL | — |
| nist-coverage-rubric.md | 1.0 | 2026-06-12 | Alex Rivera | CANONICAL | — |
| sample-evidence-retention.md | 1.0 | 2026-06-12 | Jordan Lee | CANONICAL | — |
| COMPLIANCE_CLAIMS_MATRIX.md | 8.0.0 | 2026-06-02 | Venky | CANONICAL | — |
| how-saro-reasons.md | — | 2026-06-12 | Alex Rivera | CANONICAL | — |
| incident-response-plan.md | — | — | Jordan Lee | CANONICAL | incident-response.md (root) |
| legal/saro-dpa-template-v1.0.md | 1.0 | — | Venky | CANONICAL | DPA_interim_v0.md, DPA_interim_v0.1.md |
| soc2-readiness-roadmap-v1.0.md | 1.0 | — | Venky | CANONICAL | — |
| deployment-context.md | — | — | Jordan Lee | SUPERSEDED → ARCHITECTURE.md | — |
| MIGRATION_RUNBOOK.md | — | 2026-05-08 | Jordan Lee | ARCHIVED (migration complete) | — |
| DPA_interim_v0.md | 0 | — | Venky | SUPERSEDED → legal/saro-dpa-template-v1.0.md | — |
| DPA_interim_v0.1.md | 0.1 | — | Venky | SUPERSEDED → legal/saro-dpa-template-v1.0.md | — |

## Rules

1. A new governance document is added here in the same change that creates it.
2. Replacing a document: mark the old one SUPERSEDED with a pointer; never silently revise an
   externally-shared document — issue errata instead.
3. Any stack reference must match `ARCHITECTURE.md`.
