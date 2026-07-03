#!/usr/bin/env bash
# security_scan.sh — AgentShield-style OWASP + PII pattern scan for SARO.
#
# Ported from ECC's `security-scan` skill concept and adapted to SARO's
# compliance surface. This is a *static pattern* layer that augments (does not
# replace) the `security-auditor` agent and the `security-audit` skill.
#
# Scope: backend Python only. Excludes tests, vendored data frameworks, and
# generated artifacts. Read-only — never mutates the tree.
#
# Exit codes:
#   0  no high-severity findings
#   1  one or more high-severity findings (CI-blocking)
# Advisory (medium/low) findings are printed but do not fail the scan.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Files to scan: tracked python, excluding tests and the separate data framework.
mapfile -t FILES < <(git ls-files '*.py' \
  | grep -vE '^(tests/|saro-data-framework/|scripts/security_scan)' || true)

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "security_scan: no python files to scan"
  exit 0
fi

high=0
med=0

flag_high() { echo "  [HIGH] $1"; high=$((high + 1)); }
flag_med()  { echo "  [MED ] $1"; med=$((med + 1)); }

scan() { # scan <severity> <regex> <human label>
  local sev="$1" re="$2" label="$3" hits
  hits=$(grep -rnEI "$re" "${FILES[@]}" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    echo "$label:"
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      if [ "$sev" = high ]; then flag_high "$line"; else flag_med "$line"; fi
    done <<< "$hits"
  fi
}

echo "=== SARO security_scan (OWASP + PII static patterns) ==="
echo "scanning ${#FILES[@]} python files"
echo

# --- A02 Cryptographic failures: weak hashes for security purposes ----------
scan high  'hashlib\.(md5|sha1)\(' \
  "A02 weak hash (use SHA-256; TRACE chain requires it)"

# --- A03 Injection ----------------------------------------------------------
scan high  'subprocess\.(call|run|Popen)\(.*shell\s*=\s*True' \
  "A03 command injection (shell=True)"
scan high  '(execute|executemany)\(\s*f["'\'']' \
  "A03 SQL injection (f-string into execute)"
scan high  '\beval\(|\bexec\(' \
  "A03 dynamic code execution (eval/exec)"

# --- A05 Misconfiguration ---------------------------------------------------
scan high  'verify\s*=\s*False' \
  "A05 TLS verification disabled"
scan med   'debug\s*=\s*True' \
  "A05 debug enabled"

# --- A07 Hardcoded secrets (FND-003 history) --------------------------------
scan high  '(password|passwd|secret|api_key|apikey|token)\s*=\s*["'\''][^"'\'' ]{6,}["'\'']' \
  "A07 possible hardcoded secret"
scan high  '(sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})' \
  "A07 provider credential pattern"

# --- A09 Logging PII / secrets ----------------------------------------------
scan med   '(log(ger)?|print)\([^)]*(password|api_key|token|ssn|email)' \
  "A09 possible PII/secret in logs (verify _redact_pii applied)"

echo
echo "=== summary: ${high} high, ${med} advisory ==="
if [ "$high" -gt 0 ]; then
  echo "FAIL: high-severity patterns present. Triage each (false positives -> log an FND/inline waiver)."
  exit 1
fi
echo "PASS: no high-severity static patterns."
exit 0
