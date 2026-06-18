STORY-TRACE-010: Loading skeletons and differentiated error states (403 / 404 / network)
Status: ready    Screen/Area: TRACE View
Epic: GRC-TRACE-View · Priority: P2 · Depends on: STORY-TRACE-009

Goal
On any non-OK response, `TraceView.jsx` throws `"${status} — audit not found"`, so a 403 (no access), a real 404 (missing), and a network failure all read as "audit not found." It also uses plain "Loading…" text. Distinguish the failure causes and add real skeletons so loading, empty, and the different errors are visually distinct.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 13 (transparency — the user must be able to tell "no access" from "not found" from "failed").

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a trace request returns 403, When it renders, Then the message is access-oriented ("You don't have access to this audit's trace"), not "audit not found".
AC-2: Given a 404, When it renders, Then the message is "Audit not found / no trace for this ID".
AC-3: Given a network/5xx error, When it renders, Then the message indicates a transient failure with a retry affordance.
AC-4: Given a trace is loading, When the strip and panels render, Then `Skeleton` placeholders are shown (not bare "Loading…").
AC-5: Given a successful load returning zero steps, When rendered, Then a distinct empty state is shown (separate from any error state).

Edge Cases
- Recent Traces failure stays non-fatal and does not surface as a trace-load error.
- Retry re-fetches only the trace, not a full page reload.

Out of Scope
- Endpoint/auth changes (STORY-TRACE-002/003).
- Design tokens beyond what STORY-TRACE-009 introduces.

Non-Functional Requirements
- Loading/empty/error states are mutually exclusive and individually testable.

Test Requirements
- Frontend unit (`TraceView.test.jsx`): 403 → access message; 404 → not-found; network → transient + retry; loading → skeleton; empty-steps success → empty state.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
