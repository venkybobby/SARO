# STORY-379: Buyer-Facing Validation Report Generator

**Status:** ready
**Screen/Area:** Backend script + compliance docs (Pack Epic 18)
**Depends on:** STORY-378 artifacts

## Goal
A generated validation report (methodology, corpus description, per-pack rates,
known limitations) a technical buyer can take to their own risk review.

## Acceptance Criteria
- AC-1: Report generated from STORY-378 JSON artifacts — no hand-typed numbers
  (`scripts/generate_validation_report.py`).
- AC-2: Limitations section honest by construction: synthetic-corpus caveats,
  tiers not covered (T4 pilot data absent), adapters not yet validated —
  understatement over overstatement.
- AC-3: Language guardrails (docs/compliance-claims.md): no "certified", no
  client results; generator refuses to emit forbidden phrases (lint step).
- AC-4: Output: markdown + PDF (fpdf2, matching generate_governance_pdfs.py
  conventions) into docs/validation/.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_report_is_current_with_the_artifact`, `test_numbers_come_from_the_matrix_not_the_source`, `test_real_matrix_rates_appear_in_the_report` | `scripts/generate_validation_report.py` reads `quality/validation/confusion-latest.json` |
| AC-2 | `test_limitations_name_the_tiers_not_covered`, `test_limitations_disclose_synthetic_corpus_and_unsigned_bar`, `test_report_does_not_imply_a_pass_while_the_bar_is_unsigned` | generated Limitations section |
| AC-3 | `test_report_contains_no_prohibited_claim_language`, `test_language_guard_trips_on_each_prohibited_phrase`, `test_report_states_no_customer_results` | generator refuses prohibited claim language |
| AC-4 | `test_pdf_is_generated_and_nonempty`, `test_report_lives_in_the_compliance_docs_area` | `docs/validation/validation-report.{md,pdf}` |

## Design notes
- **Generated, never hand-typed** (AC-1): every rate is read from 378's
  artifact; a test asserts changing the artifact changes the report. Generation
  is the anti-drift control.
- **Limitations derived and deliberately unflattering** (AC-2): computed from
  the actual state — only T1 measured, T2/T3/T4 named as uncovered, corpus
  synthetic, bar unsigned. A perfect T1 score is presented AS a narrow synthetic
  result, not as broad validation. While the bar is unsigned the report says
  plainly these are *measured rates, not a pass against an agreed bar*.
- **Language guardrail caught my own disclaimer.** "not a regulatory approval"
  contains the forbidden phrase even while denying it — same class as the
  earlier docstring cases. Reworded so the disclaimer doesn't need the forbidden
  bigram; the guard staying blunt is correct.
