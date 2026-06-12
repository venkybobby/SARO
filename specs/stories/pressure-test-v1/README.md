# Pressure-Test Gap Stories v1.0 — Execution Tracker

Source: [`SOURCE.md`](./SOURCE.md) — Marcus Hale Buyer-Critic Pressure Test §4 Gap Analysis (June 2026).
The full Given/When/Then acceptance criteria, edge cases, and out-of-scope notes live in `SOURCE.md`
(Definition of Ready, gate 0 of `/story`, is satisfied there).

Each pressure-test story (PT-###) maps onto prior SARO backlog work. The platform already
implements the bulk of the underlying infrastructure; the work below closes the **remaining gaps**
identified by a per-AC current-state audit.

| PT | Title | Maps to existing | Track | Status |
|----|-------|------------------|-------|--------|
| PT-001 | External SME Validation Chain & QCO Registry | STORY-003/004/007 | code | gap-close |
| PT-002 | Sample-Level Evidence Persistence + PII Redaction | STORY-005 | code | gap-close |
| PT-003 | Framework Citation Correction & Verification Pass | STORY-001 | code/docs | gap-close |
| PT-004 | SOC 2 Type I Readiness & Engagement | STORY-016 | docs | gap-close |
| PT-005 | Canonical Document Register & Claims Reconciliation | STORY-002 | docs | gap-close |
| PT-006 | ISO 42001 Annex Documentation Generator | (new) | code | gap-close |
| PT-007 | Honest NIST AI RMF Coverage Report Endpoint | STORY-011 | code | gap-close |
| PT-008 | Engine Version & Rule-Pack Hash Provenance | STORY-006 | code | gap-close |
| PT-009 | Persona RBAC Enforcement & Tenant Isolation | STORY-008/015 | code | gap-close |
| PT-010 | Tenant-Configurable Risk Weights | STORY-010 | code | gap-close |
| PT-011 | Incident Corpus Quality Dashboard & Similarity Floor | STORY-014 | code | gap-close |
| PT-012 | Vendor Continuity Package — Escrow, Infra Freeze | STORY-009/012/013 | docs/config | gap-close |

## Self-approval note

This batch was executed under an explicit instruction to self-approve and proceed without
per-story confirmation. The engineering standards' independent-review gate is honoured by running
the `reviewer` / `security-auditor` review passes before the PR is opened, and by shipping a pinning
regression test for every bug fixed (FND ledger). No existing test was weakened to reach green.
