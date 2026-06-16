# STORY-310 — Risk scoring & disposition

**Epic:** GRC-3 — Output Audit Engine
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-308, STORY-331

## Context
Every finding needs an unambiguous severity and outcome. Score = likelihood × impact, mapped to a
band; then exactly one disposition.

## Framework mapping
- NIST AI RMF: MEASURE.
- ISO/IEC 42001: risk treatment.

## Scope (in)
- Scoring: `score = likelihood(1–5) × impact(1–5)`; band from config thresholds (default LOW 1–6, MODERATE 7–12, HIGH 13–19, CRITICAL 20–25).
- Disposition assignment ∈ {PASS, CONDITIONAL, FAIL, EVIDENCE_GAP, OUT_OF_SCOPE}.
- CONDITIONAL/FAIL must carry a non-empty remediation.

## Out of scope
- Gate aggregation across findings (STORY-326). Escalation routing (STORY-313, Phase 2).

## Acceptance criteria (binary)
- [ ] Score computed correctly; band assigned from config thresholds (not hard-coded).
- [ ] Exactly one disposition per finding.
- [ ] CONDITIONAL or FAIL without a remediation is rejected.
- [ ] Band boundaries are covered by tests (6/7 and 19/20 edges).

## Technical notes
- Band thresholds read from config (STORY-331); for MVP a config constant is acceptable with a TODO.
- Disposition enum values must match the JSON contract exactly (use the shared enum).

## Test requirements
- [ ] Unit: scoring math + band-edge cases.
- [ ] Unit: missing-remediation rejection for CONDITIONAL/FAIL.

## Definition of done
Scoring and banding correct at edges; disposition rules enforced; tests green.
