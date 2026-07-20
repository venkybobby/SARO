# STORY-369: SLO Definitions + SLA Statement

**Status:** ready
**Screen/Area:** Ops/legal docs (Pack Epic 16)
**Depends on:** STORY-368 (measurement source), STORY-371 (support model reference)

## Goal
A written, honest SLA backed by measurable SLOs — real numbers for procurement,
no 99.9 promises single-region Fly can't back.

## Acceptance Criteria
- AC-1: Internal SLOs defined (`docs/ops/slo.md`): availability %, evaluation
  latency p50/p95, ingestion freshness — each tied to its STORY-368 metric.
- AC-2: External SLA draft (`docs/legal/sla-draft-v0.1.md`) at a defensible tier
  (99.5% single-region posture stated honestly + upgrade path), maintenance
  windows, measurement + exclusions.
- AC-3: References the STORY-371 support model severity/response table.

## Non-Functional Requirements
- Marked DRAFT — a contract artifact; counsel/owner review before external use.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
