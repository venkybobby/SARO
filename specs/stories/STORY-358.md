# STORY-358: Extract the Observation Adapter Contract

**Status:** ready
**Screen/Area:** Backend — adapters / rule-pack engine input layer (Pack Epic 14)
**Ground truth:** Bedrock adapter (STORY-406..408) is the only adapter; its de-facto
contract is `adapters/bedrock/records.py` (`Envelope` dataclass, body-free) +
`AuditSubmission`. This story makes that contract explicit and versioned.

## Goal
An explicit, versioned `NormalizedInvocationRecord` (Pydantic) that every
observation adapter emits and the rule-pack engine consumes — so Azure/Vertex
adapters implement one schema instead of copying Bedrock code.

## Acceptance Criteria
- AC-1: Given the new `adapters/contract.py`, When imported, Then it defines
  `NormalizedInvocationRecord` (contract_version, adapter_id, model_id,
  timestamp, tenant_id, request/response metadata, tool/function calls, token
  counts, source-log provenance = hash + pointer/cursor) with docstring spec.
- AC-2: Given a Bedrock log line, When parsed, Then the adapter emits a
  `NormalizedInvocationRecord` (converter from `Envelope` + parse metadata);
  downstream envelope-rule evaluation consumes only normalized fields.
- AC-3: Given the deterministic synthetic Bedrock corpus (STORY-407 builder),
  When re-run through ingest, Then attestation/audit hashes are unchanged
  (no hash-format bump; converter is additive).
- AC-4: Given `docs/adapter-design.md`, Then the contract spec + field table +
  "how to add adapter #N" section exist.
- AC-5: INV-2 review note in PR: no field can carry body/payload content;
  provenance carries hash + pointer only.

## Edge Cases
- Missing token counts → None, never 0 (0 is a real count).
- Unknown provider fields → dropped at the adapter boundary, never passed through.

## Out of Scope
- Rewriting `Envelope`/`AuditSubmission` (kept; converter is additive — Decision D8).
- Azure/Vertex parsing (STORY-359/360).

## Non-Functional Requirements
- Frozen/immutable model (`model_config frozen`), fully typed; standard project rules.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
