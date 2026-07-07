# STORY-DISP-001 — Finding Disposition Lifecycle

Epic: Findings & Remediation (new) | Priority: P1 (shelfware risk post-sale)
Origin: Gap #2 — evaluations that FAIL currently terminate at the finding;
no acknowledge/remediate/waive lifecycle exists (notifications table: 0 rows).

## User Story
As a Risk Officer, I need every failed evaluation to enter a tracked
disposition lifecycle, so that "what did you do about it?" has an evidence-
backed answer for every finding — because dispositions ARE evidence.

## Disposition State Machine (forward-only, mirroring evf_sme_engagements style)
OPEN → ACKNOWLEDGED → (REMEDIATED | WAIVED | ESCALATED)
WAIVED requires: justification text, approver (distinct from acknowledger where
tenant config demands four-eyes), expiry date. Expired waiver → auto-reopens
as OPEN with lineage link.

## Acceptance Criteria

AC-1
Given an evaluation produces a failing gate outcome, When the evidence record
persists, Then a disposition record is created in OPEN state, linked to the
evidence record id, carrying only de-identified finding metadata (INV-2: no
observed content in disposition records).

AC-2
Given an OPEN disposition, When a user with the appropriate persona
acknowledges it, Then state transitions with actor + timestamp, and every
transition is written to an append-only hash-chained transition log
(evf_engagement_transitions pattern).

AC-3
Given a WAIVED disposition, When its expiry date passes, Then it auto-reopens
as OPEN with a lineage reference to the expired waiver, and a notification is
emitted (first real consumer of the notifications table).

AC-4
Given an examiner/auditor query, When dispositions are requested for a time
range, Then SARO produces: findings count, disposition-state breakdown, mean
time-to-acknowledge, waivers with justifications and approvers, and reopened-
waiver lineage — as an exportable evidence artifact.

AC-5
Given persona gates (Persona→Tab Mapping Matrix), When disposition actions are
attempted, Then acknowledge/remediate/waive permissions map per persona;
waive-approval authority is configurable per tenant.

## Edge Cases
- Duplicate findings (same rule, same system, recurring): new finding links to
  prior disposition chain rather than spawning unbounded duplicates; recurrence
  count tracked — recurrence under an active waiver does NOT auto-escalate in
  v1 (record it; escalation policy is follow-on)
- Disposition against evidence record whose rule version is retired (RPV
  interplay): disposition remains valid; report annotates rule status at
  report time vs. finding time
- Bulk operations: bulk-acknowledge permitted; bulk-waive NOT permitted
  (each waiver needs individual justification)

## Out of Scope
- External ticketing sync (Jira/ServiceNow) — adapter follow-on
- SLA policies/escalation matrices per finding severity (follow-on)
- Email/webhook delivery of notifications (this story writes them; delivery
  is a separate story)

## NFRs
- Disposition writes add zero latency to the evaluation path (async, post-
  evidence-persist)
- Transition log immutability trigger-enforced

## Traceability
| Item | Reference |
|---|---|
| State machine + transition log pattern | evf_sme_engagements / evf_engagement_transitions |
| Zero-PHI in dispositions | INV-2 / INV-3 |
| Persona permissions | Persona→Tab Mapping Matrix (Epic 9); persona_permissions table |
| Examiner demand | synthetic-examiner Phase 4: "show me a failure and what happened next" |
| Notifications | notifications table (first consumer) |

### AC → tests → files
| AC | Tests | Implementation |
|---|---|---|
| AC-1 OPEN on failing finding; de-identified; recurrence links | `test_lifecycle_and_transition_chain`, `test_recurrence_links_to_prior_chain` | `disposition_service.create_disposition`; `migrations/034`; `models.Disposition` |
| AC-2 append-only hash-chained transitions; illegal rejected | `test_lifecycle_and_transition_chain` (verify), `test_illegal_transition_rejected` | `_append_transition`, `verify_transition_chain`; migration 034 immutability trigger |
| AC-3 expired waiver auto-reopen + notification | `test_expired_waiver_reopens_and_notifies` | `expire_waivers` (first `notifications` consumer) |
| AC-4 disposition report | `test_report_shape`, `test_api_acknowledge_and_report` | `disposition_report`; `GET /dispositions/report` |
| AC-5 persona gates; waiver rules + four-eyes; no bulk-waive; tenant isolation | `test_waiver_requires_fields_and_four_eyes`, `test_api_no_bulk_waive_endpoint`, `test_api_cross_tenant_404` | `routers/dispositions.py`; `config.saro_disposition_four_eyes` |
| Tenant table registered | `test_every_tenant_scoped_model_is_accounted_for` (TEN-001 guard) | migration 034 RLS policy; `docs/TENANT_ISOLATION.md` |
