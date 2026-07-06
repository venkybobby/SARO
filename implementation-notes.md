# Install saro-lifecycle pack
Stage: standard

Config/tooling install: the saro-lifecycle skill, two hooks, the /build +
/story + /finding entry points, CLAUDE.md + AGENTS.md norms, and the CI
lifecycle-guard job. No runtime code, interface, data-model, or user-facing
change — but it spans 10 files, so it is tracked as a standard task (not
trivial, which the skill reserves for single-file changes).

## Lifecycle
- [x] discover  — skipped: pack contents fully specified by its own README.
- [x] shape     — skipped: change is fully specified; no design space.
- [x] preview   — skipped: no user-facing surface.
- [x] plan      — file-by-file install map agreed before edits.
- [x] build     — files placed; settings.json and quality-gates.yml merged
                  (existing hooks/jobs preserved), not overwritten.
- [x] verify    — config-only: hooks smoke-tested manually across forward- and
                  back-slash paths and with/without a notes file (see
                  Deviations). No change-debrief.html — no runtime behavior to
                  debrief.
- [x] sell      — n/a (not design-partner-facing).

## Decision Log
- Q: Keep AGENTS.md in-repo, or treat Codex as fully out of scope?
  → A: keep AGENTS.md (repo-level norms file, part of the pack); skip only the
  out-of-repo ~/.codex/prompts kickstart.
  → consequence: Claude Code and Codex share one lifecycle source of truth.
- Q: Append a lifecycle block to finding.md (README calls it optional)?
  → A: yes, tailored to findings.
  → consequence: findings run trivial-by-default, escalate to standard at 3+
  files / interface / invariant changes.
- Q: Commit the transient implementation-notes.md?
  → A: yes for THIS PR, so the new lifecycle-guard job passes on its own
  install; future feature PRs still author their own notes.

## Deviations
- Windows-path fix to the shipped lifecycle-gate.sh. Claude Code passes
  backslash file_paths on Windows, so the `*.claude/*` allow-list glob did not
  match and the gate blocked legitimate `.claude/` edits. Conservative option
  taken: a one-line separator normalization (`FILE=${FILE//\\//}`). Aggressive
  alternative not taken: rewriting the whole allow-list as a slash-agnostic
  regex. This repo is Windows-primary, so the fix is load-bearing here.
- Untracked-file fix to the shipped lifecycle-stop.sh. The stop gate counted
  untracked files via `git status --porcelain`, so this repo's pre-existing
  untracked clutter (18 files: docs/evf/*, coverage.json, etc.) tripped the
  3+-file gate every turn once real work was committed — and it conflicted with
  the CI guard, which requires notes committed (invisible to the local hook).
  Fix: count only tracked modifications / staged changes, aligning the local
  hook with the CI guard's committed-diff semantics. Conservative: NOTES_TOUCHED
  still counts an untracked new notes file so first-task usage is unaffected.
