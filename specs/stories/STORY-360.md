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
