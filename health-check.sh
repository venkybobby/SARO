#!/bin/bash
# tools/scripts/health-check.sh
# Quick SARO platform health check — run before any demo or commit

set -e

BASE_URL="${SARO_URL:-http://localhost:8000}"

echo "=== SARO Health Check ==="
echo "Target: $BASE_URL"
echo ""

# Health endpoint
HEALTH=$(curl -s "$BASE_URL/health" 2>/dev/null || echo '{"error": "unreachable"}')
echo "Health: $HEALTH"

VERSION=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','unknown'))" 2>/dev/null || echo "parse_error")
STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "parse_error")

echo ""
if [ "$VERSION" = "8.0.0" ] && [ "$STATUS" = "healthy" ]; then
  echo "✅ Version: $VERSION"
  echo "✅ Status: $STATUS"
else
  echo "❌ Version: $VERSION (expected 8.0.0)"
  echo "❌ Status: $STATUS (expected healthy)"
fi

# Auth endpoint
echo ""
echo "Checking auth endpoint..."
AUTH=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/auth/logout" -X DELETE 2>/dev/null || echo "000")
if [ "$AUTH" = "401" ] || [ "$AUTH" = "422" ]; then
  echo "✅ DELETE /auth/logout exists (returned $AUTH without token — expected)"
elif [ "$AUTH" = "000" ]; then
  echo "⚠️  DELETE /auth/logout unreachable"
else
  echo "⚠️  DELETE /auth/logout returned $AUTH — verify"
fi

echo ""
echo "=== Done ==="
