# STORY-363: Secrets Management Baseline + Repo History Remediation (P0)

**Status:** done — artifacts + CI gate live; AC-4/AC-5 **OPEN [HUMAN]** (rotation, history decision)
**Screen/Area:** Security / CI (Pack Epic 15)
**Ground truth:** Seed scripts are already env-var-only (#119); the historic
hardcoded-secret exposure is FND-003. No secret-scanning CI gate exists yet.

## Goal
Zero secrets in the repo going forward (CI-enforced), a documented runtime-secret
inventory with rotation ownership, and an explicit human decision on history
remediation.

## Acceptance Criteria
- AC-1: Secrets inventory table committed (secret → store (Fly secrets /
  Supabase vault / GitHub Actions secrets) → rotation owner → cadence) in
  `docs/security/secrets-runbook.md`.
- AC-2: Secret-scanning (gitleaks) in CI on every PR; a seeded test secret in a
  fixture proves the gate fails (test asserts the rule catches the pattern).
- AC-3: Rotation runbook committed (who, how, cadence, verification step
  "old credential dead against prod").
- AC-4 **[HUMAN — OPEN]**: exposed credential rotated in prod; old credential
  verified dead. (Requires Fly/Supabase access — operator action.)
- AC-5 **[HUMAN — OPEN]**: history scrub vs repo re-cut decision recorded with
  tradeoff (public forks/clones mean rotation is the real control).

## Out of Scope
- Executing any history rewrite (destructive to forks — never without explicit go-ahead).

## Non-Functional Requirements
- Gitleaks config allowlists test fixtures explicitly (no blanket test-dir exemption).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | — (doc) | docs/security/secrets-runbook.md §1 |
| AC-2 | tests/test_story363_secret_scanning.py + CI self-test step | .gitleaks.toml, .github/workflows/ci.yml (secret-scan job), tests/fixtures/gitleaks_canary/ |
| AC-3 | — (doc) | docs/security/secrets-runbook.md §3 |
| AC-4 | OPEN [HUMAN] | runbook §4 checklist |
| AC-5 | OPEN [HUMAN] | runbook §5 (recommendation: rotate-only now) |
