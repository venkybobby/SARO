# STORY-META-001 — SARO Self-Audit: Governance of the Governance Tool

Epic: Security Hardening | Priority: P1 — SOC 2 spine; procurement gate
Origin: Gap #6 — audit_events table is empty; who viewed evidence, who changed
rules, who exported what is currently unanswerable. Today's rule-pack
mutation (2026-07-04) would have appeared here — and didn't.

## User Story
As a Compliance Lead (and as SARO's own future SOC 2 auditor), I need a
complete, immutable audit trail of privileged and sensitive actions WITHIN
SARO, so that the platform can survive the same scrutiny it applies to its
customers' AI systems.

## Audited Action Classes (v1 closed set)
1. RULE_PACK_CHANGE — any write to rule tables or snapshot publication (RPV)
2. EVIDENCE_ACCESS — read/export of evidence records, coverage reports,
   criteria reproductions (read-auditing on evidence, not on all data)
3. DISPOSITION_ACTION — acknowledge/remediate/waive (mirror of DISP-001 log)
4. ADMIN_ACTION — persona/permission changes, tenant config changes,
   validation_status transitions, adapter credential changes
5. AUTH_EVENT — privileged login, failed privileged attempts, role assumption
6. EXPORT — any artifact generation leaving the platform (statements, reports)

## Acceptance Criteria

AC-1
Given any action in the closed set, When it executes through the API layer,
Then an audit event persists to audit_events (finally populating it) with:
actor, tenant scope, action class, target identifier, timestamp, and outcome —
metadata only, never payload content (INV-2/INV-3 apply to the audit trail
itself; an audit log that copies evidence content becomes a retention
violation).

AC-2
Given audit_events rows, When any UPDATE or DELETE is attempted, Then it is
rejected by trigger (schema_migrations / evf transition-log immutability
pattern), and the table is hash-chained per tenant stream.

AC-3
Given direct database access exists (Supabase dashboard, MCP, psql — the path
used on 2026-07-04), When rule tables or evidence tables are written outside
the API layer, Then database-level triggers capture a RULE_PACK_CHANGE /
equivalent event with actor = database role + connection metadata. Out-of-band
changes must be visible, not just discouraged. (Gap acknowledged: a
sufficiently privileged actor can disable triggers — document this residual
risk honestly in the security whitepaper; mitigation is role separation, not
pretense.)

AC-4
Given an audit query interface (internal, AI Auditor persona), When filtered
by actor, action class, target, or time range, Then results return with chain-
verification status; exportable as evidence artifact — and the export itself
generates an EXPORT event (self-referential by design).

AC-5
Given retention configuration, When audit events age past tenant-configured
retention (with a floor meeting SOC 2 expectations, default 1 year hot),
Then archival — never silent deletion — with archival events recorded.

## Edge Cases
- Audit write failure: privileged/admin actions FAIL CLOSED (action rejected
  if unauditable); evaluation-path evidence reads fail open with a data-quality
  alarm (availability of customer's compliance function beats SARO's
  self-audit completeness — document this tradeoff explicitly)
- High-volume EVIDENCE_ACCESS (bulk report): one event per logical request
  with record-count, not per row
- The migration applied via MCP on 2026-07-04: backfill two synthetic
  RULE_PACK_CHANGE events referencing the tracked migrations, flagged
  RETROACTIVE — the trail's own first entries demonstrate honest backfill
  practice

## Out of Scope
- SIEM export/streaming (follow-on adapter)
- Full SOC 2 control implementation (this is the evidence spine, not the program)
- Anomaly detection on audit streams

## NFRs
- Audit writes < 5ms overhead per privileged action; async where fail-open,
  synchronous where fail-closed
- Chain verification over 1M events < 60s

## Traceability
| Item | Reference |
|---|---|
| Empty table observed | audit_events (0 rows), Supabase discovery 2026-07-04 |
| Immutability pattern | schema_migrations trigger; evf_engagement_transitions |
| Out-of-band precedent | This session's MCP-applied migrations |
| Procurement demand | design-partner-wargamer PROCUREMENT persona; SOC 2 path |
| Zero-PHI in audit trail | INV-2 / INV-3 |
