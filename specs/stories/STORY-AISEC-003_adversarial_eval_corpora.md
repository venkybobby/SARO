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
- **Turns a claim into a number:** replaces "we catch prompt injection" with a
  reported precision/recall SARO can defend to a technical buyer or auditor.
- **Regression insurance:** every future change to the injection detector gets an
  automatic quality signal, preventing silent accuracy drift (ties to the quality
  ratchet discipline).
- **Cheap to maintain:** static fixtures, no runtime model dependency, reruns in CI.
- **Roadmap fuel:** the per-obfuscation breakdown shows exactly where detection is
  weak, directly prioritizing the next detector investment.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
