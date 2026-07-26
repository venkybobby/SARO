# STORY-AISEC-003 — Adversarial prompt-injection eval corpora + benchmark
Stage: standard

## Lifecycle
- [x] discover   (saro-data-framework structure + cross-package testability mapped)
- [x] shape      (placement decision technically-determined by gate/test infra; logged)
- [x] preview    (skipped — backend/offline, no UI surface)
- [ ] plan
- [ ] build
- [ ] verify
- [ ] sell       (n/a)

## DISCOVER findings
- `saro-data-framework/` is a SEPARATE package (own pyproject, MIT, deps:
  datasets/huggingface-hub). Two package trees: `saro_data` (live) +
  `saro_data_framework` (legacy). Converts HF datasets → SARO batch JSON in
  `output/`. Schema `SampleOut(output, ground_truth 0/1, extra)`.
- **Gate reality (load-bearing):** the /story gates run `pytest tests/` and the
  ratchet covers the MAIN package only — `saro-data-framework/tests/` is NOT run
  by the gates, and bandit even excludes `./saro-data-framework`. So AC-pinning
  tests + the testable eval logic MUST live in the main repo to be gate-verified.
- The injection detector (`rule_packs.injection.detector`) is in the main
  package — importable from main-repo tests/scripts, not from the separate
  saro-data-framework package without sys.path hacks.

## Premise check (Stage 3a)
| Referenced artifact | Verified? | File path |
|---|---|---|
| Offline eval framework | yes | `saro-data-framework/` (`src/`, `output/`, `config.yaml`) |
| Detector under test (AISEC-001) | yes (IMPLEMENTED) | `rule_packs/injection/detector.py`, `.../1.0.0/pack.yaml` |
| ≥50-sample heuristic (SARO-002) | yes | `docs/COMPLIANCE_CLAIMS_MATRIX.md` (Sampling Methodology Basis) |
| Upstream payload taxonomies | yes | cloned red-team skills (garak/pyrit/promptfoo/system-prompt-leakage/rag) |

## Decision Log
Self-answered — technically determined by test infra; momentum per user "continue".

- Where does testable eval logic live? → main package `rule_packs/injection/eval.py` (gates cover `tests/` + main pkg only)
- Where do corpus + metrics live? → `saro-data-framework/` (corpora/ + output/), honoring the story's offline-asset intent
- Corpus schema? → purpose-built JSONL (text/label/obfuscation), not `SampleOut(ground_truth)`
- Corpus size? → ≥50 per class (SARO-002 internal heuristic, not a regulation)

| Question | Answer | Consequence |
|---|---|---|
| Where does the testable eval logic live? | **Main package** `rule_packs/injection/eval.py` | Gates (`pytest tests/`) + ratchet cover it. Deviation from spec's "batch job in saro-data-framework" area — forced by test infra. |
| Where do corpus + metrics live? | **saro-data-framework/** | Corpus `saro-data-framework/corpora/injection_eval_corpus.jsonl`; metrics `saro-data-framework/output/injection_eval_batch.json`. Honors the story's offline-asset intent. |
| Corpus schema? | **Purpose-built JSONL** (`text`, `label`, `obfuscation`) | Clearer than shoehorning into `SampleOut(ground_truth)`; the eval needs 4-way label + obfuscation tag, not a 0/1 fairness schema. |
| Corpus size? | **≥50 per class** (injection/jailbreak/leakage/benign) | AC-5 / SARO-002 internal heuristic; ≥200 inert payloads total, README states it's internal methodology not a regulatory threshold. |

## Plan (tweak-likelihood order)
1. **Corpus data** `saro-data-framework/corpora/injection_eval_corpus.jsonl` +
   README — ≥50/class labeled inert payloads across obfuscation tags (plain/
   zero-width/base64/rot13/homoglyph). Verify: corpus-shape + size unit tests.
2. **Evaluator** `rule_packs/injection/eval.py` — `load_corpus(path)`,
   `evaluate(corpus, pack) -> Metrics` (precision/recall/FP-rate/per-obfuscation).
   Pure, offline. Verify: AC-2/AC-3 unit tests.
3. **Batch runner** `scripts/run_injection_eval.py` — loads corpus + pack, runs
   evaluate, writes `saro-data-framework/output/injection_eval_batch.json`.
   Deterministic. Verify: runner smoke test (AC-2 output file).
4. **Tests** `tests/test_aisec_003_injection_eval.py` (AC-1..5, no-network fixture).
5. Gates 1-7; reviewer (+ security-auditor — touches rule_packs/); index →
   IMPLEMENTED; traceability. Trusted refactoring: none.

## Compliance guardrails
- Payloads stored INERT (data only; never interpolated into a live LLM context,
  including during any generation). No-network fixture asserts AC-4.
- ≥50/class is an INTERNAL SARO methodology heuristic (SARO-002), not a
  regulatory threshold — stated in the corpus README.

## Review round 1 (reviewer + security-auditor agents)
- **security-auditor: PASS.** Payloads confirmed inert (string-matched only, no
  eval/exec/subprocess/network); synthetic-only (RFC-2606 example domains, no
  real secrets); json.loads parsing; local-only output. No FAIL.
- **reviewer: REQUEST-CHANGES → all addressed (substantive rework):**
  1. [MAJOR] Gamed metric (positives reverse-engineered from the detector) →
     added a **held-out** subset of novel phrasings NOT derived from pack.yaml;
     metrics now split `by_source` (targeted=regression, held-out=generalization).
     Honest numbers: overall recall 0.85→0.66; targeted 0.80, **held-out 0.0**
     (regex detector doesn't generalize — the real signal). README + emitted
     JSON + story Benefits reworded: internal quality signal, NOT a certified
     detection rate.
  2. [MAJOR] Padded ≥50 floor → floor now met by ≥50 DISTINCT plain seeds/class
     (50/50/50/53); encoding variants no longer counted toward it; benign
     suffix-duplication removed. New test counts distinct plain seeds.
  3. [MINOR] Non-deterministic `generated_at` in committed report → removed
     (report now diffs cleanly; provenance = pack hash + corpus).
  4. [MINOR] Working-tree hygiene → only intended files staged; cruft excluded.

## Review round 2 (reviewer re-review of the rework)
- **reviewer: conditional APPROVE.** Verified both MAJOR reworks hold (held-out
  seeds genuinely avoid the regexes; held-out recall 0/54=0.0; floor = distinct
  plain seeds 50/50/50/53; deterministic report). Flagged 3 doc-only FM-4 items
  (I'd updated traceability/Result before the rename+rework):
  1. Traceability cited two renamed tests → updated to the shipped names
     (verified all 10 cited names exist).
  2. Result block stale (n=229/recall=0.85) → refreshed to n=347, targeted 0.80
     / held-out 0.0 / aggregate 0.66, labeled as internal signals.
  3. eval.py "apples-to-apples" comment overstated → reworded (plain spans all
     targeted-plain; encodings are the fixed 12-seed subset → indicative).
  Reviewer's stated condition ("once Traceability and Result are corrected … this
  is an APPROVE") is now satisfied and verified; fixes are doc/comment-only, no
  metric or report change.

## Deviations
- Eval logic in `rule_packs/injection/eval.py` (main package), not inside
  saro-data-framework: forced by the gate/ratchet only covering `tests/` + the
  main package. Corpus + metrics output still live under saro-data-framework/.
- Branch stacked on story/STORY-AISEC-002 (needs AISEC-001's detector; 002 is the
  current tip). CI billing-blocked so predecessors unmerged.
