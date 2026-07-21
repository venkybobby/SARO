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
| AC-1 | `test_version_has_a_single_source`, `test_main_does_not_re_hardcode_the_version`, `test_version_endpoint_returns_version_and_build_info`, `test_ui_footer_reads_the_version_endpoint_not_a_literal` | `_version.py`, `routers/version.py`, `main.py`, `frontend/src/components/AppShell.jsx` (VersionFooter) |
| AC-2 | `test_changelog_exists_and_follows_keep_a_changelog`, `test_changelog_gate_flags_a_release_pr_without_an_entry`, `test_changelog_gate_passes_when_a_bullet_is_added` | `CHANGELOG.md`, `scripts/check_changelog_entry.py`, `.github/workflows/release.yml` |
| AC-3 | `test_release_pipeline_runs_conformance_and_tests_before_deploy`, `test_release_pipeline_verifies_tag_matches_version_source`, `test_pipeline_does_not_duplicate_deploy_logic` | `.github/workflows/release.yml` |
| AC-4 | `test_rollback_doc_exists_with_the_migration_caveat`, `test_rollback_rehearsal_is_marked_human_open` | `docs/ops/release-rollback.md` |

## Design notes
- **One version source** (`_version.py`), read by the app, `/health`,
  `/api/v1/version`, and the UI footer. A test fails if `main.py` re-hardcodes
  it — bumping one place and not another is the drift this prevents.
- **`/api/v1/version` is public** — a customer's change-management process reads
  it without a credential. STORY-365's route-authz probe caught it and it was
  added to the justified allowlist (the probe working as designed).
- **Changelog gate enforces curation** — the drafter proposes from commits, the
  gate fails a release PR that adds no curated bullet.
- **Release pipeline reuses deploy + canary** rather than reimplementing them,
  and refuses a tag that disagrees with `_version.py` or has no CHANGELOG section.

## Human gate
**AC-4 [HUMAN — OPEN]:** the rollback is documented but the rehearsal on a
scratch deploy is unproven — needs Fly access. §4 of the doc has the checklist.
Same class as the DR rehearsal (STORY-370).
