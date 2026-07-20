# STORY-375: Versioned Release Process

**Status:** ready
**Screen/Area:** CI + docs (Pack Epic 17)
**Ground truth:** app.version exists (health endpoint returns it);
changelog-drafter.yml workflow exists. No CHANGELOG.md gate, no tagged-release
pipeline, no rollback rehearsal.

## Goal
Releases are versioned with changelogs and a documented rollback — customers can
answer their own change-management obligations.

## Acceptance Criteria
- AC-1: SemVer adopted; version surfaced in UI footer + `GET /health` (exists) +
  `GET /api/v1/version`.
- AC-2: CHANGELOG.md maintained (Keep-a-Changelog format); CI enforces a
  changelog entry on release PRs (label- or path-triggered check).
- AC-3: Tagged-release pipeline: tag push → build → conformance suite
  (STORY-361) + pytest gate → deploy → post-deploy canary (STORY-368).
- AC-4: Rollback procedure documented (`docs/ops/release-rollback.md`);
  rehearsal on a scratch deploy marked **[HUMAN — OPEN]** (needs Fly access).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
