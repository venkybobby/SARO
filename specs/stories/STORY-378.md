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
| AC-1 | `test_matrix_is_deterministic_run_to_run`, `test_labeled_corpus_is_deterministic`, `test_harness_makes_no_external_model_call` | `scripts/confusion_matrix_harness.py`, `scripts/build_validation_corpus.py`, `tests/fixtures/validation/t1_labeled.jsonl` |
| AC-2 | `test_matrix_has_per_pack_per_rule_confusion_counts`, `test_current_packs_score_perfectly_on_the_labeled_t1_set` | `quality/validation/confusion-latest.json` (per-pack, per-rule TP/FP/FN/TN + P/R/F1) |
| AC-3 | `test_verdict_is_report_only_while_the_bar_is_unsigned`, `test_check_mode_does_not_fail_the_build_while_unsigned`, `test_harness_would_fail_check_only_against_a_signed_unmet_bar` | `services/validation_bar.py`, `.github/workflows/conformance.yml` |
| AC-4 | `test_trend_line_excludes_the_timestamp_so_stable_rates_do_not_churn` | `quality/validation/trend.jsonl` |

## Report-only until you sign — by construction
The verdict comes from `validation_bar.active_thresholds()`, which returns
`None` unless STORY-377 is signed. While `None`, the harness reports rates and
marks the verdict `report_only`; `--check` exits 0. It **cannot** fail a build
against thresholds SARO set for itself. Signing later flips it to enforcing with
no change here — pinned by `test_harness_would_fail_check_only_against_a_signed_unmet_bar`.

## The harness earned its keep on run #1 — FND-068
Measuring the packs against labeled ground truth immediately surfaced a real
gap: `OBS-REQUIRED-FIELDS-1` tested `is None`, but the adapters emit
`model_id = ""` (availability MISSING) for an unresolved model — so the
completeness rule was **blind to the exact real-world case it exists for**
(recall 0). Logged as FND-068, fixed red-first (`value is None or value == ""`,
0 stays present), recall 0.857 → 1.0. This is the harness doing its job: a
labeled matrix catches a rule regressing because the label disagrees, not
because the label tracks the bug.
