# FND-074 — no CI workflow runs vitest (frontend regression pins unguarded)

Stage: standard

## Lifecycle
- [x] discover   (skipped — CI workflows are well-trodden: FND-070/071/072/084 all touched them)
- [x] shape      (skipped — fix fully specified by owner instruction; decisions logged below)
- [x] preview    (skipped — CI-only, no user-facing surface)
- [x] plan
- [x] build      (implemented; red-first 2/3 pre-fix → 5/5 post-fix incl. lint-step pins)
- [x] verify     (reviewer APPROVE, 3 minors addressed in-PR; change-debrief.html; full regression + verify.sh green)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| FND-074 ledger row, status open | yes | quality/findings.md:87 (on origin/main @526ab3a via PR #128) |
| FND-074 manifest row, status open, test path pre-declared | yes | tests/regression/manifest.yaml:355-359 |
| deploy.yml frontend job = npm ci + build only, no vitest | yes | .github/workflows/deploy.yml:67-88 |
| ci.yml runs pytest only (no node/vitest anywhere) | yes | .github/workflows/ci.yml (grep vitest → no hits) |
| frontend vitest pins exist (FND-021/022/023/029/031/052/053/054/073) | yes | frontend/src/**/*.test.jsx — 10+ files incl. pages/Remediation.test.jsx |
| frontend `test`/`lint` scripts + vitest devDependency | yes | frontend/package.json:10-11 ("test": "vitest run", "lint": "eslint ."), vitest ^4.1.10 |
| CI-config pin precedent | yes | tests/regression/test_fnd_084_ruff_pinned_in_ci.py |

Note: at session start FND-074 did NOT exist on origin/main (tip c44dc68) — it
landed mid-session when PR #128 (STORY-TAB-001) merged. Branch re-based onto
the new tip 526ab3a before any work; premise re-verified there.

## Decision Log
- Q: Where should the vitest gate live? → A (owner-specified): both `deploy.yml` frontend job (`npx vitest run` after `npm ci`, before `npm run build`, working-directory frontend via job default) AND a new `frontend-test` job in `ci.yml` so PR CI gates on it, not just deploy. Consequence: PRs fail fast on frontend regressions; deploy refuses to ship red frontend.
- Q: How is a CI-config finding pinned? → A (owner-specified, precedent FND-084): pytest `tests/regression/test_fnd_074_vitest_ci_gate.py` parses the workflow YAML and asserts the vitest step exists, is ordered npm ci → vitest → build, and that ci.yml's gate runs on pull_request. Red-first against current main.
- Q: Include `npm run lint`? → A: only if `eslint .` passes locally in the worktree; a born-red gate is worse than no gate. Outcome: exit 0 (0 errors, 194 warnings) → wired into both workflows and pinned in the test (reviewer minor #2).
- Q: Branch base? → A (owner-specified): off origin/main (`fix/fnd-074-vitest-ci-gate`); commit `fix(ci): FND-074 ...`; findings.md + manifest.yaml flipped open → pinned in the same commit (FM-4 control).

## Deviations
- Reviewer minor #1 accepted as a sanctioned 1-line drive-by: deploy.yml's
  pre-existing `cache-dependency-path: frontend/package.json` corrected to
  `frontend/package-lock.json` alongside the new ci.yml job (cache-key
  correctness only; `npm ci` semantics unchanged).
- Vitest runs twice per PR (deploy.yml `frontend` + ci.yml `frontend-test`) —
  owner-specified defense-in-depth, reviewer observation #4, accepted cost.
