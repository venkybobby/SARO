# STORY-359: Azure OpenAI Observation Adapter (Adapter #2)

**Status:** ready
**Screen/Area:** Backend — adapters (Pack Epic 14)
**Depends on:** STORY-358 (contract), PREREQ-RP (genesis observation rule-packs)

## Goal
SARO ingests Azure OpenAI Diagnostic Settings log exports (customer-owned
blob/JSON, mirror-async) and produces the same normalized records, rule-pack
evaluations, and attestations as the Bedrock path.

## Acceptance Criteria
- AC-1: Given an Azure OpenAI diagnostic-log JSON line (`RequestResponse`
  category shape), When parsed, Then a `NormalizedInvocationRecord` is emitted.
- AC-2: Field-mapping table documented (Azure field → normalized field →
  RP-OBS-COMPLETE / RP-TOOL-SCOPE fields consumed) in docs/adapter-design.md.
- AC-3: Given a record with unknown/missing fields, When parsed, Then provenance
  records explicit `field_unavailable` markers — never silent nulls.
- AC-4: Deterministic synthetic Azure corpus (≥50 records mirroring Bedrock
  corpus scenarios) committed + seedable.
- AC-5: RP-OBS-COMPLETE@1.0.0 and RP-TOOL-SCOPE@1.0.0 evaluate the Azure corpus
  end-to-end with attestations produced.
- AC-6: Tenant isolation: two tenants' Azure sources cannot cross-read (INV-3 test).

## Edge Cases
- Streamed responses (per-chunk log rows) — out of scope v1; documented as
  unsupported in capability matrix (no aspirational rows).
- Content-filter-annotated records: envelope metadata only, body never read.

## Out of Scope
- Live Azure API polling; Event Hub ingestion (export files only, mirror-async).

## Non-Functional Requirements
- Zero external network calls in the adapter/tests (INV-1); body-size caps as in
  Bedrock (`MAX_INLINE_BODY_CHARS` family); INV-2: body-free evaluation path.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_parses_azure_record_into_normalized_contract`, `test_azure_seven_digit_fractional_timestamp_parses`, `test_model_identity_prefers_model_name_over_deployment_alias` | `adapters/azure_openai/parse.py`, `records.py` |
| AC-2 | — (doc) | `docs/adapter-design.md` §3.2 field-mapping table |
| AC-3 | `test_absent_usage_is_unavailable_not_missing`, `test_partial_usage_is_missing_not_unavailable`, `test_no_field_is_ever_silently_none`, `test_stop_reason_and_truncation_are_structurally_unavailable` | `parse.py` availability map |
| AC-4 | `test_corpus_exists_and_meets_the_fifty_record_bar`, `test_corpus_regenerates_byte_identically`, CI `azure_corpus_builder.py --check` | `scripts/azure_corpus_builder.py`, `tests/fixtures/azure/corpus.ndjson` (54 records) |
| AC-5 | `test_obs_complete_evaluates_the_corpus_and_finds_planted_scenarios`, `test_tool_scope_detects_the_planted_violation_on_enriched_records`, `test_unavailable_usage_is_reported_at_info_not_low` | both genesis packs vs. corpus |
| AC-6 | `test_record_claiming_another_tenant_cannot_override_binding`, `test_two_tenants_read_only_their_own_export`, `test_prefix_confusion_does_not_leak_across_tenants`, `test_reader_rejects_path_traversal` | `adapters/azure_openai/source.py` |

## Coverage limitation (must be carried into STORY-362, not softened)
Standard Azure `RequestResponse` logs carry **no tool/function data** and **no
stop reason**. RP-TOOL-SCOPE therefore produces zero findings on standard Azure
records — because there is nothing to evaluate, **not** because the deployment is
in scope compliance. Marked `UNAVAILABLE` in the record and pinned by
`test_standard_azure_records_yield_no_tool_findings_because_data_is_absent`.
