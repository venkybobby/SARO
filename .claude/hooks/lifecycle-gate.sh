#!/usr/bin/env bash
# PreToolUse gate (Edit|Write|MultiEdit): on standard tasks, source files may
# not be edited until implementation-notes.md exists, is fresh for the CURRENT
# task (not a committed leftover from a finished one), and contains a Decision
# Log. Trivial tasks (Stage: trivial) bypass the trivial/log checks but must
# still be fresh. Runs under Git Bash on Windows.

set -uo pipefail
INPUT=$(cat)

# Extract target file path from the hook's stdin JSON (no jq dependency).
FILE=$(printf '%s' "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*:[[:space:]]*"//; s/"$//')
# Windows portability: Claude Code passes backslash paths on Windows; normalize
# to forward slashes so the allow-list globs below (e.g. *.claude/*) match.
FILE=${FILE//\\//}

# Paths that are always allowed: notes, mocks, docs, plugin config, and tests.
# Tests are allowed pre-Decision-Log so a failing/regression test can be written
# first (TDD red step, and the /finding red-first flow). Globs are anchored to
# filename/dir boundaries so source files like `latest_config.py` don't slip
# through: pytest test_*.py / *_test.py and anything under a tests/ dir, plus
# frontend *.test.* / *.spec.* (vitest, Playwright).
case "$FILE" in
  ""|*implementation-notes.md|*.claude/*|*mock-*.html|*design-directions.html|*change-debrief.html|*.md|*buy-in*) exit 0 ;;
  */tests/*|tests/*|*/test_*.py|test_*.py|*_test.py|*.test.*|*.spec.*) exit 0 ;;
esac

NOTES="implementation-notes.md"

if [ ! -f "$NOTES" ]; then
  echo "GATE: no implementation-notes.md. Create it from the saro-lifecycle template (classify trivial/standard) before editing source." >&2
  exit 2
fi

# Staleness guard — a COMMITTED, unmodified notes file describes work that is
# already finished (its task ended with a commit that included the notes), so it
# must not satisfy the gate for a new or unrelated task. Require the notes to be
# fresh for the current task: untracked, staged, or modified vs HEAD. The
# saro-lifecycle skill overwrites implementation-notes.md at task start, which
# makes it dirty and clears this gate. Fail open outside a git work tree.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
   && git ls-files --error-unmatch "$NOTES" >/dev/null 2>&1 \
   && git diff --quiet -- "$NOTES" \
   && git diff --cached --quiet -- "$NOTES"; then
  echo "GATE: implementation-notes.md is committed and unmodified — it reflects a COMPLETED task, not the one you are starting. Recreate it from the saro-lifecycle template for the current task (reclassify trivial/standard, write a fresh Decision Log) before editing source. A stale notes file must not satisfy the gate for unrelated work." >&2
  exit 2
fi

grep -qi '^Stage:[[:space:]]*trivial' "$NOTES" && exit 0

if ! grep -q '^## Decision Log' "$NOTES" || ! sed -n '/^## Decision Log/,/^## /p' "$NOTES" | grep -q '[A-Za-z].*→\|Q:'; then
  echo "GATE: standard task but Decision Log is missing/empty in implementation-notes.md. Run the Stage 1b interview first (saro-lifecycle skill), record the log, then edit source." >&2
  exit 2
fi

exit 0
