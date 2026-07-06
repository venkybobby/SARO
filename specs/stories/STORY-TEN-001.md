# STORY-TEN-001 — Tenant Isolation: Policies, Proof, and the Isolation Report

Epic: Security Hardening | Priority: P0 — CISO-facing, discoverable in diligence
Origin: Gap #3 — RLS shows "enabled" on all 47 tables but enabled ≠ policies
written and tested; tenants table has 1 row (isolation never exercised); the
Supabase frontend migration makes RLS load-bearing.

## User Story
As SummitCare's CISO evaluating SARO, I need demonstrated (not asserted)
tenant isolation, so that a multi-tenant deployment cannot leak evidence,
findings, or configuration across tenants under any access path.

## Acceptance Criteria

AC-1
Given all tenant-scoped tables, When RLS policies are audited, Then every
table has explicit per-operation policies (SELECT/INSERT/UPDATE/DELETE) keyed
on tenant identity, and an inventory artifact lists each table with its policy
— including which tables are intentionally global (e.g., published rule-pack
snapshots) with rationale. No table may rely on "RLS enabled, zero policies."

AC-2
Given the FastAPI access path, When queries execute, Then tenant scoping is
enforced at the API layer INDEPENDENTLY of RLS (defense in depth): service-role
connections must set tenant context explicitly; a request without tenant
context fails closed.

AC-3
Given a synthetic second tenant (TENANT-B) with seeded data mirroring TENANT-A
structure, When the cross-tenant test suite runs, Then it attempts reads and
writes across tenant boundaries through EVERY access path — direct PostgREST/
publishable key (browser path), authenticated user JWT, FastAPI endpoints —
and asserts zero leakage. Suite runs in CI on every PR touching data access.

AC-4
Given the frontend-direct-to-Supabase question (open architecture decision),
When this story completes, Then the decision is forced and recorded: either
(a) browser talks only to FastAPI and the publishable-key path is verified to
expose nothing tenant-scoped, or (b) direct access is sanctioned and RLS
policies are the certified control. The test suite in AC-3 must match the
chosen architecture. Stop-and-ask to product owner before implementing (b).

AC-5
Given the suite passes, When the Tenant Isolation Report is generated, Then it
contains: architecture diagram of access paths, policy inventory, test matrix
(path × operation × table class) with results, and run provenance — formatted
as a sales/diligence artifact (sales-engineer skill corpus item).

## Edge Cases
- Aggregate/count queries leaking existence via row counts across tenants
- Storage buckets and edge functions (if any) — same isolation audit
- evf_* and audit tables: append-only + tenant-scoped simultaneously
- Sequence/id probing: integer PKs on legacy tables leak volume signals across
  tenants — note in report; migration to UUID is follow-on, not this story

## Out of Scope
- SOC 2 controls beyond isolation (META/SOC2 track)
- Per-tenant encryption keys (roadmap item; note in report as planned)
- Performance isolation / noisy-neighbor (separate NFR story)

## NFRs
- Cross-tenant suite completes < 5 min in CI
- Zero production-behavior change for single-tenant deployments (SummitCare
  VPC posture unaffected)

## Traceability
| Item | Reference |
|---|---|
| RLS state observed | Supabase discovery 2026-07-04 (47 tables rls_enabled, 1 tenant row) |
| Frontend architecture question | Supabase migration session flag (React→FastAPI→DB vs direct) |
| Buyer objection | design-partner-wargamer CISO persona; Hale deal conditions |
| Sales artifact | sales-engineer grounding corpus |
| Deployment posture | SummitCare us-east-1 VPC / PrivateLink decisions |
