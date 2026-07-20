# STORY-364: SOC 2 Control Inventory & Gap Assessment (Type I framing delta)

**Status:** ready
**Screen/Area:** Compliance docs (Pack Epic 15)
**Ground truth:** `compliance/soc2/STORY-SOC-02_control-evidence-matrix.md` (TSC →
controls → gaps, evidence pointers) and `docs/soc2-readiness-roadmap-v1.0.md`
already exist for the Type II workstream. This story is a **delta**, not a rebuild.

## Goal
Buyer-questionnaire-ready SOC 2 posture: the existing matrix updated with current
gap→story linkage (this pack's stories), Type I vs Type II framing, and the
language guardrail — linked from compliance-claims.md.

## Acceptance Criteria
- AC-1: SOC-02 matrix updated: every ⛔ Gap row carries a closing story ID from
  this pack where one exists (363, 365, 366, 367, 368, 370, 371, 375).
- AC-2: "SOC 2 Type I in progress" language guardrail section present — never
  "SOC 2 compliant"; mirrors FR-EVF-16 tier discipline.
- AC-3: Linked from docs/compliance-claims.md.

## Out of Scope
- Re-discovering controls (SOC-02 did that); auditor engagement (SOC-01 AC-4 human gate).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
