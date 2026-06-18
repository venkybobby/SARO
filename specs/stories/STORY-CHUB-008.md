STORY-CHUB-008: Compliance Hub — loading skeletons and visible error states
Status: ready    Screen/Area: Compliance Hub
Epic: GRC-Compliance-Hub · Priority: P2 · Depends on: STORY-CHUB-007

Goal
The Compliance Hub uses plain "Loading…" text and swallows failures (`.catch(() => {})` on the audits fetch; coverage sets a banner but other failures are invisible). Loading and failure are indistinguishable from empty, which reads as "broken." Add real skeletons and surfaced, non-silent error states for every fetch on the screen.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 13 (transparency — the user must be able to tell missing data from failed data from empty data).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given each data section in `frontend/src/pages/ComplianceHub.jsx` (EVF status, recent audits, calendar, readiness), When data is loading, Then a `Skeleton` placeholder renders for that section.
AC-2: Given any fetch returns a non-OK status or throws, When the section renders, Then a visible, section-scoped error state is shown (message + retry affordance), and no error is swallowed silently.
AC-3: Given a fetch succeeds but returns an empty set, When rendered, Then a distinct empty state ("No audits yet", "No matrix data yet") is shown — visually different from the error state.
AC-4: Given a transient failure, When the user clicks retry, Then only that section re-fetches (no full-page reload).

Edge Cases
- Partial failure: EVF loads but audits 403s → audits shows error, EVF still renders normally (no whole-page failure).
- Slow network: skeletons persist until resolve/reject, never flicker to empty first.

Out of Scope
- Changing fetch endpoints or auth.
- Global error-boundary work outside this screen.

Non-Functional Requirements
- Each section's loading/error/empty/success states are mutually exclusive and individually testable.

Test Requirements
- Frontend unit (`ComplianceHub.test.jsx`): loading → skeleton; reject → error + retry; empty → empty state; partial failure isolates to the failing section; retry re-fetches only that section.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	ComplianceHub.test.jsx "AC-1: each section shows a Skeleton while loading"	frontend/src/pages/ComplianceHub.jsx (per-section *Status + Skeleton)
AC-2	ComplianceHub.test.jsx "AC-2/AC-4: rejected audits fetch shows a section error with retry"	frontend/src/pages/ComplianceHub.jsx (SectionError + loadAudits/loadCoverage/loadReadiness + ComplianceCalendar)
AC-3	ComplianceHub.test.jsx "AC-3: successful empty fetch shows the empty state, distinct from error"	frontend/src/pages/ComplianceHub.jsx
AC-4	ComplianceHub.test.jsx "AC-2/AC-4: ...retry re-fetches only that section" + "edge: partial failure isolates"	frontend/src/pages/ComplianceHub.jsx (per-section loaders)
