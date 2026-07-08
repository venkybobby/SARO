# STORY-407: Demo Corpus Builder (Synthetic Bedrock Invocation Logs)

**Status:** done
**Screen/Area:** Demo tooling / Ingestion (backend, no UI)
Epic: Adapter layer | Depends on: STORY-406 (Bedrock invocation-log adapter, already
merged on `main` at build time), the existing SARO engine + observation-coverage service.
Blocks: SummitCare demo readiness.

> Retroactive spec — this story's scope was worked out via an interview-driven Decision
> Log in `implementation-notes.md` rather than a pre-authored spec (a process deviation
> flagged in code review). This file captures the resulting shape for future traceability,
> written after the implementation, from the original request
> (`Downloads/STORY-407-demo-corpus-builder.md`) plus the choices actually made.

## Goal
Produce a curated, deterministic demo dataset of synthetic AWS Bedrock model-invocation
logs — byte-compatible with the real Bedrock log format, laid out in the real S3 key
structure — seeded with known findings from existing Evidence Corpus fixtures, so every
SummitCare demo rehearsal produces identical results. No client PHI; every record is
self-evidently synthetic.

## Key scope correction (recon vs. the original request)
The original request assumed STORY-406 (the Bedrock adapter) and STORY-405 (eval core)
did not exist yet. Recon against `origin/main` found STORY-406 fully built, reviewed, and
merged (`adapters/bedrock/{records,parse,replay}.py`, its own test suite). This story
therefore did **not** rebuild the adapter — it filled the one real gap (an S3-key-layout
discovery/reader, since `replay_backfill()` takes `(cursor, raw)` pairs but nothing turned
a key layout into that iterable) and built the generator on top of the real pipeline.

## Acceptance Criteria (Given/When/Then)

**AC-1 — Bedrock envelope fidelity.**
Given a record produced by the builder, When validated against the schema fixture
(`tests/fixtures/bedrock/model_invocation_log.schema.json`, doc-grounded from the AWS
reference with source URL + retrieval date recorded), Then every field name/type/nesting
matches, and every record carries a synthetic `identity.arn` + `requestMetadata`.

**AC-2 — S3 key layout.**
Given `--out` (local dir) or `--s3-bucket`, Then records are written as gzipped NDJSON
under `AWSLogs/{accountId}/BedrockModelInvocationLogs/{region}/{yyyy}/{mm}/{dd}/{hh}/...`,
batched by hour (multi-record objects), identical in shape whether read from local disk
(`LocalLogStore`) or S3 (`S3LogStore`) via the new `adapters/bedrock/source.py` reader.

**AC-3 — Determinism.**
Given the same manifest + `--seed`, two runs produce byte-identical gzip output (fixed
gzip `mtime=0`, sorted JSON keys, deterministic record ordering). Changing only the seed
re-rolls `requestId`s and clean-traffic sampling but not planted-scenario placement.

**AC-4 — Planted use cases fire correctly.**
Given the corpus is ingested via `adapters/bedrock/source.py` + `replay_backfill()` and
evaluated by the real `SARoEngine`, Then exactly the use cases with an existing firing
rule produce findings — UC-1 (PHI, Privacy & Security), UC-2 (hallucination,
Misinformation), UC-6 (benign false-positive, AI System Safety) — and clean traffic
produces zero findings. UC-3 (missing disclaimer), UC-4 (prompt-injection), UC-5
(off-allowlist modelId) are planted for demo completeness but have no firing rule yet;
documented as blocked on separate rule stories, not asserted by the automated check
(owner decision — plant all 6, gate the assertion to what actually fires today).

**AC-5 — Observation gap.**
Given the manifest's declared gap window, Then no log objects exist for that hour, clean
traffic exists on both sides, and `services.observation_coverage_service.reconcile_backfill_gaps`
(new — the existing `detect_gaps` is a live cadence-vs-*now* monitor and cannot see an
interior gap in a closed historical window) reports exactly one gap containing the
declared window.

**AC-6 — Synthetic provenance.**
Every record carries `accountId="999888777666"` and
`requestMetadata={"environment":"demo-synthetic","source":"saro-evidence-corpus"}`,
unconditionally, on both the planted and clean-traffic code paths.

## Edge Cases
- Planted `at` timestamps must fall in a populated (non-gap) hour — builder validates and
  raises `ValueError` otherwise.
- `clean_traffic.count` must be ≥ the number of non-gap hours, or a spurious gap could open
  in an under-filled hour — builder validates.
- Clean-traffic candidates are screened against the engine's own `_RISK_SIGNALS` tables
  before use, so a benign-pool sentence with an incidental keyword can never leak into
  "clean" traffic as a silent finding.
- Manifest `account_id`/`region` are validated (12-digit account, AWS region charset)
  before any output path is constructed from them — an untrusted/malformed `--manifest`
  cannot write outside `--out` (path-injection guard, added in security review).
- Log-object keys are validated against the exact Bedrock layout shape before any
  filesystem read, and resolved-path containment is double-checked — closes a path-
  traversal vector in `LocalLogStore.read_bytes` (added in security review).
- Both compressed-object size (`MAX_OBJECT_BYTES`) and **decompressed** output size
  (`MAX_DECOMPRESSED_BYTES`) are capped via streaming/incremental reads, closing a
  decompression-bomb vector (`gzip.decompress()` has no output bound) (security review).
- Two checkpoints sharing an identical `watermark_timestamp` reconcile in a stable,
  deterministic order (secondary sort key on `watermark_position`) rather than depending
  on DB row-return order, which Postgres does not guarantee for ties (code review).

## Out of Scope
- CloudWatch Logs delivery variant (P2).
- Streaming/near-real-time replay mode (P2).
- Multi-tenant demo dataset / second synthetic accountId (P2).
- Authoring new rules for UC-3/UC-4/UC-5 (separate future stories).
- Rebuilding or modifying the STORY-406 adapter (`records.py`/`parse.py`/`replay.py`) —
  reused as-is, its existing test suite verified still green.

## Non-Functional Requirements
- Zero external-model calls anywhere in the builder or adapter path — STORY-336 guard
  (`python -m grc.guards.external_model`) must stay green; pinned by
  `test_source_reader_is_guard_clean`.
- ruff / mypy / bandit clean on all touched files.
- Golden-path rehearsal run twice, byte-identical, before SummitCare is booked.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 envelope fidelity | `test_schema_fixture_is_valid_and_doc_grounded`, `test_every_builder_record_matches_schema` | `tests/fixtures/bedrock/model_invocation_log.schema.json`, `scripts/demo_corpus_builder.py` |
| AC-2 S3 key layout | `test_s3_key_layout_and_hourly_batching`, `test_source_reader_roundtrip` | `adapters/bedrock/source.py`, `scripts/demo_corpus_builder.py` |
| AC-3 determinism | `test_determinism_byte_identical_for_same_seed`, `test_seed_changes_ids_not_planted_placement` | `scripts/demo_corpus_builder.py` |
| AC-4 planted findings | `test_e2e_exactly_covered_findings_fire_and_gap_is_attested` | `scripts/demo_corpus_builder.py`, `scripts/demo_manifest.yaml`, `adapters/bedrock/source.py` (existing `replay.py`/engine unmodified) |
| AC-5 observation gap | `test_observation_gap_has_no_objects_with_traffic_on_both_sides`, `test_e2e_exactly_covered_findings_fire_and_gap_is_attested`, `test_reconcile_backfill_gaps_is_deterministic_on_tied_timestamps` | `services/observation_coverage_service.py` (`reconcile_backfill_gaps`) |
| AC-6 synthetic provenance | `test_synthetic_provenance_on_every_record` | `scripts/demo_corpus_builder.py` |
| Security: path traversal | `test_local_store_rejects_path_traversal_key`, `test_local_store_rejects_malformed_key_shape` | `adapters/bedrock/source.py` |
| Security: decompression bomb | `test_bounded_gunzip_rejects_decompression_bomb`, `test_bounded_gunzip_roundtrips_normal_payload` | `adapters/bedrock/source.py` |
| Security: object-size cap | `test_local_store_enforces_object_size_cap` | `adapters/bedrock/source.py` |
| Security: manifest path injection | `test_manifest_account_id_and_region_are_validated` | `scripts/demo_corpus_builder.py` |
| STORY-336 guard-clean | `test_source_reader_is_guard_clean` | `adapters/bedrock/source.py`, `grc/guards/external_model.py` (unmodified — `adapters` already scanned) |

## Review outcomes (independent reviewer + security-auditor, pre-merge)
- **security-auditor: FAIL → fixed.** Two HIGH findings, both verified experimentally:
  path traversal in `LocalLogStore.read_bytes` (no containment check) and a
  decompression bomb (`gzip.decompress()` has no output-size bound). Both fixed with
  key-shape validation + resolved-path containment, and a separate
  `MAX_DECOMPRESSED_BYTES` cap enforced via incremental read. Also fixed: MEDIUM
  (local reads weren't streamed, so the size cap was checked only after a full read)
  and LOW (unsanitized manifest `account_id`/`region` flowing into output paths).
  INFO-only, not fixed (pre-existing, out of this story's scope): `ObservationGap` has
  no UNIQUE constraint, unlike `ObservationCheckpoint` — a latent gap in the coverage
  module generally, flagged for a future FND, not introduced or worsened here.
- **reviewer: REQUEST CHANGES → fixed.** Caught the security fixes existing only in the
  working tree at review time (now staged/committed) — a real MAJOR correctness bug
  (`reconcile_backfill_gaps` had no secondary sort key, so tied `watermark_timestamp`
  rows could reconcile non-deterministically on Postgres; SQLite's insertion-order
  preservation was masking it in tests) — fixed with a `watermark_position` tiebreak and
  pinned by a dedicated regression test. Also fixed: a mypy annotation gap in
  `_make_body`, and an inaccurate design-note claim in `implementation-notes.md` ("one
  checkpoint per hour" — actually one per record; corrected). This spec file itself was
  written in response to a MINOR finding that no `specs/stories/STORY-407.md` existed.
