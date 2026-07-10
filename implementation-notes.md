# STORY-412 (round 2) — reviewer REQUEST CHANGES fix-up
Stage: standard

## Lifecycle
- [x] discover   — see prior round; new recon below is scoped to the review findings only
- [x] shape      — skipped: fixes are prescribed by the reviewer's concrete repros, no new
                   architectural decision to interview on
- [x] preview    — skipped: no new visual surface, corrective wiring only
- [x] plan       — see below
- [x] build      (all 4 fixes implemented; backend 1689 passed, frontend 185 passed, lint clean)
- [x] verify     (change-debrief.html updated with round-2 section; re-dispatching
                   independent reviewer + security-auditor on the incremental diff)
- [ ] sell       — n/a

## Decision Log

Q1 (reviewer, REQUEST CHANGES round 1): `DEMO_TABS` only filtered Sidebar's own button
list — `AppShell`'s page router has zero demo-mode awareness, so any in-page `onNavigate`
call (e.g. TraceView's always-visible "How SARO Reasons ↗" link → `TrustCenter` →
`Governance.jsx` → `GET /api/v1/governance/trust-documents`, gated
`require_role("super_admin","operator")` with no persona fallback) reaches a real 403,
rendered as an empty "No trust documents configured" state. → **Fix at the enforcement
layer, not just the display layer**: `AppShell.navigateNow` now no-ops any navigation to a
page outside `DEMO_TABS` when `user?.role === "demo_viewer"` — this closes the hole for
every current AND future off-whitelist `onNavigate` call, not just the one reproduced.
Also hiding the "How SARO Reasons" link specifically for demo sessions (cheap, prevents a
dead click rather than merely a silent one — belt-and-suspenders, not a substitute for the
AppShell-level guard).

Q2 (reviewer, REQUEST CHANGES round 1): `ComplianceHub.jsx`'s readiness-checklist checkbox
renders `disabled={!item.editable || unknown}` — `item.editable` comes from
`services/readiness_service.py` and has no read_only/role awareness, so it's `true` for a
demo session too. Clicking PUTs `/api/v1/compliance/readiness/{key}`, which
`require_write_persona` correctly 403s (read_only=True for any demo_viewer token per
`auth.py:183`) — but the frontend's `.catch()` replaces the whole Readiness Checklist card
with a `SectionError`, i.e. exactly the "disabled write path presented as available" +
"empty-by-error screen" the story exists to prevent. → **Disable client-side** for
`user?.read_only`, in addition to the existing `!item.editable || unknown` conditions.
`ComplianceHub` didn't even receive a `user` prop before this — added it (AppShell already
passes `user={user}` to every `PageComponent`, `ComplianceHub` just wasn't consuming it).
Also added an early-return guard in `toggleReadiness` itself (defense in depth, matches the
existing `if (!item.editable) return;` pattern) — belt-and-suspenders in case any future
code path calls it without going through the checkbox's `disabled` state.

Q3 (reviewer, MAJOR): the new contract test's `dashboard` tab entry asserted
`/api/v1/audits?limit=5` and `/api/v1/compliance-matrix/coverage` — endpoints Dashboard.jsx
does **not** call yet (that's STORY-413, unshipped). `implementation-notes.md` round 1
stated this as settled fact without checking, contradicting its own "verify, don't assume"
instruction applied correctly one paragraph earlier for Reports.jsx. → Strip both entries
from the `dashboard` census now; STORY-413's build will add them back to this same test
when it actually wires those tiles into Dashboard.jsx (noted inline so the two stories
don't talk past each other).

Q4 (reviewer, MINOR): `Sidebar.test.jsx`'s AC-5 suite covered 4 of the 6 personas the
implementer's own plan promised (`admin`/`super_admin` were only smoke-tested for the
switcher, not their full tab set). → add both.

## Plan
1. `frontend/src/components/AppShell.jsx` — import `DEMO_TABS`; `navigateNow` no-ops
   navigation outside the whitelist for `role === "demo_viewer"`.
2. `frontend/src/pages/TraceView.jsx` — hide the "How SARO Reasons ↗" action for
   `user?.role === "demo_viewer"`.
3. `frontend/src/pages/ComplianceHub.jsx` — accept `user` prop; checkbox
   `disabled={!item.editable || unknown || !!user?.read_only}`; `toggleReadiness` early-
   returns on `user?.read_only`.
4. `tests/regression/test_story_412_demo_tab_endpoint_census.py` — drop the two
   not-yet-real `dashboard` endpoints; add a case exercising the new AppShell guard
   isn't strictly backend-testable (it's client routing) — covered instead by a new
   frontend test in step 6.
5. Fix the false claim in this file (done — round 1's Discover section is gone, replaced by
   this round's honest Decision Log).
6. `frontend/src/components/Sidebar.test.jsx` (or a new `AppShell.test.jsx`) — pin the
   navigation-guard fix: simulate an off-whitelist `onNavigate` call for a demo user and
   assert the page does not change; add `admin`/`super_admin` to the AC-5 tab-set suite.
7. Re-run full gate suite; re-dispatch reviewer + security-auditor on the incremental diff.

## Deviations
None yet.
