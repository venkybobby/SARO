STORY-007: QCO Registry + Validation Status Badges (S-1003)
Status: ready    Screen/Area: Compliance Hub / Backend

Goal
Surface external-validation status on every framework claim so reviewed claims are distinguishable from internal opinion. Uses the EXISTING super_admin role — no Epic 9 dependency. Closes FB-001 (product surface)/024.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a published QCORegistry row, When an UPDATE or DELETE is attempted directly in the database, Then the DB trigger blocks it and the test proves the block
AC-2: Given a non-super_admin user, When POST /api/v1/qco or POST /api/v1/qco/{id}/publish is called, Then the API returns 403
AC-3: Given the Compliance Hub, When any framework label renders, Then a badge shows 'Externally Reviewed — QCO [ref]' or 'Internal Review Only — Not for External Claim' (Playwright-asserted)
AC-4: Given a framework with no QCO, When its claim text renders, Then only Tier-2 approved language from the language-tier policy appears
AC-5: Given all UI strings and registry records, When the prohibited-words lint test runs, Then zero occurrences of 'certified', 'certification', or 'conformity assessment' (AC-09b)

Edge Cases
- Expired QCO (expiry_date past): badge must fall back to 'Internal Review Only' automatically — read expiry at render.
- Amendments create new versioned rows; published rows are immutable (AC-10b).

Out of Scope
- SME lifecycle state-machine automation.
- Expiry notification workflow (Parking 5a / FR-EVF-13).

Non-Functional Requirements
Registry queryable by Sales/Legal on demand (FR-EVF-10). Migration wrapped in transaction with rollback comment.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
