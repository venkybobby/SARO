# Fix: stale notes file can satisfy the lifecycle gate
Stage: standard

Follow-up to the saro-lifecycle install (#105). The PreToolUse gate honored any
implementation-notes.md that merely existed and carried a Decision Log — with no
binding to the current task. So a committed notes file left over from a finished
task (e.g. this repo's own install notes, now on main) kept the gate satisfied
for unrelated later work. Closing that hole.

## Lifecycle
- [x] discover  — skipped: problem and file are known (lifecycle-gate.sh).
- [x] shape     — skipped: fully specified (the footgun the user named).
- [x] preview   — skipped: no user-facing surface.
- [x] plan      — staleness = git freshness of the notes file (see Decision Log).
- [x] build     — gate.sh staleness guard + SKILL.md recreate-at-start note.
- [x] verify    — 9-case isolated-git-repo matrix, all pass (committed-clean
                  blocks incl. trivial; dirty/staged/untracked allow; allowlist
                  + Windows backslash unaffected; non-git fails open).
- [x] sell      — n/a.

## Decision Log
- Q: How should the gate define a "stale" notes file?
  → A: git state — block source edits when implementation-notes.md is tracked
  AND unmodified vs HEAD (no unstaged and no staged diff). Rejected alternatives:
  mtime (fragile across git checkout/pull), and session-id binding (misses two
  unrelated tasks within one session; needs a sidecar + PostToolUse stamp).
  → consequence: finishing a task = committing its notes; starting the next =
  the skill overwrites the file (dirty), which is the freshness signal. No new
  hook, no sidecar, aligns with the CI guard's committed-diff semantics.
- Q: Should the check run before or after the trivial bypass?
  → A: before. A committed `Stage: trivial` leftover was the sharpest form of the
  bug; staleness is now checked first so stale-trivial no longer bypasses.

## Deviations
- Known residual gap (accepted, documented): if you start an unrelated task
  WITHOUT committing the previous one, its still-dirty notes look fresh, so the
  gate won't auto-flag them — recreate notes manually in that case. The common
  path (previous task committed/merged, as here) is fully covered. Fail-open
  outside a git work tree is deliberate.
