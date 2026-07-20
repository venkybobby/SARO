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
