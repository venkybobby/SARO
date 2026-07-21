# STORY-368: Platform Monitoring & Alerting

**Status:** ready
**Screen/Area:** Backend + CI + ops docs (Pack Epic 16)
**Ground truth:** `GET /health` exists (release gate). No /metrics, no canary,
no alert runbooks.

## Goal
The operator knows about degradation before the pilot customer does: metrics
endpoint, documented alert thresholds, a scheduled synthetic canary, and a
runbook per alert.

## Acceptance Criteria
- AC-1: `GET /metrics` (Prometheus text format) covering request counts/latency
  histogram/error rate + evaluation queue depth + ingestion staleness gauges;
  unauthenticated-safe (no tenant data, counts only — INV-2/INV-3 note).
- AC-2: Alert rules doc with thresholds + justification (`docs/ops/alerts.md`),
  incl. mirror-async ingestion lag > 30 min (2× the demo pull cadence).
- AC-3 **[HUMAN — channel choice]**: delivery channel documented; default =
  GitHub Actions failure → email (already watched); Slack/Pushover optional.
- AC-4: Synthetic canary: scheduled GitHub Actions job runs one known-good
  evaluation end-to-end against prod `/health` + demo evaluate path, fails loud.
- AC-5: Runbook per alert: symptom → likely cause → first action (`docs/ops/runbooks.md`).

## Out of Scope
- Third-party uptime SaaS signup (human; doc lists options).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_metrics_route_is_registered`, `test_metrics_requires_a_token`, `test_metrics_is_closed_when_no_token_is_configured`, `test_exposition_is_valid_prometheus_text`, `test_health_endpoint_still_serves_the_documented_contract` | `services/metrics.py`, `routers/metrics_endpoint.py`, `main.py` |
| AC-2 | `test_alert_doc_defines_thresholds_with_numbers`, `test_every_threshold_carries_a_justification`, `test_alert_doc_states_the_counter_reset_caveat` | `docs/ops/alerts.md` |
| AC-3 | `test_delivery_channel_is_documented_with_its_limitation` | `docs/ops/alerts.md` §3 — **[HUMAN — OPEN]** confirm destination address / paging tier |
| AC-4 | `test_canary_workflow_exists_and_is_scheduled`, `test_canary_checks_health_lag_and_an_evaluation`, `test_canary_reports_when_the_evaluation_is_skipped`, `test_canary_script_asserts_contract_not_an_exact_score` | `.github/workflows/canary.yml`, `scripts/canary_evaluation.py` |
| AC-5 | `test_runbook_exists_for_every_alert`, `test_each_runbook_gives_a_first_command_and_causes`, `test_runbooks_preserve_evidence_integrity_priority` | `docs/ops/runbooks.md` |

## Design notes
- **`/metrics` fails closed.** Bearer token from `METRICS_TOKEN`; unset means no
  valid credential exists, so every request 401s. "Open when unconfigured" is
  the CORS anti-pattern already flagged in `main.py`.
- **No tenant labels, ever (INV-3).** A scrape endpoint with `tenant_id` labels
  discloses the customer list and per-customer volumes to anyone who can reach
  it. Metrics are global aggregates; per-tenant volume is metering (STORY-374),
  behind authorization. Pinned by test on metric lines.
- **No path labels.** Raw paths carry ids (`/api/v1/traces/{uuid}`) — cardinality
  explosion *and* customer-identifying values in a scrape.
- **Dependency-free exposition.** `prometheus_client` is not a declared SARO
  dependency (rate_limiter imports it optionally), so the scrape path does not
  depend on an optional import.
- **Ingestion lag `-1` = unknown**, distinct from zero. A tenant that has never
  ingested is a provisioning state, not a stall — encoded in the metric, the
  alert rule, the canary, and the runbook.
- **Canary asserts the contract, not a score.** Pinning an exact risk score
  would make every legitimate scoring change look like an outage.

## Human gate
**AC-3 [HUMAN — OPEN]:** channel is GitHub Actions failure → operator email
(chosen: already watched daily, no new vendor, no new secret). Its weakness is
stated plainly — *email is not a pager*, so overnight detection is best-effort
and STORY-369's SLA must not promise faster response than this supports.
Confirm the destination address and whether a paging tier is needed before the
SummitCare pilot converts.
