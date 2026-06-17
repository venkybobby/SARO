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

## Traceability (implementation)
New isolated package `qa_lab/` (top-level, `LAB_PACKAGE` in STORY-336). The judge
is the sole sanctioned external-model use — offline, off by default (raises if
`ANTHROPIC_API_KEY` unset), PII-redacted before egress. `LabelingHarness` enforces
human adjudication before any label enters the corpus; `LabeledItem.to_record()`
emits full provenance.

| AC | Test(s) |
|---|---|
| Runs only in QA/lab; unreachable from product (verified by 336) | `test_product_path_does_not_import_qa_lab`, `test_qa_lab_is_outside_the_336_product_scope` |
| LLM label cannot enter corpus without recorded human adjudication | `test_unadjudicated_item_cannot_enter_corpus`, `test_pending_record_is_marked_unadjudicated` |
| Every item carries full provenance (source, suggestion, decision, labeler, time) | `test_adjudicated_item_enters_corpus_with_full_provenance`, `test_human_can_override_the_llm_suggestion`, `test_end_to_end_flow` |
| Synthetic T1: suggestion vs known label, delta recorded | `test_synthetic_defect_delta_recorded`, `test_synthetic_defect_delta_records_a_miss` |
| PII redacted before egress (SARO-102) | `test_pii_redacted_before_suggester_sees_sample`, `test_redact_pii_helper`, `test_redact_pii_covers_delimited_ssn_and_ipv4` |

Review: `reviewer` APPROVE; `security-auditor` PASS. Hardened per findings —
broadened redactor (delimiter SSNs + IPv4), defensive provider-response parsing,
explicit `adjudicated` flag on records. Residual limits (regex redactor misses
names/addresses/DOB — needs NER; static-only isolation per 336) documented and
appropriate for an offline lab over synthetic/anonymized samples.
