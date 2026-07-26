# STORY-AISEC-003: Adversarial prompt-injection eval corpora for saro-data-framework

**Status:** draft
**Screen/Area:** saro-data-framework (offline evaluation) / detector benchmarking

## Source & attribution
Payload *taxonomies* (not tooling) drawn from the Apache-2.0
`mukul975/Anthropic-Cybersecurity-Skills` red-team skills:
`red-teaming-llms-with-garak`, `orchestrating-llm-attacks-with-pyrit`,
`continuous-llm-red-teaming-with-promptfoo`, `testing-for-system-prompt-leakage`,
`testing-prompt-injection-in-rag-pipelines`. We import the **attack categories
and representative payloads** as static offline fixtures — we do NOT run garak /
PyRIT / promptfoo at runtime.

## Premise verification (FM-2 — verified before authoring)
| Referenced artifact | Verified? | File path |
|---|---|---|
| Offline eval framework | yes | `saro-data-framework/` (`src/`, `tests/`, `config.yaml`, `output/`) |
| Existing offline batch jobs | yes | CLAUDE.md — TruthfulQA / PII / toxicity batch jobs |
| Detector under test | dependency | STORY-AISEC-001 (`draft`) — this story benchmarks it |
| Claims boundary | yes | `docs/COMPLIANCE_CLAIMS_MATRIX.md` (SARO-002 sampling methodology) |

## Goal
Build a curated, labeled **offline corpus of injection / jailbreak /
system-prompt-leakage payloads** (positives) plus benign near-misses (negatives),
and a batch job in `saro-data-framework` that measures the STORY-AISEC-001
detector's precision/recall against it. This turns "we detect prompt injection"
from an assertion into a **measured, regenerable benchmark** — and gives every
future detector change a quantitative regression signal.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given the corpus, When loaded, Then each sample carries a label
  (`injection` / `jailbreak` / `leakage` / `benign`) and an obfuscation tag
  (`plain` / `zero-width` / `base64` / `rot13` / `homoglyph`).
- AC-2: Given the batch job, When run offline, Then it emits precision, recall,
  and a per-obfuscation breakdown for the detector, written under
  `saro-data-framework/output/`.
- AC-3: Given a benign near-miss set, When evaluated, Then the false-positive rate
  is reported (guards STORY-AISEC-001 AC-3 against silent regressions).
- AC-4: Given the run, When executed, Then it is fully offline/deterministic — no
  network, no external model calls — consistent with SARO posture.
- AC-5: Given corpus size, When validated, Then each class meets SARO's internal
  ≥50-sample heuristic (SARO-002) so the reported rates are statistically
  meaningful; the corpus README states this is an *internal* methodology, not a
  regulatory threshold.

## Edge Cases
- Payloads that are themselves prompt injections must be stored inert (data, never
  interpolated into any live LLM context — including during corpus generation).
- Duplicate/near-duplicate payloads across upstream skills → dedupe on normalized
  form so metrics are not inflated.

## Out of Scope
- Running garak/PyRIT/promptfoo as live red-team drivers (they need a target
  model; SARO scores static `prompt`+`raw_output`).
- Publishing the corpus externally — internal evaluation asset only.
- Tuning the detector inside this story (that is STORY-AISEC-001); here we measure.

## Non-Functional Requirements
- Deterministic batch; results regenerable and diffable.
- Payloads clearly marked untrusted; no execution path from corpus to a live model.

## Benefits
- **Turns a claim into a measured signal:** replaces "we catch prompt injection"
  with a reported precision/recall over a labeled corpus. The corpus separates
  **targeted** payloads (written to match the detector's rules → a *regression*
  signal) from **held-out** payloads (novel phrasings not derived from the rules
  → a *generalization* probe). The honest internal number is held-out recall;
  neither figure is presented as a certified real-world detection rate.
- **Regression insurance:** every future change to the injection detector gets an
  automatic quality signal, preventing silent accuracy drift (ties to the quality
  ratchet discipline).
- **Cheap to maintain:** static fixtures, no runtime model dependency, reruns in CI.
- **Roadmap fuel:** the per-obfuscation and held-out breakdowns show exactly where
  detection is weak (e.g. homoglyph, paraphrase), prioritizing the next investment.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 (labeled + obfuscation + source tags) | `test_corpus_loads_and_is_labeled` | `saro-data-framework/corpora/injection_eval_corpus.jsonl`, `rule_packs/injection/eval.py` (`load_corpus`) |
| AC-2 (precision/recall + per-obfuscation + by-source) | `test_evaluate_reports_precision_recall_and_per_obfuscation`, `test_targeted_recall_is_high_regression_signal`, `test_held_out_recall_is_reported_as_generalization_probe` | `rule_packs/injection/eval.py` (`evaluate`), `scripts/run_injection_eval.py` |
| AC-3 (benign FP rate reported) | `test_false_positive_rate_is_reported_for_benign_set` | `rule_packs/injection/eval.py` |
| AC-4 (offline, no network/model) | `test_evaluate_makes_no_network_calls`, `test_evaluate_is_deterministic` | `rule_packs/injection/eval.py`, `scripts/run_injection_eval.py` |
| AC-5 (≥50 distinct plain seeds/class, internal heuristic) | `test_floor_is_met_by_distinct_plain_seeds_not_padding`, `test_every_attack_class_has_a_held_out_generalization_subset`, `test_corpus_readme_flags_internal_methodology` | `saro-data-framework/corpora/injection_eval_corpus.jsonl`, `saro-data-framework/corpora/README.md` |

## Result (from `python scripts/run_injection_eval.py`)
n=347 · precision=1.0 · FPR=0.0. Recall by source (the honest split):
**targeted 0.80** (regression signal — payloads written to match the rules) vs
**held-out 0.0** (generalization probe — 0/54 novel phrasings caught; a regex
detector does not generalize). Aggregate recall 0.66. Per-obfuscation recall
(targeted only): plain/zero-width/base64/rot13 ≈0.94, **homoglyph 0.0** — the
NFKC normalizer does not fold Cyrillic homoglyphs. These are **internal quality
signals, not a certified detection rate**. The held-out and homoglyph gaps are
the prioritizable follow-ons (candidate: a semantic/ML detector, and homoglyph
folding in the normalizer).
