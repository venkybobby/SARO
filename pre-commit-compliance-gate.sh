#!/bin/bash
# Hook: pre-commit-compliance-gate.sh
# Layer 03 — Guardrail Layer
# Runs before any git commit. Enforces compliance + deployment readiness.

set -e

echo "=== SARO PRE-COMMIT COMPLIANCE GATE ==="

BLOCKS=()
WARNINGS=()

# --- BLOCK: Hardcoded secrets anywhere in staged files ---
STAGED=$(git diff --cached --name-only 2>/dev/null || echo "")
for f in $STAGED; do
  if [ -f "$f" ]; then
    if grep -qE "(JWT_SECRET|DATABASE_URL|REDIS_URL|ANTHROPIC_API_KEY)\s*=\s*['\"][^$\{]" "$f" 2>/dev/null; then
      BLOCKS+=("HARDCODED SECRET in $f")
    fi
  fi
done

# --- BLOCK: Version drift ---
VERSION_FILES=("package.json" "pyproject.toml" "config/settings.py" "src/__init__.py")
for vf in "${VERSION_FILES[@]}"; do
  if [ -f "$vf" ]; then
    if grep -qE "version" "$vf" 2>/dev/null; then
      if ! grep -qE "8\.0\.0" "$vf" 2>/dev/null; then
        BLOCKS+=("VERSION DRIFT in $vf — must be 8.0.0")
      fi
    fi
  fi
done

# --- BLOCK: Failing tests (run unit tests only for speed) ---
if command -v pytest &>/dev/null; then
  if ! pytest tests/unit/ -q --tb=no -x 2>/dev/null; then
    BLOCKS+=("UNIT TESTS FAILING — fix before commit")
  fi
else
  WARNINGS+=("pytest not found — skipping unit test gate")
fi

# --- WARN: .env file staged ---
if echo "$STAGED" | grep -q "\.env"; then
  BLOCKS+=(".env FILE STAGED — remove from commit immediately")
fi

# --- WARN: DELETE /auth/logout endpoint still exists ---
if [ -f "src/api/auth.py" ]; then
  if ! grep -q "DELETE\|logout" "src/api/auth.py" 2>/dev/null; then
    WARNINGS+=("DELETE /auth/logout endpoint not found in auth.py — verify it exists")
  fi
fi

# --- WARN: PWA router registration ---
if [ -f "src/main.py" ]; then
  if ! grep -q "pwa\|PWA" "src/main.py" 2>/dev/null; then
    WARNINGS+=("PWA router may not be registered in main.py — verify at startup")
  fi
fi

# --- Report ---
if [ ${#BLOCKS[@]} -gt 0 ]; then
  echo ""
  echo "❌ COMMIT BLOCKED:"
  for b in "${BLOCKS[@]}"; do
    echo "  • $b"
  done
  echo ""
  exit 1
fi

if [ ${#WARNINGS[@]} -gt 0 ]; then
  echo ""
  echo "⚠️  WARNINGS (commit allowed, but review):"
  for w in "${WARNINGS[@]}"; do
    echo "  • $w"
  done
fi

echo ""
echo "✅ Compliance gate passed — commit allowed"
echo ""
exit 0
