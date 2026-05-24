#!/bin/bash
# Hook: post-edit-version-check.sh
# Layer 03 — Guardrail Layer
# Runs after Claude edits a file. Catches version drift immediately.

FILE="$1"
echo "=== SARO POST-EDIT VERSION CHECK: $FILE ==="

EXPECTED_VERSION="8.0.0"

# Version-bearing files that must all read 8.0.0
VERSION_FILES=(
  "package.json"
  "pyproject.toml"
  "config/settings.py"
  "src/__init__.py"
  "src/api/__init__.py"
  "README.md"
  "docker-compose.yml"
  "koyeb.yaml"
)

DRIFT=()
for vf in "${VERSION_FILES[@]}"; do
  if [ -f "$vf" ] && grep -q "version" "$vf" 2>/dev/null; then
    if ! grep -q "$EXPECTED_VERSION" "$vf" 2>/dev/null; then
      DRIFT+=("$vf")
    fi
  fi
done

if [ ${#DRIFT[@]} -gt 0 ]; then
  echo ""
  echo "⚠️  VERSION DRIFT DETECTED in:"
  for d in "${DRIFT[@]}"; do
    echo "  • $d (expected $EXPECTED_VERSION)"
  done
  echo ""
  echo "Fix version strings before committing."
else
  echo "✅ Version check clean — all files at $EXPECTED_VERSION"
fi

exit 0
