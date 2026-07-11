# STORY-412 (round 3) — reviewer REQUEST CHANGES fix-up #2
Stage: standard

## Lifecycle
- [x] discover   — n/a, fixes prescribed by the reviewer's concrete findings
- [x] shape      — skipped, no new decision
- [x] preview    — skipped
- [x] plan       — see below
- [x] build      (all 3 fixes implemented; new ComplianceHub test verified via fault
                   injection — reverted the fix, confirmed the test failed red, restored,
                   confirmed green; backend 1694 passed, frontend 201 passed, ruff clean)
- [x] verify     (findings ledger + manifest consistency tests green; FND-053/FND-054
                   registered and cross-checked against tests/test_story103_findings_
                   ledger_consistency.py)
- [ ] sell       — n/a

## Decision Log

Q1 (reviewer, blocking): round 1's ComplianceHub read-only-checkbox fix (a confirmed real
BLOCKER — a 403 that blanked the whole Readiness Checklist card) shipped with zero test
coverage — `ComplianceHub.test.jsx` was never touched by the round-2 fix commit. → add a
test asserting the checkbox is disabled and `toggleReadiness` no-ops for
`user.read_only`/`role === "demo_viewer"`, matching `docs/engineering-standards.md`'s
"no bug fix without a regression test" rule.

Q2 (reviewer, blocking): neither round-1 finding (both BLOCKER — the `navigateNow`
off-whitelist navigation gap, and the ComplianceHub checkbox) was logged as an `FND-###`
row with a `manifest.yaml` entry, unlike `FND-051` (an incidentally-discovered bug in the
same original commit, which did get the full treatment). Reviewer's precedent citation
(`FND-004`, `FND-007` register frontend component tests as pins) confirms this is the
established, expected pattern — not a new bar. → file FND-053 (navigateNow guard,
pinned by `AppShell.test.jsx`, already exists from round 2 — just needs registering) and
FND-054 (ComplianceHub read-only checkbox, pinned by the new test from Q1).

Q3 (reviewer, non-blocking but tracked): `test_story_412_demo_tab_endpoint_census.py`'s
`dashboard` endpoint list is stale — STORY-413 (landed after STORY-412 round 2) wired
`/api/v1/audits` and `/api/v1/compliance-matrix/coverage` into `Dashboard.jsx`, exactly as
round 2's own comment said it eventually would, but the census was never extended to match.
Reviewer independently verified both endpoints already return 200 for a real demo token
(no live bug), so this is a coverage gap, not an active defect. → extend the list back.

## Plan
1. `frontend/src/pages/ComplianceHub.test.jsx` — add a test rendering with
   `user={{role:"demo_viewer", read_only:true}}`, asserting the readiness checkbox is
   `disabled` and no PUT fires on click.
2. `quality/findings.md` + `tests/regression/manifest.yaml` — add FND-053
   (`AppShell.test.jsx` pin, already exists) and FND-054 (new `ComplianceHub.test.jsx`
   case from step 1), both `status: pinned`.
3. `tests/regression/test_story_412_demo_tab_endpoint_census.py` — add
   `/api/v1/audits?limit=200` and `/api/v1/compliance-matrix/coverage` back to the
   `dashboard` tab's endpoint list (STORY-413 now wires both).
4. Full gate suite; re-dispatch reviewer for round 4 (final).

## Deviations
None yet.
