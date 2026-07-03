#!/usr/bin/env bash
# verify.sh — SARO unified verification loop.
#
# Ported from ECC's `verification-loop` concept: a single gate that runs
# test -> lint -> typecheck -> security in one pass and prints a consolidated
# verdict. Mirrors the CI gates in CLAUDE.md ("Testing Requirements") so a
# green local run predicts a green pipeline.
#
# Gate classes:
#   REQUIRED  (pytest, ruff, security_scan) — failure fails the loop (exit 1)
#   ADVISORY  (mypy, pip-audit)             — reported, never block locally
#
# Rationale for advisory mypy/pip-audit: mypy.ini carries documented
# pre-existing suppressions (engine.py tech-debt) and pip-audit depends on
# network + advisory DB freshness; surfacing without blocking matches the
# quality-ratchet policy (never go backward, but don't wedge the loop on
# external state). Override with VERIFY_STRICT=1 to make advisory gates block.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STRICT="${VERIFY_STRICT:-0}"
fail=0
declare -a results

run_gate() { # run_gate <class REQUIRED|ADVISORY> <name> <cmd...>
  local class="$1" name="$2"; shift 2
  echo "── [$class] $name ──────────────────────────────"
  if "$@"; then
    results+=("PASS  [$class] $name")
  else
    if [ "$class" = REQUIRED ] || [ "$STRICT" = 1 ]; then
      results+=("FAIL  [$class] $name")
      fail=1
    else
      results+=("WARN  [$class] $name (advisory)")
    fi
  fi
  echo
}

have() { command -v "$1" >/dev/null 2>&1; }

echo "=========================================="
echo " SARO verification loop"
echo " strict=$STRICT  ($(git rev-parse --abbrev-ref HEAD 2>/dev/null))"
echo "=========================================="
echo

# 1. Tests (REQUIRED) — same invocation the Stop hook uses.
run_gate REQUIRED "pytest" python -m pytest tests/ -q --tb=short --no-header

# 2. Lint (REQUIRED).
if have ruff; then
  run_gate REQUIRED "ruff" ruff check .
else
  results+=("SKIP  ruff not installed")
fi

# 3. Typecheck (ADVISORY).
if have mypy; then
  run_gate ADVISORY "mypy" mypy .
else
  results+=("SKIP  mypy not installed")
fi

# 4. Security static scan (REQUIRED).
run_gate REQUIRED "security_scan" bash scripts/security_scan.sh

# 5. Dependency audit (ADVISORY — needs network).
if have pip-audit; then
  run_gate ADVISORY "pip-audit" pip-audit --requirement requirements.txt
else
  results+=("SKIP  pip-audit not installed")
fi

echo "=========================================="
echo " VERDICT"
echo "=========================================="
for r in "${results[@]}"; do echo "  $r"; done
echo
if [ "$fail" -ne 0 ]; then
  echo "RESULT: FAIL — fix REQUIRED gates before commit/PR."
  exit 1
fi
echo "RESULT: PASS — required gates green."
exit 0
