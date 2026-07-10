# UC-5 demo-manifest reconciliation (post STORY-411)
Stage: trivial

## Lifecycle
- [x] discover   — skipped, trivial
- [x] shape      — skipped, trivial (diff pre-specified in sarouc5manifestfix.txt)
- [x] preview    — skipped, backend/config-only, no user-facing surface
- [x] plan       — skipped, trivial
- [ ] build
- [x] verify     — skipped, trivial (single-purpose 2-file mechanical diff)
- [ ] sell       — n/a

## Decision Log
N/A — trivial task, exact diff already reviewed and provided by the user
(scripts/demo_manifest.yaml: UC-5 `expected: planted_pending_rule` →
`fires`, updated notes/comments now that STORY-411 shipped
ENV-MODEL-ALLOWLIST-1; scripts/demo_corpus_builder.py: derive the
"planted but not firing" summary sentence from `summary.planted` instead
of a hardcoded UC-3/UC-4/UC-5 list).

## Deviations
None yet.
