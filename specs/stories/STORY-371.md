# STORY-371: Support Model + Incident Response Plan (delta)

**Status:** ready
**Screen/Area:** Ops/compliance docs (Pack Epic 16)
**Ground truth:** `docs/incident-response-plan.md` v1.0 EXISTS (detection →
containment → notification flows); external-sharing gap #1 was already closed by
S-1202 (per GAP_ANALYSIS_2026-06-15). Delta = support model + severity matrix +
tabletop exercise.

## Goal
A pilot customer knows severity definitions, response paths, and who answers at
2am — honest solo-founder model with named backup plan.

## Acceptance Criteria
- AC-1: Support model doc (`docs/ops/support-model.md`): channels, hours, S1–S4
  severity matrix with response/resolution targets consistent with STORY-369
  SLA, escalation path (honest solo-operator model + backup).
- AC-2: IRP updated to v1.1: link severity matrix, add security-incident
  customer-notification timeline commitments, postmortem template appended.
- AC-3: One tabletop exercise run against "leaked credential" hypothetical
  (FND-003 as the scenario); notes committed under docs/ops/tabletop/.
- AC-4: Gap-tracker linkage refreshed (IRP already closed gap #1 — record stays
  accurate, no re-claiming).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
