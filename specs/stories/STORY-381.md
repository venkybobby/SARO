# STORY-381: Privacy-Safe Product Analytics

**Status:** ready
**Screen/Area:** Backend + docs (Pack Epic 19)

## Goal
Roadmap decisions use behavior data: first-party, PHI-free usage analytics on
SARO's own UI/API.

## Acceptance Criteria
- AC-1: Event schema doc FIRST (`docs/analytics/event-schema.md`): event name,
  properties, tenant id — no PHI, no payload content, no free-text capture
  (INV-2 by construction; schema validator enforces property allowlist).
- AC-2: First-party capture: `product_events` table in Supabase (self-hosted
  option; third-party SaaS explicitly NOT chosen without sign-off — Epic 15
  security-review question).
- AC-3: Key funnels instrumented server-side: login → view attestation,
  rule-pack subscribe → first evaluation, Compliance Hub artifact views.
- AC-4: Internal query set for the founder (`docs/analytics/queries.md` +
  `cli.py analytics-summary`).
- AC-5: Analytics disclosed in the DPA/data-retention doc (ties to gating gap #3
  artifacts: docs/sample-evidence-retention.md, DPA template).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
