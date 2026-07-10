# STORY-413 (round 2) — reviewer REQUEST CHANGES fix-up
Stage: standard

## Lifecycle
- [x] discover   — n/a, fixes are prescribed by the reviewer's concrete findings
- [x] shape      — skipped, no new decision
- [x] preview    — skipped
- [x] plan       — see below
- [x] build      (both fixes implemented and verified by fault injection; backend 1694
                   passed, frontend 200 passed, ruff clean)
- [x] verify     (verified the new mapping-correctness tests actually go red against the
                   reviewer's exact swapped-index bug, then confirmed green again on
                   correct code — not just "tests exist", confirmed they catch the thing
                   they claim to catch)
- [ ] sell       — n/a

## Decision Log

Q1 (reviewer, MAJOR): no test actually verifies `deriveKpis`' hand-edited array indices
point at the correct tile — the reviewer proved this by injecting a swapped-index bug
(`risk_officer`'s `criticalCount`/`remediationPct` writes swapped between `base[0]`/
`base[1]`) and reran the STORY-413 suite: all 14 tests still passed, because
`compliance_lead`'s test fixture's `audit_count` (12) coincidentally equals "Scans This
Week"'s static default (also 12), and no test asserted `risk_officer`'s "Critical Risks"/
"Remediation %" *values* at all — only presence-of-label was checked. → Change the
`compliance_lead` fixture's `audit_count` to a value that differs from every static
default (7, none of the remaining static tiles use 7), and add explicit value assertions
for `risk_officer`'s two live-overridden tiles, including asserting the *swapped* wrong
values are ABSENT — a test that only asserts the right value is present would still pass
if both right and wrong values happened to render somewhere on the page.

Q2 (reviewer, MINOR): `scripts/check_no_placeholder_kpi_tiles.py`'s per-line regex can be
defeated by wrapping `placeholder:` and `true` across two lines — reviewer confirmed this
directly against the real guard module (pointed `DASHBOARD` at a fixture with the split
pattern, `main()` returned 0). → add a whitespace-collapsed whole-file check alongside the
per-line loop (keeps per-line reporting for the common case, closes the multi-line gap).

Q3 (reviewer, MINOR, process): Deviations section said "None yet" despite two things
worth logging (FND-052 discovery mid-build; Q1's original round scope broadened AC-2 to
every persona, not just operator/demo). → filled in.

## Plan
1. `frontend/src/pages/Dashboard.test.jsx` — as-built: left the shared `SUMMARY.audit_count`
   at 12 (changing it globally would have created a NEW collision — `open_findings_count`
   is 7, and `screen.getByText` throws on multiple matches). Instead, each new mapping test
   uses a per-test `vi.stubGlobal` fetch override with a fixture value distinct from every
   static default AND every other number on that render (`compliance_lead`: 5;
   `ai_auditor`: 9), plus `within(kpiCard(label))`-scoped assertions so a legitimate value
   on a sibling tile can't cause a false pass/fail. `risk_officer` needed no override —
   its fixture (`critical_findings_count: 3`, `remediation_pct: 40`) already differs from
   both static defaults (12, "54%").
2. `scripts/check_no_placeholder_kpi_tiles.py` — whitespace-collapsed whole-file
   secondary check.
3. `tests/test_story413_no_placeholder_kpi_tiles.py` — extend the guard's own red/green
   self-test to cover the multi-line-split case specifically (this is what the reviewer
   actually reproduced — pin it, not just the fix).
4. Fill in `implementation-notes.md` round-1 Deviations (done — this file).
5. Re-run full gate suite; verify by re-injecting the reviewer's exact bug and confirming
   the new tests go red, then green again on correct code (done — round-2 reviewer
   independently reproduced this too and returned APPROVE).

## Deviations
1. FND-052 (operator's "Avg Score" tile, also fake, not in the story's named 8) was
   discovered mid-build and logged `status: open` rather than fixed — its correct
   semantics need a product decision. See round-1 notes / quality/findings.md.
2. Round-1 Decision Log Q1 broadened AC-2's literal "operator and demo sessions" wording
   to all 6 persona keys (`compliance_lead`, `risk_officer`, `ai_auditor`, `operator`,
   `admin`, `super_admin`) — a superset of the stated floor, not a narrowing. Reviewer
   flagged this as worth surfacing (not a violation): `Coverage %` sources tenant-agnostic
   regulatory reference data (per `compliance_matrix.py`'s own docstring), so showing it on
   every persona's dashboard is factually accurate everywhere, but is a product-framing
   choice that wasn't checked with a human. No code change from this round — noting it
   here for visibility rather than silently expanding scope further to "fix" a non-bug.
