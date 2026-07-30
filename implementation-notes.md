# Fix broken Trivy action pin blocking all PR merges
Stage: trivial

## Lifecycle
- [x] discover   (skipped — found while checking CI on PR #159; root-caused via job log +
      git ls-remote against upstream tags)
- [x] shape      (skipped — trivial, single mechanical fix)
- [ ] preview    (skipped — CI config only, no UI)
- [x] plan       (see below)
- [x] build
- [x] verify     (git ls-remote confirms v0.28.0 resolves; pushed and re-ran CI on PR #159)
- [ ] sell — n/a

## Plan

`.github/workflows/security-scans.yml:75` pins `aquasecurity/trivy-action@0.28.0` (no `v`
prefix). Confirmed via `git ls-remote --tags` against the upstream repo that only
`v0.28.0` exists as a tag — `0.28.0` never did. This has been failing on `main` itself
since at least 2026-07-27 (run 30243339282), meaning every PR inherits a red "Trivy image
scan (gating, critical/high)" check regardless of its own changes.

Fix: add the missing `v` prefix — same pinned version, just resolvable. One-line,
mechanical, no behavior change to what gets scanned.

Separately, that same CI run surfaced a real, unrelated pip-audit failure (7 unwaived
starlette 0.52.1 CVEs, fixes in 1.0.1-1.3.1). That is a genuine dependency vulnerability,
not CI infra, and is NOT being fixed here — it needs its own scoped change with testing
and security-auditor review, flagged to the user separately.

## Deviations
None yet.
