#!/usr/bin/env bash
# Stop gate: on a 3+ file change, (a) implementation-notes.md must have been
# updated this session, and (b) the verify stage must be done or explicitly
# offered. Trivial tasks bypass.

set -uo pipefail
NOTES="implementation-notes.md"

[ -f "$NOTES" ] && grep -qi '^Stage:[[:space:]]*trivial' "$NOTES" && exit 0

# Count only tracked modifications / staged changes — NOT untracked files.
# Ambient build artifacts, downloads, and pre-existing clutter must not force a
# notes update; new source files count once staged. This matches the CI
# lifecycle-guard, which measures the committed diff (untracked files are
# invisible to it). NOTES_TOUCHED still counts an untracked, freshly-created
# notes file so a first-task notes.md satisfies the gate.
CHANGED=$(git status --porcelain 2>/dev/null | grep -v '^??' | grep -cv 'implementation-notes\.md' || true)
[ "${CHANGED:-0}" -lt 3 ] && exit 0

NOTES_TOUCHED=$(git status --porcelain 2>/dev/null | grep -c 'implementation-notes\.md' || true)
if [ "${NOTES_TOUCHED:-0}" -eq 0 ]; then
  echo "GATE: ${CHANGED} files changed but implementation-notes.md not updated. Update it (Deviations: None if none) and check off completed lifecycle stages." >&2
  exit 2
fi

if [ -f "$NOTES" ] && grep -q '^\- \[ \] verify' "$NOTES"; then
  echo "GATE: multi-file change with verify stage unchecked. Generate change-debrief.html (Stage 5, saro-lifecycle skill) or mark verify as skipped with a reason, then finish." >&2
  exit 2
fi

exit 0
