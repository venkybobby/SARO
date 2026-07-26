# STORY-AISEC-007: Semantic prompt-injection on the optional Gate-3 judge

**Status:** draft
**Screen/Area:** engine.py (injection scan / optional LLM judge) / COMPLIANCE_CLAIMS_MATRIX

## Origin
The STORY-AISEC-003 benchmark measured **held-out recall 0.0**: the deterministic
regex detector (AISEC-001, hardened by AISEC-005) does not generalize to novel
injection phrasings. Non-Negotiable #1 bars external models from SARO's **core**
scoring, so held-out generalization can only be closed on the **already-disclosed,
off-by-default Gate-3 LLM judge** (SARO-102). This story extends that judge to
catch injection semantically **when a tenant enables it** — zero external calls
when off (the default), bounded, PII-redacted, evidence-only.

## Premise verification (FM-2 — verified before authoring)
| Referenced artifact | Verified? | File path |
|---|---|---|
| Existing off-by-default Gate-3 judge | yes | `engine.py` (`_gate3_llm_verify_sync`, `ANTHROPIC_API_KEY` gate, `MAX_LLM_CALLS_PER_BATCH`, `LLM_JUDGE_PROVIDER/MODEL`) |
| PII redaction before egress | yes | `engine.py` `_redact_pii` (applied to fragments before the judge sees them) |
| Injection scan (evidence-only) | yes (MERGED) | `engine.py` `_scan_injection` / `_scan_injection_impl` |
| Disclosed judge exception | yes | `docs/COMPLIANCE_CLAIMS_MATRIX.md` §"External Model Usage — Optional Gate-3 LLM Judge (SARO-102)" |
| Held-out gap = 0.0 | yes | `saro-data-framework/output/injection_eval_batch.json` (`by_source.held-out`) |
| anthropic client installed | yes | `anthropic` 0.84.0 |

## Goal
Add an **optional, off-by-default** semantic prompt-injection pass to the injection
scan: when the tenant has enabled the Gate-3 judge (its API key is set), assess
the samples the deterministic detector did **not** flag for injection/jailbreak/
system-prompt-leakage, and emit **evidence-only** findings for those the judge
identifies. Reuses the existing judge infra: provider seam, `MAX_LLM_CALLS_PER_BATCH`
cap, and `_redact_pii` before egress. Update SARO-102 disclosure to match.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given no `ANTHROPIC_API_KEY` (the default), When a batch is scored, Then
  the semantic pass makes **zero** external calls and behavior is deterministic-
  only (unchanged) — proven by a socket-blocked/mock-call-count assertion.
- AC-2: Given the judge is enabled (key set) and a held-out injection sample the
  deterministic detector missed, When scored, Then the semantic pass (mocked LLM
  returning an "injection" verdict) emits an evidence-only injection TRACE entry
  tagged `source: semantic-judge`.
- AC-3: Given a sample already flagged deterministically, When the semantic pass
  runs, Then it is **not** re-sent to the LLM (no duplicate cost/finding).
- AC-4: Given egress, When the judge is called, Then the sample text is
  **PII-redacted** (`_redact_pii`) before it leaves the process, and the batch is
  bounded by `MAX_LLM_CALLS_PER_BATCH`.
- AC-5: Given the semantic pass, When it runs, Then it changes **no risk score**
  (evidence-only, no `_SampleFlag`), and any LLM/parse error fails safe (the
  deterministic result stands; no crash).
- AC-6: Given the change, When merged, Then `docs/COMPLIANCE_CLAIMS_MATRIX.md`
  SARO-102 is updated to disclose that the optional judge now also assesses
  un-flagged samples for injection (still off-by-default, PII-redacted, bounded).

## Edge Cases
- Unknown `SARO_LLM_JUDGE_PROVIDER` → fail safe to deterministic-only (no calls).
- LLM returns malformed JSON → treated as "no verdict", sample not flagged.
- Empty/blank sample → skipped (no call).

## Out of Scope
- Turning the judge on by default (stays off; tenant opt-in only).
- Changing the existing flagged-sample FP-reduction judge behavior.
- Any change to core deterministic scoring or the risk score.
- A real-LLM benchmark (tests use a mocked client; real held-out recall is
  demonstrated with the mock + documented, not measured against a live model).

## Non-Functional Requirements
- Off-by-default; zero external calls without the key. Deterministic default path
  unchanged. Evidence-only. PII-redacted before egress. Bounded by the cost cap.
- reviewer + security-auditor approve (engine.py + external-model egress path).
- compliance-guard: SARO-102 disclosure updated to match the code.

## Benefits
- **Closes the held-out generalization gap** the AISEC-003 benchmark exposed — the
  only posture-compliant way (on the disclosed, opt-in judge path).
- **Cost-safe & honest:** zero cost by default; when enabled, bounded and
  PII-redacted; the disclosure is updated so posture statement and code agree.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 (off by default, zero calls) | `test_no_key_makes_no_llm_calls_and_no_semantic_trace` | `engine.py` (`_scan_injection_semantic`) |
| AC-2 (enabled catches held-out) | `test_enabled_judge_flags_held_out_injection`, `test_enabled_but_benign_verdict_does_not_flag` | `engine.py` (`_scan_injection_semantic`, `_semantic_injection_verify_sync`) |
| AC-3 (flagged not re-sent) | `test_already_flagged_sample_is_not_sent_to_the_judge` | `engine.py` |
| AC-4 (PII-redacted egress, bounded) | `test_egress_text_is_pii_redacted` | `engine.py` (`_redact_pii`, `MAX_LLM_CALLS_PER_BATCH`) |
| AC-5 (evidence-only, fail-safe) | `test_semantic_pass_adds_no_risk_domain_flag`, `test_llm_error_fails_safe` | `engine.py` |
| AC-6 (disclosure updated) | (doc) | `docs/COMPLIANCE_CLAIMS_MATRIX.md` §SARO-102 |
