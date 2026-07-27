# Prompt-injection eval corpus (STORY-AISEC-003)

`injection_eval_corpus.jsonl` is a **labeled, inert, offline** corpus used to
benchmark SARO's prompt-injection detector (`rule_packs/injection`, STORY-AISEC-001).
It turns "we detect prompt injection" into a measured precision/recall number.

## Provenance & safety

Payload *taxonomies* are drawn from the Apache-2.0 community library
`mukul975/Anthropic-Cybersecurity-Skills` (red-team skills: garak / PyRIT /
promptfoo / system-prompt-leakage / RAG-injection). Every payload is stored as
**data only** — it is matched by the detector, never interpreted, executed, or
sent to any model. Regenerate deterministically with:

```
python saro-data-framework/corpora/build_injection_corpus.py
```

## Schema (one JSON object per line)

| field | values |
|---|---|
| `text` | the sample text (an inert payload or benign near-miss) |
| `label` | `injection` · `jailbreak` · `leakage` · `benign` |
| `obfuscation` | `plain` · `zero-width` · `base64` · `rot13` · `homoglyph` |
| `source` | `targeted` · `held-out` · `benign` |

## What the numbers mean (read before quoting them)

Attack payloads come in two provenances, and they measure different things:

- **`targeted`** — phrased to hit the detector's rules. Recall here is a
  **regression** signal: "did a detector change break a known-matchable payload."
  It is high by construction and is **not** a real-world detection rate.
- **`held-out`** — novel phrasings deliberately **not** derived from the rule
  corpus. Recall here is a **generalization** probe — the honest, real-world-ish
  number. For a regex detector it is expected to be **low**; that low number is
  the point (it shows where detection does not generalize and prioritizes work).

The reported precision/recall is an **internal quality signal**, not a certified
or auditor-facing detection rate. Do not present it as compliance evidence.

## Sample-size basis — INTERNAL methodology, not a regulation

Each class carries at least **50 samples**. This is SARO's **internal**
statistical heuristic (see `docs/COMPLIANCE_CLAIMS_MATRIX.md`,
"Sampling Methodology Basis" / SARO-002) so the reported precision/recall are
meaningful — it is **not** a regulatory threshold. Neither EU AI Act Art. 10 nor
NIST MAP 2.3 sets a batch sample size; do not attribute the 50-sample floor to
any framework.

## Running the benchmark

```
python scripts/run_injection_eval.py
```

writes `saro-data-framework/output/injection_eval_batch.json` with precision,
recall, false-positive rate, and a per-obfuscation recall breakdown. Fully
offline and deterministic (no network, no external model).
