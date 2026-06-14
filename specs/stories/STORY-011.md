STORY-011: Honest NIST Coverage Report (S-1105)
Status: ready    Screen/Area: Compliance Hub / Reports

Goal
Publish the honest map of all 72 NIST AI RMF subcategories so coverage claims match engineering reality and can be attached to contracts. Closes FB-016/030/039.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the nist_ai_rmf_controls table, When the seed migration runs, Then all 72 subcategories exist with version 'AI RMF 1.0' and last_updated populated
AC-2: Given GET /api/v1/reports/nist-coverage, When it is called, Then exactly 72 entries return, each with status mapped | partial | not_covered | requires_human_assessment derived from _COMPLIANCE_TRIGGERS plus docs/nist-coverage-status.yaml
AC-3: Given the Compliance Hub coverage panel, When it renders, Then the 'N of 72 automated' headline equals the trigger-dict derivation (test-asserted)
AC-4: Given the coverage panel, When PDF export is clicked, Then a valid PDF downloads suitable for contract attachment

Edge Cases
- A subcategory present in the YAML but absent from the seed (or vice versa) fails the completeness test — the YAML is curated, the table is canonical.
- Status conflicts (trigger says mapped, YAML says partial): YAML wins and the discrepancy is logged.

Out of Scope
- Expanding actual coverage (SARO-004 parked — honesty before expansion).
- NIST Profile generation.

Non-Functional Requirements
Endpoint cacheable; no per-request recomputation of the trigger derivation.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
