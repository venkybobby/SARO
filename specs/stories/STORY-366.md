# STORY-366: Immutable Admin & Configuration Audit Log

**Status:** ready
**Screen/Area:** Backend + migration; Compliance Hub read view deferred (Pack Epic 15)
**Ground truth:** `services/self_audit.py` exists (self-audit writes); an
`audit_events`-style table exists but usage is narrow. This story generalizes to
every admin/config mutation with append-only enforcement at the policy level.

## Goal
Every admin/config action (rule-pack publish, tenant change, role change,
adapter/log-source config) lands in an append-only audit log — SARO's own
operations meet the evidentiary bar SARO sells.

## Acceptance Criteria
- AC-1: Append-only `admin_audit_log` table (migration): actor, action, target
  type+id, timestamp, before/after SHA-256 hashes; REVOKE UPDATE/DELETE +
  RLS policy denies update/delete (Supabase-level enforcement).
- AC-2: All admin mutation endpoints write to it; a registry-driven test fails
  if a mutating admin route lacks an audit write.
- AC-3: Read endpoint (`GET /api/v1/admin/audit-log`, privileged read) for the
  Compliance Hub view; UI wiring deferred pending saro-screen-review (D7).
- AC-4: INV-2 note: log stores hashes + identifiers only — no payload/body
  content possible by construction.

## Out of Scope
- Frontend surface (follow-up after screen review).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
