# STORY-367: Dependency, Container, and IaC Scanning in CI

**Status:** ready
**Screen/Area:** CI (Pack Epic 15)
**Ground truth:** `scripts/security_scan.sh` (static OWASP/PII patterns) +
`quality-gates.yml` exist; pip-audit referenced in CLAUDE.md testing table but
verify wiring. No osv-scanner, no container scan, no weekly schedule beyond
security-evidence-weekly.

## Goal
Vulnerability scanning is a CI gate with severity thresholds and a weekly
scheduled run — findings triaged in the landing PR, no red gate landed.

## Acceptance Criteria
- AC-1: pip-audit (backend) + npm audit / osv-scanner (frontend) wired into CI,
  fail on critical/high, documented waiver process (inline allowlist file with
  expiry + reason per waiver).
- AC-2: Container image scan (trivy) on the Dockerfile(s) with same gating.
- AC-3: Weekly scheduled run (cron) in addition to on-PR.
- AC-4: Current findings triaged in this story's PR — waivers or fixes, gate lands green.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
