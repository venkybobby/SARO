# STORY-MTR-001 — PHI-Free Usage Metering

Epic: Commercial Foundations (new) | Priority: P1 — pricing has no basis without it
Origin: Gap #5 — no consumption tracking exists; billing model, pricing
enforcement, and renewal value-narrative all depend on metering.

## User Story
As the SARO founder, I need per-tenant usage metering that is PHI-free by
construction, so that pricing can be enforced, invoices substantiated, and
renewal conversations grounded in delivered value.

## Meter Set (v1)
Per tenant, per calendar period, per vertical where applicable:
- evaluations_executed (by gate, by outcome pass/fail)
- attestations_issued
- evidence_records_persisted
- coverage_report_generations / criteria_reproductions (RPV-002 API)
- active_observed_systems (high-water mark per period)
- adapter_observation_volume (count of observed outputs — COUNT ONLY, never content)

## Acceptance Criteria

AC-1
Given any metered event, When the counter increments, Then the meter record
contains only: tenant id, meter key, period bucket, count, and dimensional
tags from a CLOSED vocabulary (gate id, vertical, adapter id, outcome) — no
free-text fields, making PHI leakage structurally impossible (INV-2 by
construction, not by redaction).

AC-2
Given the evaluation path (stateless core, INV-4), When metering is added,
Then increments are emitted asynchronously post-evaluation (same posture as
DISP-001 writes) and metering failure NEVER fails or delays an evaluation —
lost increments are acceptable; blocked evaluations are not. Loss is bounded
and measured (AC-5).

AC-3
Given a billing period closes, When the usage statement is generated, Then it
produces a per-tenant artifact: meter totals, period, generation timestamp,
and a content hash — usage statements are evidence too (disputes are audits).

AC-4
Given plan limits exist (tenant_risk_configs or successor), When usage
approaches/exceeds configured thresholds, Then threshold-crossing events are
recorded and a notification is emitted; v1 records and notifies — it does NOT
enforce cutoffs (commercial decision deferred; never silently drop
evaluations for a healthcare tenant).

AC-5
Given async emission (AC-2), When reconciliation runs (daily), Then meter
totals are cross-checked against authoritative row counts (evidence records,
attestations) and drift beyond 0.5% raises a data-quality finding.

## Edge Cases
- Clock/period boundaries: bucket by UTC period at emission time; document for
  invoicing (tenant-local display is presentation-layer)
- Retried evaluations: idempotency key per evaluation invocation so retries
  don't double-count (evf_expiry_notifications pattern)
- Multi-tenant shared rule-pack reads: not metered (cost of goods, not usage)
- Backfilled/historical periods: immutable once statement issued; corrections
  are new adjustment records, never edits

## Out of Scope
- Pricing model itself (list price, tiers) — commercial workstream
- Payment/invoicing integration (Stripe et al.)
- Customer-facing usage dashboard (follow-on; statement artifact first)

## NFRs
- Metering adds zero synchronous latency to evaluation path
- Meter queries for a tenant-period resolve < 500ms

## Traceability
| Item | Reference |
|---|---|
| PHI-free by construction | INV-2; closed-vocabulary design |
| Async posture | STORY-DISP-001 AC (post-evidence-persist pattern) |
| Idempotency | evf_expiry_notifications |
| Statements as evidence | Hash discipline (SEC Proof lineage) |
| Deal condition | Hale exercise: pricing/packaging conditions |
