# STORY-COV-001 — Observation-Gap (Coverage) Attestations

Epic: Attestation Core | Priority: P1 — differentiator; converts mirror-async's
weakness into evidence
Origin: Gap #4 — mirror-async means SARO is sometimes blind (adapter outage,
lag spike, deploy window); today that blindness is silent, which an examiner
reads as either dishonesty or ignorance.

## User Story
As an AI Auditor, I need SARO to attest to when it was NOT observing — with
cause and bounds — so that coverage claims are provable and gaps are disclosed
rather than discovered.

## Concept
Continuity attestation: for each observed system/adapter, SARO maintains an
evidence-grade timeline of observation coverage. Gaps become first-class
evidence records: {system, adapter, gap_start, gap_end (or ongoing), detected
cause class, detection method}. De-identified by construction (INV-2 — gap
records contain zero payload content).

## Acceptance Criteria

AC-1
Given a registered observation source (e.g., Bedrock log-pull adapter,
STORY-406), When the adapter runs, Then it emits heartbeat/watermark markers
(last-successfully-observed position + timestamp) persisted as coverage
checkpoints — additive to the adapter contract, coordinated with STORY-406
interface freeze (swarm Lane A/B dependency).

AC-2
Given checkpoints stop advancing beyond a configured threshold (per-adapter
expected cadence + tolerance), When the coverage monitor evaluates, Then an
observation-gap record opens in evidence storage with cause class UNKNOWN
until diagnosed; cause classes: ADAPTER_FAILURE, SOURCE_UNAVAILABLE,
CREDENTIAL_EXPIRY, DEPLOY_WINDOW, LAG_EXCEEDED, PLANNED_MAINTENANCE, UNKNOWN.

AC-3
Given a gap closes (checkpoints resume), When the record finalizes, Then it
captures gap duration, watermark delta (what range of source activity was
missed, expressed as positions/timestamps — never content), and links into the
evidence hash chain like any attestation.

AC-4
Given a coverage report request for a system and time range, When generated,
Then it states: % time under observation, gap list with causes, max
observation lag observed (the mirror-async disclosure the wargamer CISO
persona demands), and methodology note — exportable as a diligence artifact.

AC-5
Given mirror-async steady state, When lag is within configured bounds, Then
lag itself is periodically recorded (p50/p95/max per window) so "maximum
observation lag" has measured evidence, not an estimate.

## Edge Cases
- SARO itself down (can't self-observe): on restart, the boot sequence detects
  checkpoint discontinuity and opens a retroactive gap record with cause class
  SARO_OUTAGE — the system must confess its own downtime
- Clock skew between source and SARO: watermark deltas use source-side
  positions where available; document skew tolerance
- Planned maintenance: pre-declared windows create gap records with
  PLANNED_MAINTENANCE cause and approver — planned gaps are still gaps
- Adapter restarts with duplicate window re-reads: coverage must not
  double-count; idempotent checkpoint semantics (evf_expiry_notifications
  idempotency-key pattern)

## Out of Scope
- Alerting/paging on gap-open (notifications story family)
- Auto-remediation of adapter failures
- Coverage SLA commitments in contracts (commercial decision; this story
  produces the measurement that makes an SLA possible)

## NFRs
- Checkpoint writes add < 1% overhead to adapter throughput
- Gap detection latency < 2× the adapter's expected cadence

## Traceability
| Item | Reference |
|---|---|
| Adapter contract | STORY-406 (Bedrock log-pull); pluggable adapter architecture |
| Zero-PHI gap records | INV-2 / INV-3 (positions and timestamps only) |
| Idempotency pattern | evf_expiry_notifications |
| CISO objection | design-partner-wargamer: "what is your maximum observation lag?" |
| Philosophy fit | Interagency guidance: evidence as byproduct; honest-gaps requirement (EVF-002 AC-5) |
