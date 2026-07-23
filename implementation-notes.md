# FND-072 — harness --check must detect a stale committed confusion matrix

Stage: trivial

Security-audit follow-up from PR #125. FND-071 correctly made
`confusion_matrix_harness.py --check` read-only, but that removed an
*accidental* freshness gate: the old rewrite of
`quality/validation/confusion-latest.json` in the CI workspace meant the next
conformance.yml step (`generate_validation_report.py --check`) compared the
committed report against CURRENT rule-pack behaviour. Now both sides are
committed files (self-referential), so a rule-pack precision/recall regression
leaves the committed evidence artifact silently stale and no CI step notices.

## Decision Log

| decision | choice | why |
|---|---|---|
| WARN vs exit-nonzero on stale artifact | **exit non-zero** | Evidence-freshness is the whole point of the conformance gate; a WARN in CI logs is FM-3 bait (drafted read as delivered). Task brief prefers non-zero. |
| Where to compare | in-memory diff of fresh `apply_bar(compute_matrix())` vs committed `MATRIX_OUT`, excluding `generated_at` | `generated_at` is the only field legitimately allowed to differ (same exclusion STORY-378's determinism test uses). Zero writes — FND-071's read-only pin stays green. |
| Missing / corrupt committed artifact | also stale → exit 1 | An absent artifact of record is the worst staleness, not a pass. |
| Ordering vs signed-bar failure | signed-bar failure first, staleness second | Bar failure is the root-cause message; staleness of the committed file is a consequence. |

## Steps (= build stage for a trivial finding)

- [x] FND-072 assigned (highest existing: FND-071)
- [x] Root cause (5-whys) + row in quality/findings.md
- [x] Red-first regression test (3 staleness cases red pre-fix, 4/4 green post-fix)
- [x] Minimal fix in scripts/confusion_matrix_harness.py (`stale_reason()` + --check exit-1)
- [x] Manifest entry status pinned
- [x] pytest tests/regression -q → 182 passed; scripts/verify.sh → PASS (pytest, ruff, mypy, security_scan; pip-audit advisory WARN pre-existing)
- [x] CI command sanity: `python scripts/confusion_matrix_harness.py --check` → exit 0, tree untouched

## Constraints pinned by existing tests

- `test_fnd_071_check_mode_is_read_only.py` — --check writes nothing (must stay green)
- `test_story378_confusion_harness.py::test_check_mode_passes_because_t1_meets_the_signed_bar`
  — `main(["--check"]) == 0` against the real committed artifact (currently fresh, so green)
- `test_trend_line_excludes_the_timestamp_so_stable_rates_do_not_churn` — source-slice
  assertion between `trend_line = {` and `with TREND_OUT`; new code stays outside that slice

## Deviations

- Branch stacked on `test/demo-live-e2e-gate` (PR #125, open): FND-071 has not
  merged to main yet and this finding depends on it. Fast-forwarded
  `claude/kind-cannon-1d0423` (zero unique commits) onto the PR head rather
  than duplicating the FND-071 change off main. Previous task's
  implementation-notes.md (PR #125's, already committed there) replaced by
  this task's notes.
