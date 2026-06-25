# STORY-404: Audit-Event Emitter + SIEM Export

**Status:** done
**Screen/Area:** Governance Runtime — evidence-grade audit (Epic 14, Phase 1)
**Depends on:** STORY-401 (`policy_version` — carried as an event field). Contract consumed by STORY-402.

## Goal
Evidence-grade audit is the compliance product. SARO emits structured, tamper-evident events;
the **client SIEM is system-of-record**. New content-free event schema, source-side per-tenant
SHA-256 hash chaining, and JSON + Parquet export over a pluggable injected transport. Reuses
the existing `services/hash_chain_service.py` chaining approach (don't reinvent crypto) for the
governance-runtime schema. SARO does not build WORM storage in this pack.

## Acceptance Criteria (Given/When/Then)

- **AC-1 (schema, no raw content):** Given an audit event, When constructed, Then it carries
  `policy_version`, `trigger_mode`, decision + rationale, evidence pointers, actor, timestamp,
  `input_hash`, `output_hash`, latency, and fail-mode applied — and **no raw input/output content**.
  A well-formed event passes validation; one missing a required field is rejected.

- **AC-2 (per-tenant chains):** Given events for multiple tenants, When emitted, Then each event
  carries `tenant_id` and a hash of the prior event **within the same tenant's chain** (per-tenant
  head), so chains are isolated and appends serialize within a tenant without a global bottleneck;
  tampering or gaps are detectable by replaying that tenant's chain.

- **AC-3 (export):** Given a sequence of events, When exported, Then it produces valid structured
  JSON and Parquet, and the transport is an injected interface (a no-op/local sink is acceptable).

- **AC-4 (retention boundary):** Given the emitter, When events are emitted, Then SARO retains only
  per-tenant chain lineage (head hash + sequence) — events are emitted outward, not durably stored
  here as system-of-record.

- **AC-5 (verification):** Given a sequence of events, When the chain-verification utility runs, Then
  it confirms integrity over an intact sequence and flags a deliberately altered event; tenant A's
  events never enter tenant B's chain, and each tenant's chain verifies independently.

## Edge Cases
- Genesis event for a tenant has `prev_hash = None`.
- `verify_chain` over a mixed-tenant sequence raises (a chain is single-tenant by construction).
- Empty event list verifies as valid (nothing to check).
- Nullable fields (`latency_ms`, `fail_mode_applied`, `prev_hash`) round-trip through JSON + Parquet.

## Out of Scope
- Building WORM storage / long-term retention (client SIEM owns it).
- PrivateLink transport wiring (deployment-dependent — interface only; default no-op sink).
- Mapping STORY-402's `RoutingDecision` → `AuditEvent` (integration wiring, later).

## Non-Functional Requirements
- **Invariant guard (Epic 14):** deterministic crypto only — no external model/network call; audit
  events never embed raw content (pinned by a schema test).
- **Compliance (claims matrix):** "tamper-evident" / "hash-chain integrity verifiable" only — never
  "tamper-proof" or "immutable storage" (pinned by a source-scan test).
- Per-tenant locks: different tenants append concurrently; appends within a tenant serialize.

## Traceability
All tests in `tests/test_story404_audit_emitter.py`; impl in `services/audit_emitter.py`.

| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_event_has_required_fields`, `test_event_schema_carries_no_raw_content`, `test_validate_event_rejects_missing_required_field`, `test_input_output_hashing_is_deterministic_sha256` | services/audit_emitter.py |
| AC-2 | `test_per_tenant_chains_are_isolated`, `test_genesis_event_has_no_prev_hash` | services/audit_emitter.py |
| AC-3 | `test_export_json_is_schema_valid_and_content_free`, `test_export_parquet_is_schema_valid_and_content_free`, `test_injected_transport_receives_each_event`, `test_default_transport_is_a_safe_noop` | services/audit_emitter.py |
| AC-4 | `test_emitter_retains_only_chain_lineage_not_events` | services/audit_emitter.py |
| AC-5 | `test_intact_single_tenant_chain_verifies`, `test_altered_event_is_detected`, `test_verify_chain_rejects_mixed_tenants` | services/audit_emitter.py |
| Review fixes | `test_chain_seq_tamper_is_detected` (seal chain_seq), `test_prev_hash_tamper_is_detected`, `test_tail_truncation_detected_with_anchor` (head/count anchor), `test_concurrent_same_tenant_emits_stay_in_chain_order` (in-lock delivery), `test_parquet_schema_is_stable_across_batches` (explicit schema) | services/audit_emitter.py |
| Invariant | `test_no_external_model_or_network`, `test_no_overclaim_language` | services/audit_emitter.py |
