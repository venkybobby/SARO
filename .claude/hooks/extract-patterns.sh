#!/usr/bin/env bash
# extract-patterns.sh — continuous-learning Stop hook (ECC pattern, adapted).
#
# Non-blocking. Records a lightweight session-learning prompt into
# .claude/learnings/ when a session touched code in a way that *might* be worth
# distilling into a reusable skill. It never blocks the Stop event (always
# exits 0) and never mutates source — it only appends a markdown note that a
# human (or a follow-up /story) can promote into .claude/skills/.
#
# Heuristic: if this session created/modified files under engine.py, routers/,
# rule_packs/, services/, or added a new skill/agent, log a candidate.
set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 0

LEARN_DIR=".claude/learnings"
mkdir -p "$LEARN_DIR"

# Files changed vs HEAD (staged + unstaged + untracked tracked-candidates).
CHANGED=$(git status --porcelain 2>/dev/null | awk '{print $2}')
[ -z "$CHANGED" ] && exit 0

# Only consider substantive areas worth a reusable pattern.
CANDIDATES=$(echo "$CHANGED" | grep -E \
  '(^engine\.py|^routers/|^rule_packs/|^services/|^middleware/|^\.claude/skills/|^\.claude/agents/)' || true)
[ -z "$CANDIDATES" ] && exit 0

TS=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
LOG="$LEARN_DIR/candidates.md"

{
  echo "## Session $TS"
  echo
  echo "Touched areas that may contain a reusable pattern:"
  echo "$CANDIDATES" | sed 's/^/- /'
  echo
  echo "> Review prompt: did this session establish a repeatable technique"
  echo "> (a scoring idiom, a router/auth pattern, a test fixture, a rule-pack"
  echo "> validation step)? If yes, promote it into \`.claude/skills/\` —"
  echo "> ideally via \`/story\` so it ships with a regression test. If no,"
  echo "> leave this note; it is advisory only."
  echo
} >> "$LOG"

echo "[extract-patterns] Logged learning candidate -> $LOG (advisory, non-blocking)." >&2
exit 0
