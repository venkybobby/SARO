# STORY-META-001 — SARO Self-Audit: Governance of the Governance Tool
Stage: standard

## Lifecycle
- [x] discover   (recon: audit_events table + AuditEvent ORM model exist (event_type/event_data,
                  0 rows live); several routers already append unchained events (clients/sso/
                  remediation/insights/compliance_hub). services/audit_emitter.py is a SEPARATE
                  in-memory SIEM emitter (Epic 14 governance-runtime allow/block), NOT this table.
                  grc/evidence.py is the DB-persisted per-tenant hash-chain pattern to reuse.)
- [x] shape      (skipped brainstorm — STORY has ACs; interview -> Decision Log below)
- [x] preview    (skipped — backend spine + query API; no new UI surface)
- [x] plan
- [x] build
- [x] verify    (change-debrief.html generated)
- [x] sell       (n/a)

## Decision Log
Q1 new table or extend audit_events? → EXTEND audit_events (migration 033) with the META-001
  columns (action_class, target_type, target_id, outcome, actor, seq, prev_hash, event_hash,
  retroactive), keeping event_type/event_data for the existing unchained writers. New self-audit
  events use the full chained schema; old writers keep working (append-only).

Q2 hash-chain mechanism? → REUSE the grc/evidence.py DB pattern (per-tenant seq + content_hash +
  chain_hash), NOT the in-memory audit_emitter. Content-free: the hashed payload is metadata only
  (actor, action_class, target, outcome, timestamp) — never payload content (INV-2/INV-3 apply to
  the audit trail itself; an audit log that copies evidence content is a retention violation).

Q3 immutability? → DB trigger rejects UPDATE/DELETE (append-only, like migration 012/025) + the
  service exposes only record/query/verify. Per-tenant chain (unique(tenant_id, seq)).

Q4 fail-closed vs fail-open (edge)? → record_privileged() FAILS CLOSED (raises; the privileged
  action aborts if unauditable). record_access() FAILS OPEN with a data-quality log (customer's
  compliance function availability beats SARO's self-audit completeness — documented tradeoff).

Q5 which action classes are wired now (scope)? → the story's out-of-scope says "evidence spine, not
  the program". Wire the classes the codebase surfaces cleanly: RULE_PACK_CHANGE (rule-pack publish),
  EXPORT + EVIDENCE_ACCESS (evidence-criteria read/export, self-referential EXPORT-of-export).
  ADMIN_ACTION/AUTH_EVENT get the helper but full wiring is incremental; DISPOSITION_ACTION is
  DISP-001's log (AC-1 names it a mirror). One event per logical request (bulk = record-count, AC edge).

Q6 out-of-band DB writes (AC-3)? → a DB trigger on eu_ai_act_rules/governance_rules inserts a
  RULE_PACK_CHANGE audit_event with actor = 'db:'||current_user when rules are written outside the
  API (the 2026-07-04 path). Residual risk (a superuser can disable the trigger) documented honestly,
  not pretended away — mitigation is role separation.

Q7 backfill (AC edge)? → migration 033 seeds 2 synthetic RETROACTIVE RULE_PACK_CHANGE events
  referencing the tracked radar migrations, flagged retroactive=TRUE, for the existing tenant — the
  trail's own first entries demonstrate honest backfill.

Q8 retention (AC-5)? → config saro_audit_retention_days (default 365 hot); archival-not-deletion is
  the policy — record the intent + a note that the archival job is follow-on (spine, not program).

## Deviations
None (no plan reversal). Live-apply caught a real bug (audit_events.id had only an ORM-level
default, so raw-SQL backfill + the out-of-band trigger inserts failed NOT NULL — added
ALTER COLUMN id SET DEFAULT gen_random_uuid() to the migration). SQLite NUMERIC affinity
coerced an all-numeric SYSTEM tenant UUID to int on readback -> gave the SYSTEM tenant a
leading-'a' UUID (Postgres unaffected).

## Review outcomes (both agents)
- Reviewer VERDICT: APPROVE. Security-auditor VERDICT: PASS. No blockers.
- Should-fixes addressed in-PR:
  - Retention config was declared but unused (AC-5) -> added find_archival_candidates +
    record_retention_sweep (archival-not-deletion: records an ADMIN_ACTION archival event,
    NEVER deletes). Pinned by test_retention_sweep_records_archival_and_never_deletes.
  - Postgres-only triggers (immutability AC-2 + out-of-band AC-3) had no CI guard -> added
    test_migration_033_defines_immutability_and_oob_capture (static DDL guard) complementing
    the live Supabase verification (immutability rejects UPDATE, out-of-band fires w/ row_count).
- Nice-to-haves: renamed the shadowing route handler (verify_chain_endpoint); documented the
  genesis-race window in _chain_tail; moved the self_audit imports to module level.
