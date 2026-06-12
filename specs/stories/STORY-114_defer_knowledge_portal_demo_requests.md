# STORY-114: Defer Knowledge Portal and Demo Requests — Remove from Buyer-Facing Scope
Status: draft
Screen/Area: Product Scope / Knowledge Portal, Demo Requests tabs

## Goal
Neither feature serves a buyer persona; both expand QA and EVF validation scope before the first QCO is issued (Demo Requests is a sales CRM living inside the product). Feature-flag both off, remove from all persona navs (admin may retain behind flag), and move their backlog items to a Deferred section so the validation surface matches what the EVF can actually defend.

GRC mapping: audit-surface minimization; every shipped tab pre-QCO widens FR-EVF coverage obligations.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given any non-admin persona, When the app renders, Then no Knowledge Portal or Demo Requests nav item or route is reachable (403/redirect at API layer too).
- AC-2: Given the feature flags (default off), When an admin enables one in a non-production environment, Then the feature works unchanged — deferral, not deletion.
- AC-3: Given `docs/backlog.md`, When updated, Then both features sit under a "Deferred (post-first-QCO)" heading with re-entry criteria stated.
- AC-4: Given EVF scope documentation, When updated, Then deferred surfaces are explicitly listed as out of current validation scope.
- AC-5: Given the regression manifest, When run, Then tests for deferred features are tagged/skipped in the buyer-facing suite but still runnable behind the flag.

## Edge Cases
- Existing demo-request records in the database → retained; data is not deleted by a UI deferral.
- Knowledge Portal links embedded in onboarding emails or docs → updated or removed.

## Out of Scope
- Deleting either feature's code; building an external CRM replacement.

## Non-Functional Requirements
- Flags evaluated server-side (no client-only hiding). Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
