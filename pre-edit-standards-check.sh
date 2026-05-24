#!/bin/bash
# Hook: pre-edit-standards-check.sh
# Layer 03 — Guardrail Layer
# Runs before Claude edits any file. Enforces SARO codebase standards.
# If any check fails, Claude must surface it before proceeding.

set -e

FILE="$1"
echo "=== SARO PRE-EDIT STANDARDS CHECK ==="
echo "Target file: $FILE"

WARNINGS=()
BLOCKS=()

# --- BLOCK: Hardcoded secrets ---
if grep -qE "(JWT_SECRET|DATABASE_URL|REDIS_URL|ANTHROPIC_API_KEY)\s*=\s*['\"][^$\{]" "$FILE" 2>/dev/null; then
  BLOCKS+=("HARDCODED SECRET detected — use environment variables only")
fi

# --- BLOCK: Hardcoded version strings that don't match 8.0.0 ---
if grep -qE "(version|VERSION)\s*=\s*['\"](?!8\.0\.0)[0-9]" "$FILE" 2>/dev/null; then
  BLOCKS+=("VERSION DRIFT — only '8.0.0' is allowed as the version string")
fi

# --- BLOCK: time.sleep() in async context ---
if grep -q "time\.sleep(" "$FILE" 2>/dev/null && grep -q "async def\|await\|asyncio" "$FILE" 2>/dev/null; then
  BLOCKS+=("ASYNC VIOLATION — time.sleep() found in async context. Use await asyncio.sleep()")
fi

# --- WARN: Full file output pattern (Claude outputting entire files) ---
# (informational — caught in output review, not pre-edit)

# --- WARN: Missing @pytest.mark.requirement tag in test files ---
if [[ "$FILE" == tests/* ]] && grep -q "def test_" "$FILE" 2>/dev/null; then
  if ! grep -q "@pytest.mark.requirement" "$FILE" 2>/dev/null; then
    WARNINGS+=("TEST FILE missing @pytest.mark.requirement(\"FR/NFR-XXX\") tags")
  fi
fi

# --- WARN: New endpoint without auth check ---
if grep -qE "@(app|router)\.(get|post|put|delete|patch)\(" "$FILE" 2>/dev/null; then
  if ! grep -qE "(Depends|jwt|verify_token|get_current_user)" "$FILE" 2>/dev/null; then
    WARNINGS+=("NEW ENDPOINT detected — verify JWT auth dependency is applied")
  fi
fi

# --- Report ---
if [ ${#BLOCKS[@]} -gt 0 ]; then
  echo ""
  echo "❌ BLOCKED — fix before proceeding:"
  for b in "${BLOCKS[@]}"; do
    echo "  • $b"
  done
  echo ""
  exit 1
fi

if [ ${#WARNINGS[@]} -gt 0 ]; then
  echo ""
  echo "⚠️  WARNINGS — review before continuing:"
  for w in "${WARNINGS[@]}"; do
    echo "  • $w"
  done
fi

echo ""
echo "✅ Pre-edit check passed for: $FILE"
echo ""
exit 0
