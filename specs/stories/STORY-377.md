# STORY-377: Define the Oracle Completion Bar (FP/FN targets)

**Status:** ready (sign-off human-gated)
**Screen/Area:** Validation docs (Pack Epic 18)
**Ground truth:** No "validation strategy v1.1" or 4-tier labeled corpus exists
(pack assumption corrected — see STORY-PACK-14-19-INDEX). This story CREATES
validation strategy v1.0 with tiers, proposed thresholds, and protocol.

## Goal
"Validated" becomes a number with a method: per-pack FP/FN targets + measurement
protocol, proposed with tradeoffs for explicit human sign-off.

## Acceptance Criteria
- AC-1: For RP-OBS-COMPLETE and RP-TOOL-SCOPE: proposed precision/recall
  thresholds with rationale, per ground-truth tier. Tiers defined in this doc
  (T1 synthetic-deterministic, T2 synthetic-adversarial, T3 offline
  qa_lab-labeled (STORY-338 harness), T4 pilot-labeled — future).
- AC-2: Measurement protocol: corpus composition, tier weighting, exclusion
  rules, re-measurement cadence, re-validation triggers (pack version bump,
  adapter addition).
- AC-3 **[HUMAN — OPEN]**: threshold sign-off. Numbers are PROPOSED in the doc
  with tradeoffs; the bar is not active until signed. Do not self-certify.
- AC-4: Documented as `docs/validation/validation-strategy-v1.0.md`.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
