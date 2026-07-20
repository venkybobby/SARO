# STORY-361: Cross-Adapter Conformance Suite

**Status:** ready
**Screen/Area:** Backend/CI — tests (Pack Epic 14)
**Depends on:** STORY-358..360

## Goal
One conformance suite runs every adapter against equivalent scenario corpora so
"supports Azure/Vertex" is a tested claim.

## Acceptance Criteria
- AC-1: Shared scenario set (happy path, missing fields, malformed record,
  tool-scope violation, incomplete observation) expressed once
  (parametrized), instantiated per adapter.
- AC-2: CI job runs the suite on every PR touching `adapters/**` or
  `rule_packs/observation/**`; failures block merge.
- AC-3: Conformance report artifact (per-adapter pass/fail matrix JSON +
  markdown) generated in CI.
- AC-4: Documented procedure for adding adapter #4 (what it must pass) in
  docs/adapter-design.md.

## Out of Scope
- Performance benchmarks per adapter (Locust story territory).

## Non-Functional Requirements
- Deterministic; no network; runs in the standard pytest gate too.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
