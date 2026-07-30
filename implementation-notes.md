# Fix broken Trivy action pin blocking all PR merges
Stage: trivial

## Lifecycle
- [x] discover   (skipped — found while checking CI on PR #159; root-caused via job log +
      git ls-remote against upstream tags)
- [x] shape      (skipped — trivial, single mechanical fix)
- [ ] preview    (skipped — CI config only, no UI)
- [x] plan       (see below)
- [x] build
- [x] verify     (raw.githubusercontent.com confirms v0.36.0's setup-trivy is SHA-pinned;
      pushed and re-ran CI on PR #159)
- [ ] sell — n/a

## Plan

`.github/workflows/security-scans.yml:75` pinned `aquasecurity/trivy-action@0.28.0` (no
`v` prefix — didn't exist upstream). First fix (commit 82d5089) added the missing `v`,
which resolved the action itself but exposed a second, deeper break: `v0.28.0`'s own
composite action pins `aquasecurity/setup-trivy@v0.2.1` by tag, and that tag no longer
exists upstream (only v0.2.6+ do now) — so the job still failed one level down.

Verified via raw.githubusercontent.com that `trivy-action@v0.36.0` (latest) pins its
`setup-trivy` dependency by commit SHA instead of a floating tag, avoiding this exact
class of breakage going forward. Bumping `v0.28.0` -> `v0.36.0`.

This has been failing on `main` itself since at least 2026-07-27 (run 30243339282),
meaning every PR inherits a red "Trivy image scan (gating, critical/high)" check
regardless of its own changes — a repo-wide CI outage, not something this PR caused.

Separately, that same CI run surfaced a real, unrelated pip-audit failure (7 unwaived
starlette 0.52.1 CVEs, fixes in 1.0.1-1.3.1). That is a genuine dependency vulnerability,
not CI infra, and is NOT being fixed here — it needs its own scoped change with testing
and security-auditor review, flagged to the user separately.

## Deviations
- Planned as a 1-line prefix fix; actual fix required a version bump (v0.28.0 -> v0.36.0)
  once the prefix fix exposed a second broken pin one level down. Conservative option
  taken: bump to the newest tagged release rather than hunting for the oldest version
  that happens to still resolve, since newer = SHA-pinned internal dependency = less
  likely to rot the same way again.
