STORY-004: SME Engagement Execution — NIST + EU AI Act (S-1004 / Gate G-2)
Status: draft    Screen/Area: EVF Process / Founder-executed

Goal
Execute external SME engagements producing Qualified Compliance Opinions for the NIST AI RMF and EU AI Act scopes so external claims have a named, credentialed validator. Closes FB-001/024/038. Status stays draft until SME firms are shortlisted (external dependency, OQ-1 budget).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the _COMPLIANCE_TRIGGERS dict and repo artifacts, When Claude Code compiles the Evidence Packages, Then each package contains all five FR-EVF-06 areas: control-mapping spreadsheet, architecture diagram, data-flow documentation, sample artifacts (one full TRACE export, one evidence pack), and a known-limitations register seeded from Critical Review sections 3-4
AC-2: Given a completed Evidence Package, When Product Owner review occurs, Then a sign-off record exists before SME handover
AC-3: Given the SME Register, When SOWs are issued, Then two COI-cleared candidate firms per framework are documented and executed SOWs reference the review protocol
AC-4: Given the engagement timeline, When day 75 of the phase is reached, Then at least one draft QCO has been received
AC-5: Given the FR-EVF-08 Validation Gate checklist, When phase end is reached, Then all seven gate items pass for at least two frameworks

Edge Cases
- SME requests repo access: provide Evidence Package only — no customer data, no unreleased roadmap without separate NDA (FR-EVF-22).
- Draft QCO uses prohibited language: reject per AC-09b and return for revision (max two clarification rounds per FR-EVF-07).

Out of Scope
- AIGP and ISO 42001 engagements (EVF wave 2, parking lot).
- Publishing claims before QCO approval (blocked by Gate G-2).

Non-Functional Requirements
QCO documents CONFIDENTIAL with access control per FR-EVF-22. All correspondence retained 7 years per FR-EVF-20.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
