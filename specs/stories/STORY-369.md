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
| AC-1 | `test_slo_document_exists_with_the_required_indicators`, `test_every_sli_names_the_metric_it_is_computed_from`, `test_ingestion_slo_matches_the_alert_threshold_exactly`, `test_slo_explicitly_rejects_a_999_target` | `docs/ops/slo.md` |
| AC-2 | `test_sla_is_marked_draft_and_not_for_external_use`, `test_sla_commits_to_995_not_999`, `test_sla_defines_measurement_method_and_its_granularity`, `test_sla_lists_exclusions_including_upstream_providers`, `test_sla_is_explicit_about_no_service_credits` | `docs/legal/sla-draft-v0.1.md` |
| AC-3 | `test_sla_points_at_the_support_model_rather_than_restating_it`, `test_sla_does_not_restate_response_time_commitments` | SLA §5 — pointer, not a copy |

## Finding raised: FND-064 (open, blocks external SLA use)
The premise check found that `docs/incident-response-plan.md` — **served
customer-facing** via `GET /api/v1/governance/ir-plan` (`sla_hours: 1` for
downtime and breach) — commits to "Automated (<5 min)" detection, 15-minute
acknowledgement, and 1-hour P1 response. Measured reality after STORY-368:
canary every 30 min + two-consecutive-failure rule ⇒ **≤60 min detection**, over
an **email channel that is explicitly not a pager**. Its escalation matrix also
names an on-call engineer and `Slack @oncall` that do not exist, and still lists
Railway (superseded) as a detection trigger.

Deliberately **not** silently rewritten: changing published commitments is an
owner decision and STORY-371 owns the IRP delta. Instead the SLA points at the
IRP rather than restating targets, and **gates its own external use** on the
reconciliation. `test_ir_plan_still_contains_the_unreconciled_claims` fails if
someone edits the claims out without updating the finding and the gate.

## Design notes
- **SLOs are stricter than the SLA** so an objective can breach before a
  commitment does.
- **Measurement honesty:** targets are defined but continuous measurement is
  **not in place** — no TSDB is deployed and `/metrics` counters reset on
  restart. Availability is approximable only at 30-minute probe granularity, and
  the doc states that floor rather than implying second-level accuracy.
- **99.5%, not 99.9%:** single machine, single region, no failover, plus a hard
  Supabase dependency. 99.9% allows 43 min/month — less than one bad deploy plus
  rollback. The refusal and its reason are written down.

## Human gate
SLA is **DRAFT** — requires counsel review before any external use, and is
additionally blocked by FND-064.
