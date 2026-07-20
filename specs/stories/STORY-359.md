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
