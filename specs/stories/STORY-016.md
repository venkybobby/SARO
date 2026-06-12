STORY-016: SOC 2 Readiness Self-Assessment (S-1204)
Status: ready    Screen/Area: Governance Docs / Trust Page

Goal
Map existing controls to the SOC 2 security Trust Services Criteria so the absence of attestation reads as a managed plan, not a blind spot. Closes FB-006 (readiness half).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given docs/soc2-readiness.md, When it is written, Then every SOC 2 security TSC criterion has a status row mapping to existing controls (JWT/tenant RBAC, hash-chained audit log, CI security scans, Sentry, isolation evidence) or a gap entry with owner
AC-2: Given the document, When its language is reviewed, Then an explicit 'no attestation yet' statement with intended timeline is present and the prohibited-words lint passes
AC-3: Given the Trust page, When it renders, Then a 'SOC 2 readiness assessment — available under NDA' entry is live

Edge Cases
- Controls delivered by other Phase-10 stories (STORY-015 evidence, STORY-006 provenance) are referenced by story ID so the doc stays current as they land.

Out of Scope
- Engaging an auditor (FB-027/040 — founder budget decision OQ-2).
- Availability/confidentiality/privacy TSC categories beyond security.

Non-Functional Requirements
Honest-language standard: every claim verifiable in-repo. Document registered in DOCUMENT_REGISTER.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
