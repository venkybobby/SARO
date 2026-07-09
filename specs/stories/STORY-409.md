# STORY-409 — Scheduled Incremental Log Poller

**Status:** Specced, **PILOT-GATED — do not build until SummitCare pilot is signed.**
**Depends on:** STORY-408 (cross-account auth), STORY-410 (CLI/orchestration), STORY-406 coverage semantics; related: ObservationGap UNIQUE-constraint FND (fix lands here — see FR-4)
**Delivery rule:** Integrated into the single SARO repo.

## Problem Statement

Everything today is closed-window backfill: an operator points at a window and runs once. Shadow mode at a pilot client means continuous operation — new Bedrock log objects appear in the client bucket on AWS's delivery schedule (minutes of delay, occasionally late), and SARO must ingest them incrementally, exactly-once in effect, surviving restarts, without an operator in the loop. This is the difference between a demo and a running pilot.

## Goals

1. A poller that wakes on an interval, discovers only-new objects since a durable per-stream cursor, ingests them, and advances the cursor atomically.
2. At-least-once delivery with idempotent effect (no duplicate findings/checkpoints on redelivery or crash-retry).
3. Late-arriving objects are not silently skipped.
4. Concurrent-run safety (the residual race the security-auditor flagged gets fixed, not inherited).

## Non-Goals

- No real-time/streaming (S3 event notifications, EventBridge, SQS) — polling only for the pilot; event-driven is P2 and requires client-side setup that complicates onboarding.
- No inline-blocking or mirror-sync modes — mirror-async shadow mode only, per locked trigger taxonomy.
- No autoscaling/multi-worker sharding — one poller per tenant stream is sufficient at pilot scale.

## Functional Requirements

### FR-1: Durable cursor (P0)
Per (tenant, stream) cursor persisted in the database recording the high-water mark of ingested objects.

**AC-1.1:** Cursor advances only after the batch's records are fully persisted (findings + checkpoints + gaps) — crash between ingest and cursor-advance results in re-ingest, never in loss.
**AC-1.2:** Restart resumes from the cursor with zero operator input.
**AC-1.3:** Cursor definition must handle S3 key ordering vs delivery time: Bedrock's hourly key layout means lexicographic key order ≈ event time, but delivery can lag. Cursor = (latest fully-ingested key) plus a configurable lookback re-list window (default: re-list the trailing N hours of prefixes, default N=3) so late deliveries into already-passed hours are caught.

**AC-1.4 (late-arrival test):** Given an object delivered into an hour-prefix older than the cursor but within the lookback window, the next poll ingests it exactly once.

### FR-2: Idempotent ingest (P0)
**AC-2.1:** Re-processing an already-ingested object produces zero new findings, checkpoints, or gaps. Dedupe key decision: object key + record `requestId` (requestId alone is insufficient if a record could legitimately repeat across objects — recon the actual uniqueness guarantees and document the chosen key in the traceability table).
**AC-2.2:** Crash-recovery test: kill the poller mid-batch, restart, assert final state identical to an uninterrupted run.

### FR-3: Poison-object handling (P0)
**AC-3.1:** A malformed/oversized/undecompressible object (STORY-407's caps apply) is quarantined: recorded with key + error, skipped, cursor still advances past it, and it surfaces in poller status output. It does NOT halt the stream, and it does NOT retry forever.
**AC-3.2:** Quarantined objects are visible via `saro poller status` (FR-5) — an examiner asking "did you process everything?" gets an honest answer including what was skipped and why. (This is an observation-gap-adjacent disclosure: consider whether a quarantined object should register as a coverage caveat — flag for owner decision rather than deciding unilaterally; it touches attestation semantics.)

### FR-4: Concurrency safety (P0)
**AC-4.1:** Two poller instances for the same (tenant, stream) cannot interleave: per-stream advisory lock or equivalent; the second exits cleanly with a "already running" status.
**AC-4.2:** Fix the pre-existing residual: add the missing UNIQUE constraint (or equivalent upsert discipline) on `ObservationGap` so concurrent reconciliation cannot create duplicate gap rows. Migration + regression test. (This closes the security-auditor's FND against the coverage module.)

### FR-5: Scheduling & operations (P0)
```
saro poller run --tenant <t> [--interval 15m] [--once]
saro poller status --tenant <t>
```
**AC-5.1:** `--once` performs a single poll cycle and exits (this is also how an external scheduler — cron/Fly machine schedule — can drive it, avoiding a long-lived daemon if that fits the Fly.io deployment better; recon the deployment model and pick, documenting the choice).
**AC-5.2:** `status` reports: cursor position, last successful poll time, objects/records ingested in last cycle, quarantine count, lock state.
**AC-5.3:** Deployment note for Fly.io: if run as a long-lived process, `auto_stop_machines=false` applies (known cold-start loop failure mode).

### FR-6: Metering hook (P1)
**AC-6.1:** Per-cycle counts (objects, records, findings) emit through the PHI-free metering pathway (existing story's conventions) — no bodies, no client content, envelope counts only.

## Verification (all-or-nothing)
- [ ] Crash-recovery and late-arrival tests green (AC-1.4, AC-2.2)
- [ ] Idempotency pinned; dedupe key documented
- [ ] Two-instance concurrency test + ObservationGap UNIQUE migration + regression test
- [ ] 24h soak against a bucket receiving synthetic objects on a drip (builder can generate the drip) — zero duplicates, zero missed objects, quarantine behaves
- [ ] Coverage attestations over the soak window are correct (gaps only where objects were genuinely absent)
- [ ] STORY-336 guard green; INV-2 untouched; full suite passes

## Open Questions
1. Quarantined-object ↔ coverage-attestation semantics (does a skipped object create a disclosed caveat?). Touches examiner-grade claims — owner decision. (Venky)
2. Long-lived daemon vs `--once` under external scheduler on Fly.io. (Recon → Venky)
3. Record-level dedupe key uniqueness guarantees. (Recon)
