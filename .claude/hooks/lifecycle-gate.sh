#!/usr/bin/env bash
# PreToolUse gate (Edit|Write|MultiEdit): on standard tasks, source files may
# not be edited until implementation-notes.md exists and contains a Decision
# Log. Trivial tasks (Stage: trivial) bypass everything.
# Runs under Git Bash on Windows.

set -uo pipefail
INPUT=$(cat)

# Extract target file path from the hook's stdin JSON (no jq dependency).
FILE=$(printf '%s' "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*:[[:space:]]*"//; s/"$//')
# Windows portability: Claude Code passes backslash paths on Windows; normalize
# to forward slashes so the allow-list globs below (e.g. *.claude/*) match.
FILE=${FILE//\\//}

# Paths that are always allowed: notes, mocks, docs, plugin config, tests-as-spec.
case "$FILE" in
  ""|*implementation-notes.md|*.claude/*|*mock-*.html|*design-directions.html|*change-debrief.html|*.md|*buy-in*) exit 0 ;;
esac

NOTES="implementation-notes.md"

if [ ! -f "$NOTES" ]; then
  echo "GATE: no implementation-notes.md. Create it from the saro-lifecycle template (classify trivial/standard) before editing source." >&2
  exit 2
fi

grep -qi '^Stage:[[:space:]]*trivial' "$NOTES" && exit 0

if ! grep -q '^## Decision Log' "$NOTES" || ! sed -n '/^## Decision Log/,/^## /p' "$NOTES" | grep -q '[A-Za-z].*→\|Q:'; then
  echo "GATE: standard task but Decision Log is missing/empty in implementation-notes.md. Run the Stage 1b interview first (saro-lifecycle skill), record the log, then edit source." >&2
  exit 2
fi

exit 0
