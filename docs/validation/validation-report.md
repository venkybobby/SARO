# SARO Rule-Pack Validation Report

> **Generated** by `scripts/generate_validation_report.py` from the confusion-matrix artifact (STORY-378). Every rate below is measured, not asserted — regenerating this report cannot state a number the harness did not produce.

- **Generated:** 2026-07-22
- **Corpus tier measured:** T1 (synthetic-deterministic)
- **Corpus records:** 11
- **Completion bar:** PROPOSED_AWAITING_SIGNOFF - **not yet signed** (see Limitations)

## What this measures

For each rule-pack, the rate at which its rules fire when they should (recall) and fire only when they should (precision), measured against a labeled corpus. These are **analytical measurements of SARO's own rule behaviour** - they are not a determination about any customer system, and SARO does not issue verdicts.

## Results

| Rule pack | Precision | Recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| RP-OBS-COMPLETE@1.0.0 | 1.0 | 1.0 | 1.0 | 7 | 0 | 0 | 37 |
| RP-TOOL-SCOPE@1.0.0 | 1.0 | 1.0 | 1.0 | 3 | 0 | 0 | 30 |

### Per-rule detail

**RP-OBS-COMPLETE@1.0.0**

| Rule | Precision | Recall | TP | FP | FN | TN |
|---|---|---|---|---|---|---|
| OBS-ERROR-INVOCATION-1 | 1.0 | 1.0 | 2 | 0 | 0 | 9 |
| OBS-REQUIRED-FIELDS-1 | 1.0 | 1.0 | 1 | 0 | 0 | 10 |
| OBS-TOKEN-COUNTS-1 | 1.0 | 1.0 | 2 | 0 | 0 | 9 |
| OBS-TRUNCATED-OUTPUT-1 | 1.0 | 1.0 | 2 | 0 | 0 | 9 |

**RP-TOOL-SCOPE@1.0.0**

| Rule | Precision | Recall | TP | FP | FN | TN |
|---|---|---|---|---|---|---|
| TOOL-POLICY-ABSENT-1 | 1.0 | 1.0 | 1 | 0 | 0 | 10 |
| TOOL-SCOPE-OFFERED-1 | 1.0 | 1.0 | 1 | 0 | 0 | 10 |
| TOOL-SCOPE-VIOLATION-1 | 1.0 | 1.0 | 1 | 0 | 0 | 10 |

## Limitations - read this before relying on the numbers above

Understatement over overstatement. These results are real but narrow:

- **Only tier T1 was measured.** Tiers not yet covered: T2 (synthetic-adversarial), T3 (offline labeled), T4 (pilot labeled). A perfect score on a synthetic tier does not demonstrate behaviour on adversarial or real-world data.
- **The corpus is synthetic.** It is deterministic and labeled by construction, which makes it reproducible - but it is not real customer traffic. Real-world (T3) and pilot (T4) data are how these rates are validated against reality, and that data is not yet in place.
- **2 rule-pack(s)** were measured: RP-OBS-COMPLETE@1.0.0, RP-TOOL-SCOPE@1.0.0. Other packs are not covered by this report.
- **No completion bar is signed yet.** The pass/fail thresholds (STORY-377) are proposed and awaiting owner sign-off. Until then these are *measured rates*, not a pass against an agreed bar - this report describes behaviour, it does not validate it against a target.
- **Adapters not yet validated on real data:** the observation adapters (Azure OpenAI, Vertex AI) are exercised by the conformance suite but their FP/FN rates on real provider logs are not yet measured.

## How these numbers were produced

The rule engine is deterministic and makes no external model calls (INV-1). The labeled corpus is built by `scripts/build_validation_corpus.py` and verified byte-identical in CI, so the confusion matrix is reproducible run to run. This report is regenerated from that artifact; it contains no hand-entered figures.

---

*This is a report of SARO's own rule-pack measurements for a technical reviewer. It carries no regulatory weight, is not a determination under any framework, and includes no customer results. Human review by qualified personnel is required before any regulatory submission.*

