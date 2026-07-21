# STORY-360: Vertex AI Observation Adapter (Adapter #3)

**Status:** ready
**Screen/Area:** Backend — adapters (Pack Epic 14)
**Depends on:** STORY-358, PREREQ-RP; same bar as STORY-359.

## Goal
Same shape as STORY-359 for Google Vertex AI request/audit logs exported via
Cloud Logging sink to customer-owned GCS/JSON (mirror-async).

## Acceptance Criteria
- AC-1: Vertex Cloud Logging export entry (LogEntry JSON with
  `jsonPayload`/audit-log shape) parses to `NormalizedInvocationRecord`.
- AC-2: Field-mapping table (Vertex → normalized → rule-pack fields) in
  docs/adapter-design.md.
- AC-3: Unknown/missing fields → explicit `field_unavailable` provenance.
- AC-4: Deterministic synthetic Vertex corpus (≥50 records, mirrored scenarios)
  committed + seedable.
- AC-5: Both genesis rule-packs evaluate the corpus end-to-end w/ attestations.
- AC-6: INV-3 cross-tenant isolation test.

## Edge Cases / Out of Scope / NFRs
Mirror STORY-359 (no live GCP calls; export files only; body-free path).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_parses_vertex_entry_into_normalized_contract`, `test_nanosecond_timestamp_parses`, `test_rpc_status_code_maps_to_named_error` | `adapters/vertex_ai/parse.py`, `records.py` |
| AC-2 | — (doc) | `docs/adapter-design.md` §3.3 |
| AC-3 | `test_endpoint_deployment_yields_missing_model_not_an_endpoint_id`, `test_token_counts_and_stop_reason_are_structurally_unavailable`, `test_no_field_is_ever_silently_none` | `parse.py` availability map |
| AC-4 | `test_corpus_meets_the_fifty_record_bar`, `test_corpus_regenerates_byte_identically`, CI `vertex_corpus_builder.py --check` | `scripts/vertex_corpus_builder.py`, `tests/fixtures/vertex/corpus.ndjson` (56 records) |
| AC-5 | `test_obs_complete_evaluates_corpus_and_finds_planted_scenarios`, `test_tool_scope_detects_planted_violation_on_enriched_entries`, `test_all_vertex_token_findings_are_info_because_the_gap_is_structural` | both genesis packs vs. corpus |
| AC-6 | `test_project_id_in_log_cannot_override_tenant_binding`, `test_two_tenants_read_only_their_own_export`, `test_reader_rejects_traversal_and_prefix_confusion` | `adapters/export_source.py`, `adapters/vertex_ai/source.py` |

## INV-2 note (why this adapter is not like Azure)
Vertex Data Access logs **can contain the prompt and completion**
(`protoPayload.request` / `.response`). The parser is body-blind by
construction — no code path indexes those keys — and the corpus plants
PHI-bearing entries so the guard cannot pass vacuously. Pinned by
`test_phi_payload_present_in_source_never_reaches_the_record` and
`test_phi_never_reaches_rule_findings_either`.

## Coverage limitations (carry into STORY-362 unsoftened)
- No token counts, no stop reason (audit schema) → `UNAVAILABLE`, graded INFO.
- No tool data → RP-TOOL-SCOPE silent on standard entries: a gap, not a pass.
- Endpoint-deployed models → model identity `MISSING`; an endpoint id is never
  reported as a model id.
