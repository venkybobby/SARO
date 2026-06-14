# Pressure-Test Gap Stories v1.0 — Execution Tracker

Source: [`SOURCE.md`](./SOURCE.md) — Marcus Hale Buyer-Critic Pressure Test §4 Gap Analysis (June 2026).
The full Given/When/Then acceptance criteria, edge cases, and out-of-scope notes live in `SOURCE.md`
(Definition of Ready, gate 0 of `/story`, is satisfied there).

Each pressure-test story (PT-###) maps onto prior SARO backlog work. The platform already
implements the bulk of the underlying infrastructure; the work below closes the **remaining gaps**
identified by a per-AC current-state audit.

| PT | Title | Maps to existing | Track | Gap closed in this batch |
|----|-------|------------------|-------|--------|
| PT-001 | External SME Validation Chain & QCO Registry | STORY-003/004/007 | code | QCO pinned to rule-pack hash + `qco_rule_pack_is_current`, findings summary, migration 022. (SME ≥2 enforcement / evidence-package export remain follow-ups.) |
| PT-002 | Sample-Level Evidence Persistence + PII Redaction | STORY-005 | code | Signal-level dedupe at persistence + retention/redaction policy doc. (Core persistence + PII redaction already shipped.) |
| PT-003 | Framework Citation Correction & Verification Pass | STORY-001 | code/docs | Citation inventory + CI lint + Gate-1 docstring fix. |
| PT-004 | SOC 2 Type I Readiness & Engagement | STORY-016 | docs | Compensating-controls doc + doc register; engagement-letter signature is a process follow-up. |
| PT-005 | Canonical Document Register & Claims Reconciliation | STORY-002 | docs | DOCUMENT_REGISTER, ARCHITECTURE (canonical Fly.io+Supabase), CLAIMS_AUDIT_LOG, supersession headers. |
| PT-006 | ISO 42001 Annex Documentation Generator | (new) | code | NOT-COVERED section, provenance stamp, min-evidence refusal. (Lead-auditor QCO gating is a process follow-up.) |
| PT-007 | Honest NIST AI RMF Coverage Report Endpoint | STORY-011 | code | Coverage `mapped` derived mechanically from triggers + pinned against drift; version + N-of-68 summary; rubric. |
| PT-008 | Engine Version & Rule-Pack Hash Provenance | STORY-006 | code | Provenance now inside the signed `export_hash`; pre-provenance sentinel; PDF footer. |
| PT-009 | Persona RBAC Enforcement & Tenant Isolation | STORY-008/015 | code | FND-009 allowlist, FND-010 LIKE-injection fix, authz logging, 60-session isolation test. |
| PT-010 | Tenant-Configurable Risk Weights | STORY-010 | code | Degenerate-weight rejection, Risk Officer RBAC, 0.80-cap rationale. |
| PT-011 | Incident Corpus Quality Dashboard & Similarity Floor | STORY-014 | code | Below-floor suppression, source breakdown, staleness warning. (Floor kept at pinned 0.15; 0.30 pending data.) |
| PT-012 | Vendor Continuity Package — Escrow, Infra Freeze | STORY-009/012/013 | docs/config | Continuity + escrow docs, infra freeze verified (`auto_stop_machines='off'`), legacy refs superseded. |

**Found & fixed en route:** FND-011 — FastAPI `dependency_overrides` leaked across tests; the suite
previously passed only by collection-order luck. Fixed with a conftest snapshot/restore + default
SQLite `get_db`. Pinned.

## Self-approval note

This batch was executed under an explicit instruction to self-approve and proceed without
per-story confirmation. The engineering standards' independent-review gate is honoured by running
the `reviewer` / `security-auditor` review passes before the PR is opened, and by shipping a pinning
regression test for every bug fixed (FND ledger). No existing test was weakened to reach green.
