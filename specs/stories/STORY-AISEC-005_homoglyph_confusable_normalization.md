# STORY-AISEC-005: Homoglyph / confusable normalization for the injection detector

**Status:** IMPLEMENTED (718e04f)
**Screen/Area:** rule_packs/injection (detector normalize) / TRACE evidence

## Origin
Follow-on prioritized by the STORY-AISEC-003 benchmark, which measured
**homoglyph-obfuscation recall = 0/36 = 0.0** — the injection detector's NFKC
normalization does not fold Cyrillic/Greek Latin-lookalikes, so an attacker who
swaps `a→а e→е o→о c→с p→р` (Cyrillic) evades every rule. This closes that
specific, measured gap. (The separately-measured *held-out* recall 0.0 is NOT in
scope — that is the regex detector failing to generalize to novel phrasings,
which only a semantic/ML detector fixes, and external models are barred from core
scoring by Non-Negotiable #1.)

## Premise verification (FM-2 — verified before authoring)
| Referenced artifact | Verified? | File path |
|---|---|---|
| Injection detector normalize() | yes | `rule_packs/injection/detector.py` (`normalize`, NFKC at the `unicodedata.normalize` line) |
| Homoglyph gap is real | yes | `saro-data-framework/output/injection_eval_batch.json` — `by_obfuscation.homoglyph.recall = 0.0` |
| Eval harness to re-measure | yes | `rule_packs/injection/eval.py`, `scripts/run_injection_eval.py`, `saro-data-framework/corpora/injection_eval_corpus.jsonl` |
| Benign FP corpus | yes | same corpus (`label=benign`, 53 samples) |
| No-external-model posture | yes | CLAUDE.md Non-Negotiable #1 |

## Goal
Fold well-established Unicode **letter** confusables (Cyrillic + Greek
Latin-lookalikes) to their Latin skeleton inside the detector's `normalize()` —
*before* heuristic matching — so homoglyph-obfuscated injection is caught.
Deterministic, no external model, no new dependency (curated confusables map).
Digit/punctuation confusables are deliberately **out of scope** (folding `0→o`,
`1→l` etc. risks corrupting legitimate text/URLs — under-fold rather than
over-fold). Validate the improvement with the STORY-AISEC-003 benchmark.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given an injection directive obfuscated with Cyrillic homoglyphs (e.g.
  `іgnоrе all previous instructions`), When normalized and scanned, Then it is
  detected (folded to the Latin skeleton first).
- AC-2: Given the STORY-AISEC-003 corpus re-evaluated after the change, When the
  benchmark runs, Then `by_obfuscation.homoglyph.recall` rises to ≥ 0.8 (from 0.0),
  and the committed `injection_eval_batch.json` is regenerated to match.
- AC-3: Given the benign corpus (and legitimately non-Latin benign text), When
  scanned, Then the false-positive rate stays 0.0 — confusable folding introduces
  no new false positives.
- AC-4: Given any input, When normalized, Then folding is deterministic and makes
  zero external-model/network calls (a curated in-code confusables map, no new
  dependency) — consistent with SARO posture and the existing normalize() constants.
- AC-5: Given the confusables map, When reviewed, Then it covers at least the
  common Cyrillic and Greek → Latin homoglyph set, with a provenance comment
  (Unicode confusables / TR39 basis) so it is auditable; folding is confined to
  confusable codepoints (mixed-script text keeps its non-confusable characters).

## Edge Cases
- Mixed-script text (some Cyrillic, some Latin) → fold only the confusable
  codepoints, leave the rest.
- Legitimate all-Cyrillic benign text folded to Latin gibberish → must not match
  any injection rule (validated by the benign corpus FP rate).
- Over-folding risk → fold only well-established confusables, never broad
  transliteration; do not fold characters whose Latin skeleton is ambiguous.

## Out of Scope
- Full Unicode TR39 confusables table or a homoglyph *library dependency* — a
  curated subset covering the common attack set is sufficient.
- Held-out / semantic generalization (barred — needs an external model).
- Any change outside the injection detector's `normalize()` (e.g. extending
  normalization to all Gate-3 signals remains a separate deferred story).

## Non-Functional Requirements
- Deterministic, side-effect-free, no network, no new dependency.
- Tests pin every AC in `tests/test_aisec_005_homoglyph_normalization.py`;
  quality ratchet must not regress.
- reviewer + security-auditor approve before merge (rule_packs/ + input-handling).

## Benefits
- **Closes a measured detection gap:** homoglyph recall 0.0 → ≥0.8, turning a
  known evasion (Cyrillic lookalikes) into a caught one — directly actioning the
  AISEC-003 benchmark's finding.
- **Posture-safe:** deterministic confusable folding, no external model, no new
  dependency; the evidence-only, read-only posture is untouched.
- **Self-validating:** the AISEC-003 benchmark re-measures the improvement, so the
  gain is a reported number, not a claim.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 (homoglyph injection detected) | `test_homoglyph_obfuscated_injection_is_detected` | `rule_packs/injection/detector.py` (`_CONFUSABLES`, `normalize`) |
| AC-2 (homoglyph recall 0→≥0.8, report regen) | `test_homoglyph_recall_improved_on_the_corpus`, `test_committed_benchmark_report_reflects_the_improvement` | `rule_packs/injection/detector.py`, `saro-data-framework/output/injection_eval_batch.json` |
| AC-3 (no new false positives) | `test_benign_false_positive_rate_stays_zero`, `test_benign_cyrillic_text_is_not_a_false_positive` | `rule_packs/injection/detector.py`, `saro-data-framework/corpora/injection_eval_corpus.jsonl` |
| AC-4 (deterministic, no network/dep) | `test_scan_makes_no_network_calls` | `rule_packs/injection/detector.py` |
| AC-5 (curated map, folds only confusables) | `test_confusables_map_folds_common_cyrillic_and_greek`, `test_normalize_folds_only_confusables_keeps_other_text` | `rule_packs/injection/detector.py` (`_CONFUSABLES`) |

## Result (from `python scripts/run_injection_eval.py`)
homoglyph by-obfuscation recall **0.0 → 0.9444** (34/36); false-positive rate
stays **0.0** — now measured over a benign set that includes 5 Cyrillic/Greek
sentences (58 benign total), so the FP number genuinely exercises the fold and
confirms no over-folding on non-Latin prose. targeted recall 0.80 → 0.9458;
aggregate recall 0.66 → 0.77. Held-out recall unchanged at 0.0 (out of scope —
needs a semantic detector).
