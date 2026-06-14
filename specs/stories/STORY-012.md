STORY-012: Trust Page — IR Plan and RTO Publication (S-1202 / Gate G-1)
Status: draft    Screen/Area: Governance Trust Page

Goal
Publish the incident response plan and RTO commitments so operational maturity is verifiable pre-contract. Draft until VERIFY V-1 resolves (RTO tier values sourced from the actual IR plan — chat-history figures are not authoritative). Closes FB-009/026 (IR half).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the actual IR plan document, When V-1 runs, Then the published two-tier RTO values match the source document byte-for-byte, with the source path recorded in CONCERNS
AC-2: Given the Governance Trust page, When it renders, Then the IR plan summary (9 scenarios) and RTO table display with versioned PDF downloads
AC-3: Given docs/compliance-claims.md, When Gap 1 status is updated, Then it reads CLOSED with an evidence link to the published artifact

Edge Cases
- IR plan contains internal-only escalation contacts: publish a summary version, retain full version access-controlled.
- PDF version stamp must match DOCUMENT_REGISTER entry.

Out of Scope
- Contractual SLA language (FB-029 deferred).
- Editing the IR plan content itself.

Non-Functional Requirements
Playwright render + download tests. Page load under 2s.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
