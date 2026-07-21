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
| AC-1 | `test_adapter_conforms` (18 parametrized cases = 3 adapters × 6 scenarios), `test_every_adapter_answers_every_scenario` | `tests/conformance/harness.py`, `tests/conformance/providers.py` |
| AC-2 | CI job blocking on `adapters/**`, `rule_packs/observation/**` | `.github/workflows/conformance.yml` |
| AC-3 | `test_report_serializes_to_the_documented_schema`, `test_gaps_are_reported_as_gaps_not_passes` | `scripts/generate_conformance_report.py` → `quality/conformance/adapter-conformance.{json,md}` + job summary + upload |
| AC-4 | — (doc) | `docs/adapter-design.md` §5 "The conformance bar — what adapter #4 must pass" |

## Design note — three honest answers, not two
An adapter may answer a scenario `supported`, `conditional` (works only under a
stated precondition), or `not_supported` (the provider's logs cannot express
it). `conditional` exists because Azure/Vertex tool-scope detection works **only
on enriched exports** — rendering that as ✅ would tell a buyer it works on the
logs they already have. Reasons are mandatory (≥20 chars) and asserted; gaps and
conditionals are pinned by test so a new one is a reviewed change, not a quiet
regression.

## Current matrix (generated, not authored)
| Scenario | Bedrock | Azure OpenAI | Vertex AI |
|---|---|---|---|
| happy_path | ✅ | ✅ | ✅ |
| missing_fields | ✅ | ✅ | ✅ |
| malformed_record | ✅ | ✅ | ✅ |
| tool_scope_violation | ✅ | ◐ conditional | ◐ conditional |
| incomplete_observation | ✅ | ⚠️ n/a | ⚠️ n/a |
| tenancy_spoofing | ✅ | ✅ | ✅ |
