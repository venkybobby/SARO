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

### AC → tests → files
| AC | Tests | Implementation |
|---|---|---|
| AC-1 checkpoint interface (heartbeat/watermark) | `test_checkpoint_idempotent_and_gap_opens_when_stale`, `test_api_checkpoint_and_report` | `record_checkpoint`; `migrations/036`; `ObservationCheckpoint`. **Live-adapter emission DEFERRED (STORY-406).** |
| AC-2 gap opens (cause UNKNOWN); diagnose | `test_checkpoint_idempotent...`, `test_diagnose_gap_sets_cause` | `detect_gaps`, `diagnose_gap` |
| AC-3 resume closes gap w/ duration + watermark delta | `test_resuming_checkpoint_closes_gap` | `record_checkpoint` → `_close_gap` |
| AC-4 coverage report (%, gaps, max lag, methodology) | `test_coverage_report_percentage`, `test_api_checkpoint_and_report` | `coverage_report`; `GET /observation-coverage/report` |
| AC-5 lag p50/p95/max measured | `test_lag_percentiles` | `record_lag_sample` |
| Edge SARO_OUTAGE / maintenance / idempotent re-read | `test_saro_outage_is_retroactive`, `test_planned_maintenance_has_approver` | `detect_saro_outage`, `declare_maintenance` |
| Tenant tables registered | TEN-001 guard | migration 036 RLS + `docs/TENANT_ISOLATION.md` |

**Deferred (owner-locked):** AC-1's live Bedrock-adapter heartbeat emission — STORY-406 (adapter
contract) does not exist. The checkpoint interface ships; wiring a real adapter is follow-on.
