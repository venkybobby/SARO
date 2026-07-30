# Phase-1 cleanup audit — repo hygiene follow-ups
Stage: trivial

## Lifecycle
- [x] discover   (skipped — well-trodden repo housekeeping, no new subsystem)
- [x] shape      (skipped — trivial)
- [ ] preview    (skipped — no UI, no user-facing surface)
- [x] plan       (see below)
- [x] build
- [x] verify     (tests/test_pt005_doc_register.py — 6 passed; git status/worktree
      list/ignored-check confirmed all 4 changes landed as intended)
- [ ] sell — n/a

## Plan

Four independent, low-risk repo-hygiene fixes identified during a premise-verification
audit against a pasted (non-SARO-specific) "phase-1-tech-spec.md" cleanup doc. None of
that doc's claims held (no saro-persona-rbac/, no committed .env, DB already sync-only).
These 4 are the real findings surfaced instead, confirmed against the repo directly:

1. `.claude/skills/deploy-railway/SKILL.md` describes Railway/Vercel topology that
   contradicts the frozen Fly.io+Supabase stack (`docs/ARCHITECTURE.md`, PT-012) and
   carries no SUPERSEDED marker, unlike every other legacy-infra doc in the repo
   (`deployment-context.md` etc., enforced by `tests/test_pt005_doc_register.py`).
   Fix: add a `[SUPERSEDED]` header matching the established pattern. DONE.

2. `Dockerfile` (Fly.io prod, referenced by fly.toml + deploy.yml + security-scans.yml)
   and `Dockerfile.api` (local docker-compose dev only) have no documentation
   distinguishing their purpose — an easy target for someone to "clean up" the wrong
   one later. Fix: add a one-line comment at the top of each.

3. Two merged, clean git worktrees under `.claude/worktrees/` (already gitignored,
   local-only) are leftover from completed sessions (PRs #153, #155, both already in
   `main` at b1ddfcb). Fix: `git worktree remove` both.

4. Untracked `demo-logs/`, `demo-logs-a/`, `demo-logs-b/` (synthetic Bedrock log
   fixtures, fake account 999888777666) and `.claude/data/` (local MCP plugin cache)
   are not covered by `.gitignore`, risking accidental `git add -A` inclusion. Fix:
   add gitignore entries (no deletion — user asked to gitignore, not prune).

No application code, engine/router/schema, or test-suite changes. Nothing here
touches a locked SARO invariant.

## Deviations
None yet.
