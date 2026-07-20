# STORY-378: Confusion-Matrix Harness in CI

**Status:** ready
**Screen/Area:** Backend/CI (Pack Epic 18)
**Depends on:** PREREQ-RP packs, STORY-377 tiers, labeled corpora (359/360 + Bedrock)

## Goal
FP/FN rates continuously measured: a deterministic harness evaluates each
published observation rule-pack against the labeled corpus and emits a confusion
matrix per pack per tier.

## Acceptance Criteria
- AC-1: Harness deterministic + reproducible run-to-run; rule engine only, zero
  model calls (INV-1).
- AC-2: Per-pack, per-tier confusion matrix + precision/recall/F1 as a versioned
  JSON artifact (`quality/validation/confusion-latest.json`).
- AC-3: Gate: rule-pack publish (STORY-376 lifecycle) requires meeting the
  STORY-377 bar or an explicit documented waiver — until human sign-off of the
  bar, the gate runs in report-only mode (never silently enforcing unsigned
  thresholds).
- AC-4: Trend file appended per run (`quality/validation/trend.jsonl`) so
  regressions are diffable.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
