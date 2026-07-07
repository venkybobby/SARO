# STORY-MTR-001 — PHI-Free Usage Metering
Stage: standard

## Lifecycle
- [x] discover   (recon: Notification model + notification_service exist; evf_expiry_notifications
                  idempotency_key UNIQUE pattern to reuse; grc_evidence_records is the authoritative
                  count source for reconciliation; DISP-001 async-post-evidence posture is the model;
                  RPV-002 reproduce endpoint is a metered surface (criteria_reproductions);
                  TEN-001 schema-completeness guard will require registering the new tenant table)
- [x] shape      (skipped brainstorm — STORY has ACs; interview -> Decision Log below)
- [x] preview    (skipped — backend meters + statement API; no new UI surface)
- [x] plan
- [x] build
- [x] verify    (change-debrief.html generated)
- [x] sell       (n/a)

## Decision Log
Q1 PHI-free by construction (AC-1)? → meter records carry ONLY: tenant_id, meter_key (closed set),
  period_bucket, count, and dimension tags from a CLOSED vocabulary (gate_id, vertical, adapter_id,
  outcome). NO free-text fields — validated at write; unknown meter_key or dimension key raises.
  PHI leakage is structurally impossible (INV-2 by construction, not by redaction).

Q2 meter set (v1)? → evaluations_executed, attestations_issued, evidence_records_persisted,
  coverage_report_generations, criteria_reproductions, active_observed_systems (high-water per
  period), adapter_observation_volume (COUNT ONLY, never content).

Q3 async posture (AC-2, NFR)? → increments emitted post-evidence-persist, best-effort; a metering
  failure NEVER fails/delays an evaluation (lost increments acceptable; blocked evals are not).
  Loss is bounded + measured by reconciliation (AC-5).

Q4 idempotency (edge)? → idempotency_key per logical invocation (UNIQUE) so retries don't
  double-count — reuse the evf_expiry_notifications pattern. Multi-tenant shared rule-pack reads are
  NOT metered (cost of goods, not usage).

Q5 usage statement (AC-3)? → per-tenant, per-period artifact: meter totals, period, generation
  timestamp, content_hash (usage statements are evidence too — disputes are audits). UTC period
  bucketing at emission (tenant-local display is presentation-layer). Immutable once issued;
  corrections are new adjustment records, never edits.

Q6 thresholds (AC-4)? → threshold-crossing events recorded + a Notification emitted; v1 RECORDS and
  NOTIFIES, does NOT enforce cutoffs (never silently drop a healthcare tenant's evaluations).
  Config saro_metering_thresholds is per-meter soft limits.

Q7 reconciliation (AC-5)? → daily cross-check of meter totals vs authoritative row counts
  (grc_evidence_records for evidence_records_persisted; dispositions/attestations where applicable);
  drift beyond 0.5% raises a data-quality finding (Notification type='data_quality').

Q8 tenant isolation? → usage_meters is tenant-scoped -> RLS policy (migration 035) + register in the
  TEN-001 schema-completeness guard + docs/TENANT_ISOLATION.md (the guard enforces this).

## Deviations
None (no plan reversal).

## Review outcomes (both agents)
- Reviewer VERDICT: REQUEST-CHANGES -> resolved. Security-auditor VERDICT: PASS.
- B1 (reviewer BLOCKER): reconcile compared a period-scoped meter vs an ALL-TIME authoritative
  count -> false positive once a tenant spans >1 period. Fixed: authoritative count is period-scoped
  via _period_range(created_at). Pinned by test_reconcile_is_period_scoped.
- SF (reviewer): check_threshold had no runtime caller (AC-4 half-delivered). Fixed: wired into
  safe_increment (best-effort, post-increment). Pinned by test_safe_increment_fires_threshold.
- SF (reviewer): evaluations_executed metered without an idempotency key -> retry double-count.
  Fixed: idempotency_key=f"eval:{record.id}". Pinned by test_eval_style_idempotency_dedup.
- SF (reviewer): daily reconcile has no scheduler -> documented as out-of-scope (endpoint = manual
  trigger; cron/CI wiring is ops follow-on).
- SF (security): dimension VALUES were unbounded (PHI-free was key-only). Fixed: bounded scalars +
  64-char cap + closed per-key allow-lists. FND-045 (pinned regression).
- NH: limit==0 treated as unset -> `if limit is None`; period query param validated (422 on bad
  format); TENANT_ISOLATION/migration doc corrected (idempotency keys must be globally unique).
