# STORY-401: Policy-Trigger Schema

**Status:** done
**Screen/Area:** Governance Runtime — policy configuration (Epic 14, Phase 1)
**Depends on:** STORY-400 (recon — see [STORY-400-recon-findings.md](STORY-400-recon-findings.md))

## Goal
Each governance policy can declare *how it fires* at runtime. Introduce a new tenant-scoped
`Policy` entity carrying per-policy trigger configuration (`trigger_mode`, `latency_budget_ms`,
`on_timeout`, `sample_rate`, `policy_version`), with validation that prevents silent
misconfiguration, a SQLAlchemy model + numbered SQL migration, and a Pydantic request/response
schema mirroring the same rules. This schema is the spine the STORY-402 router dispatches on.

Per STORY-400: **create** a new model (no policy entity exists); `TenantRiskConfig` is scoring-weight
tuning, not trigger config. Migration is a numbered `migrations/027_*.sql` (SARO has no Alembic).

## Acceptance Criteria (Given/When/Then)

- **AC-1 (fields):** Given the `Policy` model, When inspected, Then it carries `tenant_id` (UUID FK),
  a human name, `trigger_mode` enum {`block`,`mirror`,`sample`}, `latency_budget_ms` int (nullable),
  `on_timeout` enum {`open`,`closed`} (nullable), `sample_rate` float in [0,1] (nullable), and
  `policy_version` int (monotonic, starts at 1).

- **AC-2 (block validation):** Given `trigger_mode = block`, When `latency_budget_ms` OR `on_timeout`
  is missing, Then creation/update is rejected with a clear error naming the missing field(s).

- **AC-3 (sample validation):** Given `trigger_mode = sample`, When `sample_rate` is missing or
  outside [0,1], Then it is rejected with a clear error.

- **AC-4 (mirror validation):** Given `trigger_mode = mirror`, When any of `latency_budget_ms`,
  `on_timeout`, or `sample_rate` is set, Then it is rejected (mirror ignores them; rejecting prevents
  silent misconfig).

- **AC-5 (round-trip):** Given a valid config for each of the three modes, When persisted and reloaded,
  Then every field round-trips unchanged.

- **AC-6 (migration + backfill):** Given the `027_*.sql` migration applied to a DB with existing rows
  (if any seed policies exist), When migration completes, Then no policy is left in an invalid state;
  the safe default for any backfilled row is `mirror` with null budget/timeout/rate.

- **AC-7 (version increment):** Given an existing policy, When any trigger-config field changes via the
  update path, Then `policy_version` increments by exactly 1 deterministically and is queryable; an
  update that changes no trigger-config field does not bump the version.

- **AC-8 (tenant isolation):** Given two tenants A and B, When tenant A reads or writes policies, Then
  only tenant A's policies are visible/mutable; a cross-tenant read or write is denied. Matches the
  `tenant_id` FK + RLS (`current_setting('app.current_tenant')`) + app-layer-filter pattern from STORY-400.

- **AC-9 (Pydantic parity):** Given the request/response schemas, When the same invalid combinations
  from AC-2/3/4 are submitted, Then the Pydantic validator rejects them with the same semantics as the
  model layer (single source of validation truth, no drift).

## Edge Cases
- `sample_rate` exactly 0.0 and 1.0 are valid for `sample`.
- `latency_budget_ms` must be > 0 when required (reject 0 / negative).
- Concurrent updates: `policy_version` increment must not skip or collide (use the same row-update path).
- Empty/whitespace policy name rejected.
- Updating `trigger_mode` from `block` → `mirror` must clear/forbid the now-invalid budget/timeout fields.

## Out of Scope
- The router / any dispatch behavior (STORY-402).
- Per-request budget override (STORY-402 parameter).
- Surface-specific budgets / member-vs-internal logic (held — workshop-dependent).
- Any network call or model call — this is schema/config only.

## Non-Functional Requirements
- **Invariant guard:** schema/config only — assert no network or external-model call is introduced on
  any code path added by this story (Epic 14 locked invariant).
- Tenant isolation by construction (not retrofitted); cross-tenant access is a tested failure.
- Async-only FastAPI handlers, `/api/v1/` prefix, standardized error responses (api-conventions).
- Anti-overclaim (ADR-004 / compliance matrix): field docstrings describe configuration, make no
  guarantee claims.

## Traceability
All tests in `tests/test_story401_policy_schema.py` unless noted. Implementation in
`models.py` (`Policy`), `schemas.py` (`validate_trigger_config`, `PolicyCreate/Update/Out`),
`services/policy_service.py`, `migrations/027_create_policies.sql`.

| AC | Test(s) | Files |
|---|---|---|
| AC-1 fields | `test_block/mirror/sample_valid_config_accepted`, `test_roundtrip_each_mode` | models.py, schemas.py |
| AC-2 block needs budget+timeout | `test_block_missing_budget_or_timeout_rejected`, `test_block_nonpositive_budget_rejected` | schemas.py |
| AC-3 sample needs rate∈[0,1] | `test_sample_missing_or_out_of_range_rate_rejected`, `test_sample_rate_boundaries_valid` | schemas.py |
| AC-4 mirror rejects extras | `test_mirror_with_any_extra_rejected` | schemas.py |
| AC-5 round-trip per mode | `test_roundtrip_each_mode` | models.py, services/policy_service.py |
| AC-6 safe default mirror | `test_default_mode_is_mirror_with_nulls` | models.py, migrations/027 |
| AC-7 version increment | `test_version_increments_on_trigger_config_change`, `test_version_unchanged_on_non_trigger_change`, `test_version_unchanged_on_same_value_trigger_write` | services/policy_service.py |
| AC-8 tenant isolation | `test_cross_tenant_read_denied`, `test_cross_tenant_write_denied`; `tests/test_tenant_isolation.py` (Policy registered) | services/policy_service.py |
| AC-9 single validation source | `test_create_and_validator_share_one_function`, `test_update_invalid_merged_combo_rejected`, `test_mode_only_restate_uses_existing_fields`, `test_block_to_sample_with_rate_accepted` | schemas.py, services/policy_service.py |
| Edge/sec | `test_blank_name_rejected`, `test_name_over_max_length_rejected`, `test_block_budget_over_ceiling_rejected`, `test_explicit_null_name_rejected`, `test_switch_block_to_mirror_must_clear_budget` | schemas.py, services/policy_service.py |
| Invariant | `test_no_network_or_model_calls_in_policy_service` | services/policy_service.py |
