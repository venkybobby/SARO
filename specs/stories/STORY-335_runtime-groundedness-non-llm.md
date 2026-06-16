# STORY-335 — Runtime groundedness via non-LLM methods

**Epic:** GRC-3 — Output Audit Engine
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-305, STORY-308
**Supersedes:** the groundedness sub-check in STORY-309 (which proposed LLM-as-judge)

## Context
The groundedness check must run in the product path without calling a third-party hosted model API,
to preserve SARO's locked claim that it never calls external AI models at runtime. This story
replaces the LLM-as-judge approach with self-hosted / algorithmic methods.

## Definition in force
"External AI model" = a **third-party hosted model API** that transmits client data outside SARO.
A **self-hosted** model running inside SARO's infra does **not** violate the claim (data never leaves).

## Framework mapping
- NIST AI RMF: valid & reliable.
- ISO/IEC 42001: data quality.

## Scope (in)
Runtime groundedness scored from non-external-model signals over the output and its `retrieved_context`:
- **Entailment / NLI** using a self-hosted model (no external API call), OR
- **Retrieval-overlap** (claim ↔ source span matching), AND
- **Citation matching** (each factual claim traced to a supporting span).
- Emit a groundedness finding (supported / unsupported claims) for the orchestrator to score.

## Out of scope
- Any third-party hosted model API call in the product path (forbidden — guarded by STORY-336).
- Offline LLM-as-judge (moved to STORY-338, QA lab only).

## Acceptance criteria (binary)
- [ ] Groundedness runs with zero calls to any third-party hosted model API.
- [ ] An unsupported factual claim in a fixture is flagged; a supported claim passes.
- [ ] Each flagged claim references the source span it failed to match.
- [ ] If a self-hosted model is used, it runs in SARO infra and is recorded as an internal dependency.

## Technical notes
- Prefer a small self-hosted NLI model + retrieval-overlap; keep the method inspectable for auditors.
- Method choice resolves OPEN-VAL-1 in the validation strategy.

## Test requirements
- [ ] Unit: supported vs unsupported claim fixtures.
- [ ] Guard test: assert no external model SDK/endpoint is invoked on this path (links to STORY-336).

## Definition of done
Groundedness operates with no external model call, flags unsupported claims with source traceability, tests green.
