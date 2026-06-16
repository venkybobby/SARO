# STORY-338 — Offline LLM-as-judge labeling harness (QA lab only)

**Epic:** GRC-8 — Validation & Testing
**Priority:** P1 · **Status:** READY · **Depends on:** STORY-336
**Connects:** Validation & Testing Strategy (T1 defect verification, T3 pre-labeling)

## Context
LLM-as-judge is valuable for *building ground truth* — but only offline, isolated from the product
path, and never as the final say. It helps label and pre-screen corpus items; a human adjudicates
before any label is accepted. This is where the capability removed from the runtime (STORY-335) is
allowed to live.

## Framework mapping
- NIST AI RMF: MEASURE (test methodology).
- ISO/IEC 42001: data for AI systems (validation data governance).

## Scope (in)
- An offline labeling tool that uses an LLM-as-judge to (a) verify injected defects in synthetic data
  (T1) and (b) pre-label real/anonymized samples (T3) for SME review.
- A required human-adjudication step: no LLM-suggested label enters the validation corpus without
  human sign-off.
- Each labeled item records: source, LLM suggestion, human decision, labeler identity, timestamp.
- The package is isolated from product code and is the **only** sanctioned external-model use,
  exempted under STORY-336.

## Out of scope
- Any product-path use (forbidden). Auto-accepting LLM labels without human adjudication.

## Acceptance criteria (binary)
- [ ] The harness runs only in the QA/lab context and is unreachable from product code (verified by STORY-336).
- [ ] An LLM-suggested label cannot enter the corpus without recorded human adjudication.
- [ ] Every labeled item carries full provenance (source, LLM suggestion, human decision, labeler, time).
- [ ] On a synthetic item with a known injected defect, the harness's suggestion is compared to the known label and the delta recorded.

## Technical notes
- Reuse the existing Anthropic API pattern here (allowed offline). Keep the lab package physically
  separate (own module/dir) so the STORY-336 exemption is unambiguous.
- Output feeds the validation corpus (data strategy tiers T1/T3).

## Test requirements
- [ ] Isolation test: importing the lab package from product code is rejected/flagged.
- [ ] Flow test: suggestion → human adjudication → corpus entry with provenance.

## Definition of done
Offline judge aids labeling with mandatory human adjudication and full provenance, isolated from the product path; tests green.
