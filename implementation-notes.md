# STORY-COV-001 — Observation-Gap (Coverage) Attestations
Stage: standard

## Lifecycle
- [x] discover   (recon: no STORY-406 adapter exists (stories stop at 404) -> AC-1 live-adapter
                  heartbeat wiring is DEFERRED per the owner decision; grc/evidence hash-chain +
                  self_audit + metering patterns available to reuse; INV-2 = positions/timestamps
                  only, never content; TEN-001 schema-completeness guard requires registering new
                  tenant tables)
- [x] shape      (skipped brainstorm — STORY has ACs; interview -> Decision Log below)
- [x] preview    (skipped — backend coverage engine + report API; no new UI surface)
- [x] plan
- [x] build
- [x] verify    (change-debrief.html generated)
- [x] sell       (n/a)

## Decision Log
Q1 scope (owner-locked)? → build the ADAPTER-INDEPENDENT core: checkpoint interface, gap records
  with cause classes, SARO_OUTAGE self-detect, lag p50/p95/max, coverage report. DEFER AC-1's live
  Bedrock-adapter heartbeat emission until STORY-406 (the adapter contract) exists. The checkpoint
  DATA MODEL + record_checkpoint() ARE in scope so a future adapter just calls them.

Q2 checkpoint (AC-1 core)? → observation_checkpoints: {tenant, system, adapter, watermark_position,
  watermark_timestamp, recorded_at}. Idempotent per (tenant, system, adapter, watermark_position) so
  duplicate window re-reads don't double-record (evf_expiry_notifications idempotency pattern).

Q3 gap lifecycle (AC-2/AC-3)? → when the latest checkpoint for a (system, adapter) is older than the
  configured cadence + tolerance and no gap is open, open an observation_gap with cause UNKNOWN
  (until diagnosed). Cause classes: ADAPTER_FAILURE | SOURCE_UNAVAILABLE | CREDENTIAL_EXPIRY |
  DEPLOY_WINDOW | LAG_EXCEEDED | PLANNED_MAINTENANCE | SARO_OUTAGE | UNKNOWN. A resuming checkpoint
  closes the open gap with duration + watermark delta (positions/timestamps only — never content).
  AC-3 "links into the evidence hash chain": on FINALIZATION (close / created-closed) each gap gets a
  content_hash + prev_hash chaining per tenant (reviewer B1 — added; verify_gap_chain detects tamper).

Q4 zero-PHI (INV-2/INV-3)? → gap + checkpoint records carry positions and timestamps ONLY. No
  observed content, ever. Watermark deltas are expressed as positions/timestamps.

Q5 SARO self-outage (edge)? → detect_saro_outage(): on boot, a checkpoint-discontinuity beyond
  tolerance opens a RETROACTIVE gap with cause SARO_OUTAGE — the system confesses its own downtime.

Q6 planned maintenance (edge)? → declare_maintenance() pre-creates a gap with cause
  PLANNED_MAINTENANCE + approver. Planned gaps are still gaps (counted in coverage).

Q7 lag (AC-5)? → observation_lag_samples: p50/p95/max per window so "maximum observation lag" has
  MEASURED evidence, not an estimate. Recorded periodically.

Q8 report (AC-4)? → coverage_report(system, range): % time under observation, gap list with causes,
  max observation lag observed, methodology note — exportable diligence artifact.

Q9 tenant isolation? → all three tables are tenant-scoped -> RLS (migration 036) + register in the
  TEN-001 schema-completeness guard + docs/TENANT_ISOLATION.md.

## Deviations
- DEV-1 (owner-locked scope): AC-1's live-adapter heartbeat EMISSION is deferred (STORY-406 absent).
  The checkpoint interface + all gap/lag/report logic ships; wiring a real adapter is follow-on.

## Review outcomes (both agents)
- Reviewer VERDICT: REQUEST-CHANGES -> resolved. Security-auditor VERDICT: FAIL -> resolved.
- B1 (reviewer BLOCKER): AC-3 hash-chain linkage was missing AND undisclosed. Fixed: ObservationGap
  gets content_hash + prev_hash (migration ALTER + model), finalized on close/create-closed, chained
  per tenant; verify_gap_chain added. Pinned by test_gap_chain_finalizes_and_detects_tamper.
- SF (security FAIL): CheckpointIn strings unbounded -> PII could be smuggled into watermark_position
  (INV-2 breach). Fixed: max_length=255 + opaque-token pattern. FND-046 (pinned regression).
- SF (reviewer): coverage % double-counted overlapping gaps. Fixed: _merge_intervals union.
  Pinned by test_coverage_union_no_double_count.
- SF (reviewer): max_observation_lag_ms ignored the report window. Fixed: bounded by recorded_at.
- NH: _aware in detect_saro_outage/declare_maintenance; duration_seconds BigInteger; out-of-window
  gaps excluded from the report list.

## Out of scope (this story)
- Alerting/paging on gap-open (notifications family)
- Auto-remediation of adapter failures
- Coverage SLA contract commitments (this produces the measurement that makes an SLA possible)
- Live Bedrock adapter heartbeat wiring (STORY-406 dependency — deferred)
