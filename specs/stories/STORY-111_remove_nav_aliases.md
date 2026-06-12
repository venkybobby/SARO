# STORY-111: Remove Duplicate Nav Aliases (evidence_export, vendor_risk, ir_plan)
Status: ready
Screen/Area: Navigation / `Sidebar.jsx:45–51`

## Goal
Three sidebar items are aliases pointing at pages other items already cover: `evidence_export` → trace_view, `vendor_risk` → risk_summary, `ir_plan` → governance_docs. An evaluator clicking two items and landing on the same page downgrades the whole UI's credibility. Remove the aliases; if a destination genuinely warrants a distinct entry point later, it gets a distinct page via its own story.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given the sidebar config, When rendered for every persona, Then no two nav items resolve to the same route/page component.
- AC-2: Given the three alias slugs, When any bookmarked/deep-linked URL using them is visited, Then a 301-style client redirect lands on the canonical page (no 404s for existing users).
- AC-3: Given the Persona→Tab Mapping Matrix, When updated, Then alias rows are removed and per-persona tab counts are restated honestly.
- AC-4: Given a CI/lint check on the sidebar config, When a future PR introduces two items targeting one route, Then the check fails.

## Edge Cases
- Any persona whose ONLY path to a page was via an alias → ensure the canonical item is in that persona's mapping before removal.
- In-app onboarding text referencing the alias names → update strings.

## Out of Scope
- Building real Evidence Export / Vendor Risk / IR Plan pages.

## Non-Functional Requirements
- Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
