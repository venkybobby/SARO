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
