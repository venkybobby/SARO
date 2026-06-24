# STORY-403: Edge-Redaction Reference Sidecar/SDK

**Status:** done
**Screen/Area:** Governance Runtime — edge redaction (Epic 14, Phase 1)
**Depends on:** none (independent). Built off `main`.

## Goal
SummitCare operates redaction; SARO ships a **reference component + policy-as-code** so the
logic isn't duplicated and SARO mostly never holds raw PHI. Deterministic Safe Harbor
(HIPAA-18) redaction driven by an **injected** data-classification catalog — no hardcoded
master list inside SARO. Emits per-batch SLIs (coverage, residual-identifier rate, drift vs a
rolling baseline). Expert Determination is a named hook that raises cleanly, not implemented.

Per STORY-400 recon, the shared synthetic-PHI fixture (`tests/fixtures/synthetic_phi.py`) is
built here first as a shared asset (never real member data).

## Acceptance Criteria (Given/When/Then)

- **AC-1 (HIPAA-18 via catalog):** Given a caller-supplied data-classification catalog covering the
  18 Safe Harbor classes, When text/records are redacted, Then every class's identifiers are
  redacted — and the 18-class list lives in the **catalog**, not baked into SARO.

- **AC-2 (catalog-injected):** Given the catalog is config-injected, When a field class is disabled,
  Then that class is no longer redacted; When a new field class is added, Then it is honored — both
  with no code change.

- **AC-3 (SLIs):** Given a batch, When redacted, Then the result emits redaction coverage, a
  residual-identifier rate (re-scan of the output), and drift vs a supplied rolling baseline.

- **AC-4 (de-identified egress, no retention):** Given an input, When redacted, Then the output is a
  de-identified copy suitable for egress and the caller's original is neither mutated nor retained by
  the component (it is stateless).

- **AC-5 (Expert Determination hook):** Given the Expert Determination extension point, When called,
  Then it raises `NotImplementedError` cleanly rather than silently passing data through.

## Edge Cases
- Empty catalog → nothing redacted (proves no baked master list).
- Disabled class still counts toward residual on the re-scan (a measured gap, not a blind spot).
- Structured field-kind redaction replaces the whole field value; regex-kind scans string values.
- No baseline supplied → drift is `None`, not a fabricated 0.

## Out of Scope
- The client's DLP integration.
- Expert Determination methodology (hook only).
- Any non-local model / NER via external API.

## Non-Functional Requirements
- **Invariant guard (Epic 14):** deterministic/rule-based only — no external API/model on any path
  (pinned). If local NER is added later it must stay local.
- **Anti-overclaim (ADR-004):** SLIs describe measured coverage only; no "guarantees removal" language
  (pinned by a source-scan test).
- Stateless component; original never retained.

## Traceability
All tests in `tests/test_story403_edge_redaction.py`; impl in `services/edge_redaction.py`; shared
fixture `tests/fixtures/synthetic_phi.py`.

| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_reference_catalog_enumerates_all_18_hipaa_categories`, `test_each_text_identifier_class_redacted`, `test_residual_rate_below_threshold_on_fixture` | services/edge_redaction.py, tests/fixtures/synthetic_phi.py |
| AC-2 | `test_empty_catalog_redacts_nothing`, `test_disabling_a_class_is_reflected_in_output`, `test_adding_a_new_class_is_honored` | services/edge_redaction.py |
| AC-3 | `test_sli_math_full_coverage`, `test_sli_math_partial_coverage_when_class_disabled`, `test_drift_none_without_baseline` | services/edge_redaction.py |
| AC-4 | `test_structured_field_redacted_wholesale`, `test_original_record_not_mutated` | services/edge_redaction.py |
| AC-5 | `test_expert_determination_raises_not_implemented` | services/edge_redaction.py |
| Review fixes | `test_overlapping_patterns_count_one_identifier` (no double-count), `test_disabled_field_class_counts_as_residual` (field-kind residual), `test_nested_record_phi_is_redacted_and_not_aliased` + `test_nonstring_scalar_field_not_aliased` (nested/aliasing), `test_no_signal_coverage_is_none_not_fabricated` (no-signal SLI), `test_catalog_validation_rejects_dangerous_patterns` (ReDoS guard) | services/edge_redaction.py |
| Invariant | `test_no_external_api_or_model_in_service`, `test_no_overclaim_language_in_service` | services/edge_redaction.py |
