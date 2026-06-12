# STORY-113: Merge Risk Summary into Risk Register as a View
Status: draft
Screen/Area: UI Architecture / Risk Summary, Risk Register (Risk Officer cluster)

## Goal
Risk Summary and Risk Register overlap; Summary should become a view/filter of the Register, reducing the risk cluster (Dashboard, Summary, Register, Detail) by one surface while keeping every Risk Officer job-to-be-done reachable.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given the Risk Register page, When the "Summary" view is selected, Then it renders the aggregate content the standalone Risk Summary provided today (parity checklist attached to PR).
- AC-2: Given the `risk_summary` route, When visited, Then it redirects to the Register's summary view.
- AC-3: Given the vendor_risk alias removal in STORY-111 (which pointed at risk_summary), When both stories are merged, Then the redirect chain resolves in one hop to the Register summary view.
- AC-4: Given risk_officer and admin personas, When mappings are updated, Then the standalone Summary tab is removed and the RBAC parity test passes.

## Edge Cases
- Dashboard widgets deep-linking into Risk Summary → repoint.
- Saved report templates citing Risk Summary as a source → verify generator references the underlying service, not the page.

## Out of Scope
- Dashboard redesign; Risk Detail changes; AI Insights methodology question (separate finding — if AI Insights makes or implies model calls it needs Gate-3-equivalent disclosure; log via /finding).

## Non-Functional Requirements
- Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
