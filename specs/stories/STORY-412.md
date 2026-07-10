# STORY-412: Demo surface trim — every visible tab must survive a click

**Status:** ready
**Screen/Area:** Public demo (`/demo`) — Sidebar navigation + demo-token backend contract
**Epic:** GRC-10 — Demo Readiness
**Priority:** P0 · **Depends on:** none (S-205/S-205B shipped)

## Context
The public `/demo` route issues a JWT with `role=demo_viewer, persona_role=compliance_lead`.
The Sidebar renders the `compliance_lead` tab set, which includes AIMS, Evaluations, Trust
Center, and Upload — all backed by endpoints gated `require_role("super_admin", "operator")`
or write-gated. A prospect one click off the happy path watches a 403/empty screen. The demo
must show fewer things that all work, not more things that mostly work.

## Framework mapping
- Internal: INV-2 discipline (demo shows only what is real); ADR-004 (no implied capability
  the persona cannot exercise).

## Goal
A prospect in `/demo` can click every visible element without hitting a single 403,
empty-by-error screen, or disabled write path presented as available; CI proves it stays
that way.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given a freshly minted demo token, when the integration test enumerates every GET
  endpoint each `DEMO_TABS` page calls on load, then every one returns 200 (not 401/403),
  proven in CI.
- AC-2: Given a demo session (`role === "demo_viewer"`), when the Sidebar renders, then it
  shows exactly `DEMO_TABS` (`dashboard`, `trace_view`, `compliance_hub`, `reports`) — no
  AIMS, Evaluations, Trust Center, Upload, Onboarding, or admin tabs — pinned by a component
  test.
- AC-3: Given a demo session, when the Sidebar renders, then the persona switcher is not
  rendered — pinned by a test confirming `demo_viewer` cannot switch.
- AC-4: Given a demo token, when a write endpoint is attempted, then it still returns 403
  (existing `require_write_access` behavior — regression-pinned, not newly built).
- AC-5: Given a non-demo session, when the Sidebar renders, then tab sets are identical to
  today — zero behavior change outside demo mode (snapshot/regression test).

## Scope (in)
1. **Frontend:** explicit `DEMO_TABS` whitelist in `Sidebar.jsx`; when the session is a demo
   session, render only `DEMO_TABS` regardless of persona tab set. Initial whitelist:
   `dashboard`, `trace_view`, `compliance_hub`, `reports` — each pending AC-1 verification;
   any tab failing AC-1 is removed from the whitelist rather than its gate being widened.
2. **Backend contract test:** an integration test that mints a demo token (as
   `GET /api/v1/demo/token` does), enumerates every GET endpoint each `DEMO_TABS` page calls,
   and asserts none returns 403. The whitelist and the test read from one shared fixture list
   so they cannot drift apart.
3. **Persona switcher:** hidden in demo mode (`canSwitch` already checks base role — verify
   `demo_viewer` cannot switch; add a test pinning it).

## Out of Scope
- Widening any `require_role` gate to admit `demo_viewer` (expands the attack surface of a
  public, unauthenticated-issuance token — explicitly rejected direction).
- The logged-in operator demo path (unaffected).
- Fixing the `persona_required(["compliance_lead","admin"])` varargs bug in
  `routers/compliance_hub.py:138` — distinct defect, file separately (this story stays
  surgical).

## Edge Cases
- `ComplianceHub.jsx` fires `compliance-matrix/coverage`, `evf/validation-status`,
  `evf/qco/expiry-alerts`, `audits`, `compliance/readiness` — AC-1 must cover all five; if any
  is role-gated above `demo_viewer`, the page either degrades that panel gracefully or the
  tab leaves the whitelist.
- `Reports` uses `_require_reports_access` (role-or-persona); expected to pass via
  `persona_role=compliance_lead` — verify, don't assume.

## Non-Functional Requirements
- Simplest correct mechanism: filter at render time in `Sidebar.jsx`; do not fork
  `PERSONA_TABS`.
- Standard project rules (compliance-guard, api-conventions).

## Test Requirements
- Integration: demo-token endpoint census (AC-1), lives beside
  `tests/regression/test_fnd_028_trace_audit_read_access.py`.
- Component: Sidebar demo whitelist render (AC-2), switcher hidden (AC-3).
- Regression: non-demo tab sets unchanged (AC-5).

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
