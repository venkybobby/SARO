STORY-003: EVF Artifact Pack (S-1001)
Status: ready    Screen/Area: Governance Docs / EVF

Goal
File the six External SME Validation Framework documents implementing GRC FR-EVF-01/03/04/16/18/20 so SME engagements can begin against approved templates. Closes FB-001 (partial)/037.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given docs/evf/, When the pack is created, Then sme-qualification-criteria.md, coi-declaration-form.md, sow-template.md, language-tier-policy.md, claims-challenge-protocol.md, and evf-retention-addendum.md all exist and are version-controlled
AC-2: Given each document, When its content is compared to the GRC requirements doc, Then it implements its FR-EVF spec verbatim, including all mandatory elements (e.g., 7 SOW elements, 3 COI coverage areas, 3 language tiers)
AC-3: Given each document, When reviewed for approval workflow, Then legal-approval placeholder fields are present
AC-4: Given tests/test_evf_docs.py, When pytest runs, Then file-existence and mandatory-section assertions pass for all six documents

Edge Cases
- Language-tier policy must embed the prohibited-words list (certified / certification / conformity assessment) so STORY-007's lint test has a single source.
- Retention addendum must reference the 7-year minimum per FR-EVF-20 and flag alignment with the DPA policy (STORY-013).

Out of Scope
- SME outreach itself (STORY-004).
- QCO content authoring.

Non-Functional Requirements
Standard project rules. Documents classified CONFIDIDENTIAL-internal until legal approval recorded.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
