# STORY-AISEC-001: Deterministic prompt-injection normalization + detection rule-pack

**Status:** draft
**Screen/Area:** Scoring engine / rule_packs (observation family) / TRACE evidence

## Source & attribution
Derived from the Apache-2.0 community library
`mukul975/Anthropic-Cybersecurity-Skills`, skill
`detecting-indirect-prompt-injection` (`scripts/agent.py`). We port **semantics,
not code verbatim** (lifecycle Port sub-protocol): the normalization pipeline and
the heuristic regex corpus. Preserve the upstream Apache-2.0 attribution in a
`NOTICE`/header where code is adapted.

## Premise verification (FM-2 — verified before authoring)
| Referenced artifact | Verified? | File path |
|---|---|---|
| Observation rule-pack family | yes | `rule_packs/observation/rp_obs_complete/`, `rp_tool_scope/` |
| Rule-pack evaluator | yes | `rule_packs/observation/evaluate.py` (`evaluate_records`) |
| Pack loader | yes | `rule_packs/observation/loader.py` |
| Finding → framework stamping in engine | yes | `engine.py:303+` (`nist_subcategory_id` on AuditTrace detail_json) |
| Core-scoring inputs (`prompt` + `raw_output`) | yes | CLAUDE.md Non-Negotiable #1; `schemas.py` scan request |
| Upstream heuristics/normalization | yes | cloned skill `detecting-indirect-prompt-injection/scripts/agent.py` (`normalize`, `HEURISTICS`) |

## Goal
Give SARO's core scoring a **deterministic, no-external-model** detector that
catches prompt-injection and system-prompt-leakage attempts hidden by obfuscation
— zero-width characters, Unicode homoglyphs, base64/ROT13 encoding, invisible
HTML/markup text — by normalizing `prompt` + `raw_output` before matching against
a curated heuristic corpus, and emitting evidence-shaped findings on the TRACE
timeline. This closes the current gap where a plain-regex gate is trivially
evaded by splitting or encoding the payload.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given an input containing `"ignore previous instructions"` split by
  zero-width spaces, When it is scored, Then the normalizer collapses it and the
  detector fires an injection finding (a raw-regex-only baseline does not).
- AC-2: Given a base64- or ROT13-encoded injection directive in `raw_output`,
  When scored, Then the decoded payload is scanned and flagged, with the decoded
  form recorded in the finding evidence (never re-executed).
- AC-3: Given benign text that merely mentions "instructions", When scored, Then
  no finding fires (guards against false positives; pinned by fixtures).
- AC-4: Given any input, When scored, Then the detector makes **zero external
  model/network calls** (asserted by a no-network fixture) — it is pure Python.
- AC-5: Given a fired finding, When the TRACE is exported, Then the language is
  evidence-shaped per COMPLIANCE_CLAIMS_MATRIX ("indicators consistent with…",
  "human review required") — never a verdict ("malicious", "blocked").
- AC-6: Given the new pack, When `rule_packs` provenance is queried, Then the
  pack carries a version + SHA-256 hash like the existing observation packs.

## Edge Cases
- Mixed/nested encodings (base64-of-ROT13); cap decode depth to avoid a decode bomb.
- Very large `raw_output` — normalization must be O(n) and bounded (size ceiling).
- Legitimate base64 (e.g., an image data URI) must not auto-flag on decode alone;
  a decoded payload only scores if it *also* matches a heuristic.
- Non-UTF-8 / malformed bytes — normalize defensively, never raise.

## Out of Scope
- **Any ML/transformer detector** (Llama Guard, Prompt Guard 2, deberta). Those
  require running an external model and are barred from core scoring by
  Non-Negotiable #1. If ever added, they belong ONLY to the disclosed,
  off-by-default Gate-3 LLM-judge path (SARO-102), never to core scoring.
- Blocking/remediating the caller's traffic — SARO is read-only, evidence-only.
- Multimodal (image OCR) extraction — a later story if warranted.

## Non-Functional Requirements
- Deterministic and side-effect-free; no network; no writes to client systems.
- Tests pin every AC (red→green) in `tests/test_aisec_001_injection_detector.py`
  (feature-story tests live in `tests/` per SARO convention; `tests/regression/`
  is reserved for FND bug-fix pins — this is a new feature, not a bug fix).
  Quality ratchet must not regress.
- reviewer + security-auditor agents approve before merge (input-handling code).

## Benefits
- **Security:** materially raises the evasion cost for the single most common
  LLM attack class (OWASP LLM01) — normalization defeats the split/encode
  bypasses that a flat regex gate misses today.
- **Posture-safe differentiation:** delivers "prompt-injection evidence" without
  breaking SARO's "never calls external models in core scoring" promise — a claim
  most competitors that wrap a guard-model cannot make.
- **Cheap & fast:** pure-Python, no GPU, no per-call inference cost; runs inline
  in the existing gate with negligible latency.
- **Evidence value:** produces auditor-ready TRACE findings mapped to a
  recognized attack technique (see STORY-AISEC-002), strengthening the evidence
  package without new compliance claims.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 (obfuscation normalized+detected) | `test_zero_width_obfuscation_is_normalized_then_detected` | `rule_packs/injection/detector.py` (`normalize`, `scan`) |
| AC-2 (base64/ROT13 decoded, recorded) | `test_base64_encoded_injection_is_decoded_detected_and_recorded`, `test_rot13_encoded_injection_is_decoded_and_detected` | `rule_packs/injection/detector.py` (`_decode_segments`) |
| AC-3 (benign no false-positive) | `test_benign_instructions_mention_does_not_fire`, `test_legitimate_base64_blob_is_not_a_false_positive` | `rule_packs/injection/detector.py`, `rule_packs/injection/1.0.0/pack.yaml` |
| AC-4 (zero external/network) | `test_scan_makes_no_network_calls` | `rule_packs/injection/detector.py` |
| AC-5 (evidence-shaped TRACE) | `test_run_output_audit_emits_evidence_only_injection_trace`, `test_rule_titles_use_evidence_language_not_verdicts` | `engine.py` (`_scan_injection`) |
| AC-6 (versioned + SHA-256 pack) | `test_pack_has_version_and_sha256_hash`, `test_pack_hash_is_deterministic` | `rule_packs/injection/detector.py` (`load_injection_pack`, `_pack_hash`) |
| (evidence-only, no score impact) | `test_injection_scan_does_not_change_risk_flags` | `engine.py` (`_scan_injection`) |
| (ATLAS mapping for AISEC-002) | `test_findings_carry_atlas_technique_ids` | `rule_packs/injection/1.0.0/pack.yaml` |
