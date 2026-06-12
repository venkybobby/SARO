# STORY-101: Fix Gate-3 LLM-Judge Input — Send Redacted Sample Text, Not Signal Name (G-1)
Status: ready
Screen/Area: Scoring Engine / Hybrid Gate-3 (`engine.py`) + DPA Sub-Processor Annex

## Goal
The LLM-as-judge currently receives `flag.signal` (the matched keyword/pattern name, `_SampleFlag` def engine.py:503–507) instead of the customer's AI output sample (engine.py:1365). The judge must evaluate **redacted, truncated sample text** so that (a) contextual false-positive reduction is real, (b) `false_positive_reduction_rate` persisted to `AuditTrace.detail_json` is methodologically founded, and (c) the data flow matches the DPA sub-processor annex disclosure ("AI model output samples, truncated to 500 characters" — saro-dpa-template-v1.0.md:205).

GRC mapping: EU AI Act Art. 10 (data governance) & Art. 13 (transparency); ISO/IEC 42001 A.7 (data for AI systems) & A.6.2.4 (verification/validation); NIST AI RMF MEASURE 2.5 / MANAGE 2.2. A persisted accuracy metric with no methodological basis is a misrepresentation risk in any audit or contract claim.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given hybrid mode is active (`ANTHROPIC_API_KEY` set, tenant opted in), When `_gate3_llm_verify_sync` is invoked for a flagged sample, Then the API payload contains the **redacted sample text truncated to ≤500 characters**, and the matched signal name is passed only as structured context (e.g., `matched_pattern` field), never as the text under judgment.
- AC-2: Given a sample containing PII (email, SSN, phone patterns), When the payload is constructed, Then PII is redacted **before** egress to the sub-processor, and a unit test proves no raw PII leaves the boundary.
- AC-3: Given hybrid mode did NOT run for a scan (no key, opt-out, or API failure), When the scan completes, Then `false_positive_reduction_rate` is **absent/null** in `AuditTrace.detail_json` — never a fabricated value.
- AC-4: Given the fix is merged, When the DPA annex (saro-dpa-template-v1.0.md §sub-processors) is compared to the actual payload schema, Then the disclosure matches the implemented data flow word-for-word on: what is sent, truncation limit, redaction step, and purpose.
- AC-5: Given a regression test fixture with a known false positive (e.g., medical-context "vaccine" in legitimate clinical text), When Gate-3 runs against the fixed payload, Then the judge can downgrade the flag — demonstrating contextual FP reduction is now functionally possible.

## Edge Cases
- Sample text is empty/whitespace → skip Gate-3, log skip reason, no metric persisted.
- Sample shorter than 500 chars → send as-is post-redaction.
- Anthropic API timeout/error → fall back to deterministic Gate-1/2 score; flag retains pre-judge state; failure logged to audit trail with no metric.
- Redaction removes the very token that triggered the flag → pass `matched_pattern` context so the judge still has signal provenance.
- Multi-flag samples → one judge call per sample (not per flag) to bound cost and sub-processor exposure; aggregate verdicts.

## Out of Scope
- Removing or redesigning hybrid mode (kill-switch decision is STORY-102's claims work; this story fixes the implementation).
- Changing the judge model or prompt-engineering optimization beyond what AC-5 requires.
- DPA re-execution with existing tenants (legal process, tracked under GRC gap "Data Retention/DPA Policy").

## Non-Functional Requirements
- Redaction must execute in-process before any network egress (no external redaction service).
- Payload schema versioned; version recorded in audit trace for evidentiary reproducibility.
- Standard project rules: changed code only, FILES CHANGED summary, no destructive ops without confirmation.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
