STORY-013: DPA and Retention Publication (S-1203 / Gate G-3)
Status: draft    Screen/Area: Governance Trust Page

Goal
Publish the legal-reviewed DPA template and retention schedule so procurement review starts without a meeting. Draft until STORY-002's V-2 confirms the GOV-003 artifact; if absent, scope escalates to drafting the DPA per Critical Gap 3. Closes FB-026 (DPA half).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the V-2 result from STORY-002, When this story starts, Then the disposition is confirmed: EVIDENCE (publish existing artifact) or BUILD (draft DPA + retention schedule, legal review required) — recorded in CONCERNS
AC-2: Given the Trust page, When it renders, Then the DPA template and retention schedule display, versioned, with the legal-review record noted
AC-3: Given the retention schedule, When it is reviewed, Then the FR-EVF-20 seven-year EVF retention is cross-referenced with no contradicting periods
AC-4: Given docs/compliance-claims.md, When Gap 3 status is updated, Then it reads CLOSED with an evidence link

Edge Cases
- GDPR/CCPA divergence in retention rows: schedule must state jurisdiction per row, not a single global period.
- Template fields (customer name, dates) clearly marked as fill-ins — not pre-filled examples that look executed.

Out of Scope
- Per-customer DPA negotiation.
- DORA/SOC 2/FedRAMP additions (separate track per GRC scope).

Non-Functional Requirements
Documents versioned in DOCUMENT_REGISTER. Prohibited-words lint applies.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
