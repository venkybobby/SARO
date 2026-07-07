# STORY-DISP-001 — Finding Disposition Lifecycle
Stage: standard

## Lifecycle
- [x] discover   (recon: Notification model + notification_service (dispatch/generate) exist,
                  notifications table 0 rows -> DISP is first real consumer; evf_engagement_service
                  is the state-machine + hash-chained append-only transition-log pattern to mirror
                  (_build_transition_payload, _compute_transition_hash, _write_transition);
                  grc_evidence_records is the evidence FK target (UUID); self_audit.record_event
                  exists for DISPOSITION_ACTION mirroring, META-001)
- [x] shape      (skipped brainstorm — STORY has ACs; interview -> Decision Log below)
- [x] preview    (skipped — backend lifecycle + report API; no new UI surface designed here)
- [x] plan
- [x] build
- [x] verify    (change-debrief.html generated)
- [x] sell       (n/a)

## Decision Log
Q1 state machine? → forward-only OPEN -> ACKNOWLEDGED -> (REMEDIATED | WAIVED | ESCALATED),
  mirroring evf_sme_engagements. Terminal states are REMEDIATED/WAIVED/ESCALATED; an expired
  WAIVED auto-reopens to OPEN with a lineage link (reopened_from_id). Illegal transitions rejected.

Q2 transition log? → append-only disposition_transitions, hash-chained per disposition
  (event_hash = SHA-256(payload + prev_hash)), immutability trigger — reuse the evf pattern verbatim.

Q3 zero-PHI (INV-2)? → dispositions carry only de-identified finding metadata (evidence_record_id,
  rule/gate id, system id, severity) — NEVER observed content. Same for transitions.

Q4 waiver rules? → WAIVED requires justification text + approver + expiry_date. Four-eyes
  (approver distinct from acknowledger) is per-tenant config (saro_disposition_four_eyes, default
  False). Expired waiver -> auto-reopen OPEN with lineage + emit a Notification (AC-3, first consumer).

Q5 recurrence (edge)? → a duplicate finding (same rule+system) links to the prior disposition chain
  (recurrence_count++) rather than spawning unbounded duplicates; recurrence under an ACTIVE waiver
  does NOT auto-escalate in v1 (record it; escalation policy is follow-on).

Q6 bulk ops (edge)? → bulk-acknowledge permitted; bulk-waive FORBIDDEN (each waiver needs its own
  justification). API enforces this.

Q7 async / zero eval-path latency (NFR)? → create_disposition is wired into grc.orchestrator
  run_audit_by_id (after run_audit computes findings, for each FAIL finding) via
  _open_dispositions_for_failures, wrapped in a fail-open try/except so a creation failure never
  blocks the evaluation. (Reviewer B1: this wiring was missing in the first cut and is now added.)

Q8 persona gates (AC-5)? → acknowledge/remediate/waive/escalate map per persona; waive-approval
  authority is per-tenant configurable. v1: risk_officer + ai_auditor + admin may act; compliance_lead
  read-only; waive-approve requires operator/admin (distinct actor under four-eyes).

Q9 report (AC-4)? → findings count, state breakdown, mean time-to-acknowledge, waivers with
  justifications + approvers, reopened-waiver lineage — exportable evidence artifact.

Q10 META-001 tie-in? → each transition also records a DISPOSITION_ACTION self-audit event
  (self_audit.record_access, fail-open) so the disposition log mirrors into the audit spine.

## Deviations
None (no plan reversal).

## Review outcomes (both agents)
- Reviewer VERDICT: REQUEST-CHANGES -> resolved. Security-auditor VERDICT: PASS.
- B1 (reviewer BLOCKER): AC-1 was unwired (create_disposition had no production caller). Fixed:
  grc.orchestrator.run_audit_by_id now opens a disposition per FAIL finding (fail-open). Pinned by
  test_evaluation_failure_opens_disposition. Corrected the untruthful Q7 note.
- SF (both agents): four-eyes compared the waive-actor, not the acknowledger. Fixed: persist
  acknowledged_by; four-eyes now requires approver differ from BOTH acknowledger and actor. Pinned by
  test_four_eyes_blocks_approver_equal_acknowledger.
- SF (security): unbounded waiver expiry could indefinitely suppress a finding. Fixed:
  saro_disposition_max_waiver_days (default 180); reject past/absurd-future expiry. Pinned by
  test_waiver_expiry_bounds.
- NH (both): reopened_from_id dead + report double-counted reopened rows as active waivers. Fixed:
  migration comment corrected (lineage lives in the transition log; column reserved); report
  waivers list now counts only state==WAIVED.
- NH (both): expire-waivers has no scheduler yet — it is an operator-triggered/cron sweep in v1
  (documented); automatic per-request reopen is follow-on.
