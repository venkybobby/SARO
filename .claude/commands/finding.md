---
description: Log a new finding and pin it with a regression test
argument-hint: <short description of the bug/finding>
---

Process a new finding: "$ARGUMENTS"

1. Assign the next FND-### ID (read quality/findings.md for the highest existing).
2. Root-cause it (5-whys, briefly). Add a row to quality/findings.md.
3. Write `tests/regression/test_fnd_###_<slug>.py` that REPRODUCES the failure —
   run it and show it failing (red) before any fix.
4. Implement the minimal fix. Show the regression test passing (green).
5. Add the manifest entry in tests/regression/manifest.yaml with status `pinned`.
6. Run `pytest tests/regression -q` (full) plus gates 1–4 from /story.
7. End with FILES CHANGED / NOT TOUCHED / CONCERNS.

---

## Lifecycle (mandatory)

This finding runs under the saro-lifecycle skill. Most findings are
**trivial** (single-file fix + its regression test): write `Stage: trivial`
atop implementation-notes.md and steps 1–7 above ARE the build stage — the
gates stand down.

Treat a finding as **standard** when the fix spans 3+ files, changes an
interface or data model, or touches a locked SARO invariant. Then:

1. Create implementation-notes.md from the lifecycle template before editing
   any source file (the gate hook enforces this).
2. The root-cause note (step 2) and the pinning regression test (step 3) double
   as the Stage 1b decision record — capture the `root-cause → fix` decision in
   the Decision Log so the gate is satisfied.
3. Walk PLAN → BUILD → VERIFY; a standard-sized fix triggers Stage 5 (produce
   change-debrief.html, or mark verify skipped with a reason).
4. DISCOVER / SHAPE / PREVIEW / SELL stay skipped for findings unless the fix
   reopens a design question or I ask.
