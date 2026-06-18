STORY-TRACE-005: Enforce the ADR-004 TRACE gate ("How SARO Reasons" link + demo gate)
Status: ready    Screen/Area: TRACE View
Epic: GRC-TRACE-View · Priority: P0 · Depends on: —

Goal
ADR-004 requires the "How SARO Reasons" transparency document (authored by the ML Lead) to exist before any enterprise demo of the TRACE view. The page exists (`frontend/src/pages/HowSaroReasons.jsx`), but `TraceView.jsx` neither links to it nor gates on it, so TRACE can be demoed with the transparency doc absent — violating the ADR-004 gate. Surface the methodology link and gate enterprise/demo presentation on the doc's presence/readiness.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 13 (transparency — methodology disclosure accompanies the reasoning view).
- ADR-004: "TRACE View Gate" enforced in product, not just policy.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the TRACE View, When it renders, Then it shows a visible "How SARO Reasons" link/affordance that navigates to `HowSaroReasons.jsx`.
AC-2: Given a readiness flag/config representing whether the transparency doc is authored and approved, When the doc is NOT ready and the session is in an enterprise/demo context, Then the TRACE technical mode (or full reasoning detail) is gated with a clear notice referencing the requirement, rather than freely shown.
AC-3: Given the doc IS ready, When TRACE renders in any context, Then no gating notice appears and all modes are available (subject to role).
AC-4: Given the gate state, When determined, Then it is sourced from an explicit configuration/flag (single source of truth) — not hardcoded in the component.

Edge Cases
- Internal (non-demo) sessions for permitted roles are not blocked from their normal work by the gate — the gate targets enterprise/demo presentation, per ADR-004 wording.
- If the readiness flag is missing/unset, default to the safe (gated) state.

Out of Scope
- Authoring the "How SARO Reasons" content (owned by ML Lead per ADR-004).
- TRACE rendering correctness (STORY-TRACE-001).

Non-Functional Requirements
- Gate decision passes `/saro:compliance-check`; default-deny when readiness is unknown.

Test Requirements
- Frontend unit (`TraceView.test.jsx`): link present and navigates; doc-not-ready + demo context → gated notice; doc-ready → ungated; missing flag → gated (default-safe).

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
