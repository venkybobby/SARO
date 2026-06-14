# STORY-101: Gate 3 LLM-judge receives matched-signal label instead of sample text

**Status:** ready
**Screen/Area:** engine.py — Gate 3 Risk Classification (SPEC-E1 LLM-as-judge hybrid pass)

## Goal
When the optional Gate-3 hybrid verification pass runs (only when `ANTHROPIC_API_KEY` is set), the LLM judge must reason over the **actual flagged sample text**, not the meta-label of the rule that matched. Today it is handed `flag.signal` (e.g. `"keyword:ssn"` or `"pattern:[0-9]{3}-..."`), so the judge can never meaningfully confirm or reject a flag, defeating the entire false-positive-reduction purpose of the pass.

## Context (file:line)
- `engine.py:1361` — `verdict = self._gate3_llm_verify_sync(_client, flag.signal, flag.domain)` passes `flag.signal` into a param named `sample_text`.
- `engine.py:1445-1456` — `_gate3_llm_verify_sync(self, client, sample_text, domain)` builds the prompt `"Sample text: {truncated}\n\n..."` — expects real text.
- `engine.py` `_SampleFlag` dataclass (≈502-507) — fields `sample_id, domain, signal, weight`; **no field carries the matched sample text**.
- `engine.py:1336-1342` — `self._sample_findings` already stores `{sample_id, domain, matched_signal, matched_text_fragment, weight}` (PII-redacted fragment) — a source for the real text.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given a batch where a sample is flagged for a domain and `ANTHROPIC_API_KEY` is set, When Gate 3's hybrid pass verifies that flag, Then `_gate3_llm_verify_sync` receives the flagged **sample's text** (the redacted `matched_text_fragment` or the originating `sample.text`), not the `flag.signal` label.
- **AC-2:** Given the judge confirms a flag (confirmed=true, confidence ≥ `LLM_CONFIDENCE_THRESHOLD`), When the pass completes, Then that flag is retained; given the judge rejects it, Then it is dropped — identical control flow to today (`engine.py:1374-1377`), only the input is corrected.
- **AC-3:** Given `ANTHROPIC_API_KEY` is **unset** (keyword-only mode), When Gate 3 runs, Then behavior, scoring, and `gate3_details` are byte-for-byte unchanged from before this story (no external call, no new fields).
- **AC-4:** Given a flag whose sample text is unavailable for any reason, When the judge is invoked, Then the pass fails safe (keeps the flag, as the existing `verdict is None` path does) rather than sending a label string.

## Edge Cases
- Multiple flags on the same `sample_id` across different domains — each judge call must get that sample's text for the correct domain.
- PII redaction must still be applied to whatever text is sent (never send raw unredacted PII to the external judge).
- `MAX_LLM_CALLS_PER_BATCH` cap and `llm_parse_failures` accounting must be preserved.

## Out of Scope
- Removing/keeping the external-model call as a compliance matter — that is **STORY-102**.
- Removing the dead `false_positive_reduction_rate` math — that is **STORY-107**.
- Changing the DIR/score formula, thresholds, or any other gate.

## Non-Functional Requirements
- risk-scoring invariants: scoring math, gate status thresholds, and SHAP unchanged. Follow `.claude/skills/risk-scoring`.
- No new PII egress; redaction preserved. Deterministic keyword-only path must stay deterministic.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_gate3_judge_receives_sample_text_not_signal_label` (real text reaches judge, label does not) | engine.py |
| AC-2 | full gate3 suite (88 passed) — confirm/reject control flow unchanged | engine.py |
| AC-3 | `test_llm_classification_absent_without_api_key` (keyword-only path unchanged) | engine.py |
| AC-4 | fail-safe guard `if not flag.text` keeps flag with no judge call | engine.py:1367 |
| PII | same test asserts SSN `123-45-6789` redacted to `***-**-****` before egress | engine.py (`_redact_pii`) |

**Status:** done. Independent `reviewer` agent: APPROVE (PII egress provably safe — `flag.text` only ever holds `_redact_pii` output). Logged FND-014, pinned in `tests/regression/manifest.yaml`. Branch `story/STORY-101_gate3_llm_judge_input_fix` (stacked on 107).
