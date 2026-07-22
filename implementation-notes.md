# Fix red CI on main (ruff F401 + story-index shallow-clone + gitleaks)
Stage: trivial

main has been red since the pack-merge commit (9b7a9e7) — three CI failures,
none introduced by this session's cleanup commits. Fixing them so main goes
green. No product interface/behavior change; CI hygiene + one unused import.

## Lifecycle
- [x] trivial — skip to BUILD

## Decision Log
- Q: story-index gate reports every cited SHA "not reachable" in CI but passes
  locally — why? → the `regression-and-ratchet` job checks out SHALLOW
  (no fetch-depth), so `git merge-base --is-ancestor` can't see history. Fix =
  add `fetch-depth: 0` to that job's checkout (the lifecycle-guard job already
  does this). The gate logic is correct; the CI wiring was the defect.
- Q: ruff F401 in test_fnd_068 → remove the unused `FieldAvailability` import.
- Q: gitleaks 2 leaks → identify with the binary before deciding; real secret =
  remove, test-literal false positive = allowlist in .gitleaks.toml.

## Deviations
None.
