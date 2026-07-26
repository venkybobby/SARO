# STORY-AISEC-005 — Homoglyph / confusable normalization for the injection detector
Stage: standard

## Lifecycle
- [x] discover   (normalize() structure + homoglyph gap confirmed; area just built in AISEC-001)
- [x] shape      (no architecture-changing ambiguity; one decision self-answered below)
- [x] preview    (skipped — backend-only, no UI surface)
- [x] plan
- [x] build
- [x] verify
- [ ] sell       (n/a)

## DISCOVER findings
- `rule_packs/injection/detector.py` `normalize()` does zero-width strip →
  tag-range drop → NFKC → bounded base64/ROT13. NFKC does NOT fold Cyrillic/Greek
  homoglyphs, so `by_obfuscation.homoglyph.recall = 0.0` in the shipped
  `saro-data-framework/output/injection_eval_batch.json`.
- Existing normalize() constants (`_ZERO_WIDTH`, `_TAG_RANGE`) are in-code →
  a confusables map fits the same pattern.
- The AISEC-003 benchmark (`scripts/run_injection_eval.py`) re-measures the gain.

## Premise check (Stage 3a)
| Referenced artifact | Verified? | File path |
|---|---|---|
| normalize() + NFKC | yes | `rule_packs/injection/detector.py` (`normalize`) |
| homoglyph gap = 0.0 | yes | `saro-data-framework/output/injection_eval_batch.json` (`by_obfuscation.homoglyph`) |
| eval harness | yes | `rule_packs/injection/eval.py`, `scripts/run_injection_eval.py` |
| benign FP corpus | yes | `saro-data-framework/corpora/injection_eval_corpus.jsonl` (label=benign) |

## Decision Log
- Confusables map: in-code constant vs data file? → **in-code constant** (consistent with `_ZERO_WIDTH`/`_TAG_RANGE` in normalize(); provenance comment cites Unicode confusables/TR39 for auditability). Rules pack unchanged → pack hash unchanged.
- Fold scope? → **curated Cyrillic + Greek → Latin LETTER confusables only**, not broad transliteration and NOT digit/punct (folding 0→o/1→l risks corrupting real text/URLs — under-fold, over-folding guard, AC-5).
- Where to fold? → **after NFKC, before matching** in normalize(); folds only confusable codepoints, mixed-script text keeps the rest.

## Plan (tweak-likelihood order)
1. **Confusables map** `_CONFUSABLES` in `detector.py` — curated Cyrillic+Greek→Latin
   (+ common digit/punct) skeleton map, provenance comment. Verify: unit test that
   the map folds known homoglyphs.
2. **Fold step** in `normalize()` — apply `str.translate(_CONFUSABLES)` after NFKC,
   before returning `base` (flows into decode segments too). Verify: AC-1
   (Cyrillic-obfuscated injection detected), edge (mixed-script) unit tests.
3. **Re-measure** — regenerate `injection_eval_batch.json`; homoglyph recall
   0.0 → ≥0.8; benign FP rate stays 0.0. Verify: AC-2/AC-3 tests over the corpus.
4. Tests `tests/test_aisec_005_homoglyph_normalization.py` (AC-1..5, no-network).
   Gates 1-7; reviewer + security-auditor; index → IMPLEMENTED; traceability.

## Compliance guardrails
- Deterministic, no external model/network, no new dependency (AC-4).
- Fold only well-established confusables; benign corpus FP rate pins over-folding (AC-3).

## Review round 1 (reviewer + security-auditor agents)
- **security-auditor: PASS.** Fold is monotonic-toward-matching (48 keys all
  non-Latin ≥U+0400 → Latin skeleton), length-preserving (evidence offsets
  intact), O(n) bounded by max_scan_chars, no dep/network. No new evasion; a
  homoglyph inside base64 now folds+decodes (more detection). No FAIL.
- **reviewer: APPROVE** (4 minor). Addressed:
  1. Benign corpus was 100% ASCII → FP=0.0 didn't exercise the fold. Added 5
     benign Cyrillic/Greek sentences (benign 53→58); FP rate stays 0.0 → now
     genuinely tests over-folding.
  2. Story "punct/digit confusables" overclaim → corrected (code folds letters
     only; digit/punct explicitly out of scope).
  3. Index SPECIFIED + notes boxes → flipped at close (this commit).
  4. Untracked noise → only intended files staged.

## Deviations
- Branch off main (fresh — AISEC pack already merged to main as 0f4ec30). Not
  stacked; this is an independent follow-on.
