# STORY-104: Reconcile NIST Subcategory Count — 72 vs 68 Single Source of Truth (G-4)
Status: ready
Screen/Area: Reports API (`reports.py:328`) / `docs/nist-coverage-rubric.md`

## Goal
The coverage endpoint docstring and response claim "all 72 subcategories" while the rubric states "12 of 68" and "the map is complete (68/68)." One number is wrong, inside the artifact pair built specifically to prevent citation discrepancies. Establish a single authoritative count derived from the actual NIST AI RMF subcategory map, referenced by both code and docs, with a parity test.

GRC mapping: NIST AI RMF self-assessment integrity (the prior 38-subcategory self-assessment doc must also be checked for consistency); ISO/IEC 42001 A.6.2.2 (documentation accuracy).

## Acceptance Criteria (Given/When/Then)
- AC-1: Given the canonical subcategory map data structure, When its length is computed, Then a single module-level constant (e.g., `NIST_SUBCATEGORY_COUNT`) is derived from it — never hard-coded in prose strings.
- AC-2: Given `reports.py` coverage endpoint, When the response and docstring are generated, Then both interpolate the constant.
- AC-3: Given `docs/nist-coverage-rubric.md`, When read, Then every count cited matches the constant, and a doc-parity test fails CI if a numeric drift is introduced.
- AC-4: Given the discrepancy investigation, When the correct count is determined (against the published NIST AI RMF 1.0 categories/subcategories actually mapped), Then a finding (`/finding`) records which artifact was wrong and why, closing the loop in the ledger.

## Edge Cases
- The map intentionally excludes some subcategories → rubric must say "X of Y mapped" with both numbers from the same source.
- Cached/archived report PDFs already issued with the wrong number → list them; no silent retro-editing of issued evidence.

## Out of Scope
- Expanding actual NIST coverage; this is a citation-integrity fix only.

## Non-Functional Requirements
- Parity test runs in CI quality gate; standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
