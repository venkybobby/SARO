# STORY-406 — Bedrock Invocation-Log Adapter

**Status:** ready
**Screen/Area:** Ingestion / Observation coverage (backend, no UI)
Epic: Adapter layer | Priority: P1 — unblocks the deferred STORY-COV-001 AC-1
live heartbeat and is the substrate for the Wave-1 evaluability rules.
Origin: evaluability-gate results (`saro-evaluability-gate-results.md`); deferral
pointers in `migrations/036_observation_coverage.sql:12` and `STORY-COV-001.md:79,88,96`.

## Goal
Give SARO a **read-only** adapter that turns a customer's AWS Bedrock
model-invocation logs into SARO's two existing evidence streams — async risk
audits (`IngestRequest` → engine) and observation-coverage heartbeats
(`record_checkpoint`) — without SARO ever calling a hosted model. The adapter
parses logs the customer already produced; it never invokes `bedrock-runtime`.
This story ships the **backfill (historical replay)** path; live-tail is spec'd
but follow-on. It is the missing half of STORY-COV-001's deferred heartbeat.

## Key schema facts (from the gate doc)
- `Converse` `input.inputBodyJson` carries the full conversation per invocation
  (`system`, all prior turns, `toolResult` blocks) — cross-turn context is
  present yet each record is *stateless per record*.
- Output carries `toolUse` blocks + `stopReason` — the model's *intended*
  actions, not the harness's *executed* actions (claim ceiling).
- Coverage heartbeat reads only the **envelope** (`modelId`, cursor,
  `timestamp`) — never bodies (INV-2).
- Large payloads externalize to `input.inputBodyS3Path` / `output.outputBodyS3Path`;
  the audit branch may resolve them (D3), the coverage branch may not.

## Acceptance Criteria (Given/When/Then)

**AC-1 — Parse & normalize (Converse + InvokeModel).**
Given a well-formed Bedrock `ModelInvocationLog` record of `operation` in
{`Converse`, `ConverseStream`, `InvokeModel`, `InvokeModelWithResponseStream`},
When the adapter parses it, Then it yields a normalized observation carrying:
`prompt` (flattened user turns; `system` prepended when present), `raw_output`
(assistant text), `source_model` (per AC-5), `system_id` = `modelId`,
`watermark_position` = the record's stream cursor, `watermark_timestamp` =
record `timestamp`, and `metadata` = {`requestId`, `region`, `operation`,
`modelId`, `inputTokenCount`, `outputTokenCount`, `stopReason`}; and it does not
raise on any well-formed record.

**AC-2 — Coverage heartbeat is envelope-only, backfill cursor (INV-2).**
Given a corpus of records replayed in backfill mode, When the adapter emits
coverage, Then for each record it calls `record_checkpoint` with the monotonic
stream cursor as `watermark_position` (NOT a time bucket) and reads ONLY
envelope fields; And a test asserts the coverage branch never accesses
`inputBodyJson`/`outputBodyJson` nor performs any S3 fetch (INV-2 proven, not
asserted).

**AC-3 — Audit branch resolves bodies (incl. S3), coverage never does (D3).**
Given a record whose bodies are inline OR externalized as
`inputBodyS3Path`/`outputBodyS3Path`, When the audit branch runs, Then bodies
are resolved (read-only `s3:GetObject` for externalized) and submitted as
`prompt`+`raw_output` through the existing engine audit path; And the coverage
branch performs zero body or S3 reads for the same record.

**AC-4 — Idempotent replay.**
Given the same log corpus replayed twice (adapter restart / duplicate window),
When coverage emits, Then checkpoints remain idempotent per
`(tenant_id, system_id, adapter_id, watermark_position)` — no double count —
reusing the existing UNIQUE constraint + `IntegrityError` no-op path.

**AC-5 — `source_model` mapping (D1).**
Given `modelId` matching `anthropic.*` (or `*.anthropic.claude-*` cross-region),
Then `source_model` = `"claude"`; Given any other Bedrock `modelId`
(`amazon.nova-*`, `meta.llama*`, `mistral.*`, `cohere.*`, …), Then
`source_model` = `"bedrock"`; And the `IngestRequest` `Literal` gains `"bedrock"`;
And the exact model survives in `system_id` and `metadata.modelId`.

**AC-6 — STORY-336 stays green.**
Given the new adapter module(s) on the product path, When
`grc.guards.external_model.assert_clean_product_path()` scans, Then it passes:
the adapter imports only boto3 `s3`/`logs` (or stdlib), references no
`bedrock-runtime`/`bedrock-agent-runtime` endpoint literal, and makes zero
hosted-model calls; And a regression test pins that the adapter path is guard-clean.

## Edge Cases
- **Missing/partial output** (no `output`, or `raw_output` empty after flatten):
  skip the AUDIT for that record with a logged reason (`IngestRequest` requires
  `min_length=1`); still emit the coverage heartbeat (we observed an invocation).
- **`stopReason=max_tokens`** (truncated output): still audit; record
  `truncated=true` in `metadata` (feeds a future RP-OBS-COMPLETE rule).
- **S3 body missing / `AccessDenied`**: audit branch fails-soft for that record
  (log + skip), coverage branch unaffected (it never touched S3).
- **Clock skew** source vs SARO: `watermark_timestamp` uses the source-side
  record `timestamp`; document skew tolerance.
- **Unsafe chars in `modelId`/cursor**: pass through `_safe_ident` (already in
  the coverage service) → deterministic surrogate; no free text reaches evidence.
- **Malformed JSON / unknown `operation`**: skip the record with a structured
  warning; never abort the whole corpus.

## Out of Scope
- **Live-tail scheduler** — spec'd (reuses the cursor primitive); backfill ships first.
- **RP-* rule packs** (RP-TOOL-SCOPE, RP-INJ-BOUNDARY, RP-HIER-INTEGRITY,
  RP-ACTION-TIER, RP-OBS-COMPLETE) — Wave 1/2 follow-on. Blocked additionally by
  the rule-pack loader/schema mismatch (`rule_packs/loader.py` vs shipped
  `*_v1.0.yaml`). This story only emits the *data* those rules will consume
  (`toolConfig`, `toolUse`, `stopReason`, truncation flags) into `metadata`.
- **Harness-level execution/approval attestation** — claim ceiling; needs a
  future harness adapter.
- **Alerting/paging on gap-open** — notifications family.
- **IAM/credential provisioning** — operator responsibility; adapter assumes a
  read-only role is already configured.

## Non-Functional Requirements
- Zero hosted-model calls on the product path (STORY-336 hard gate).
- INV-2: coverage evidence carries positions/timestamps only — proven by test.
- Backfill parsing is streaming/bounded-memory over a corpus (no whole-file slurp
  of unbounded logs where avoidable).
- Standard project rules: async handlers if any route is added, `/api/v1/` prefix,
  ruff/mypy/bandit clean, ratchet holds.

## Claim-ceiling note (for ADR/compliance)
Invocation-log evidence is **model-invocation-level**, not system-level. External
claims derived from this adapter must be scoped accordingly; enforcement-level
claims wait for a harness adapter. (Prevents a later Marcus-Hale-style finding.)

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 parse/normalize | `test_parse_envelope_converse`, `test_extract_converse_prompt_output`, `test_extract_invoke_model_prompt_output`, `test_truncated_flag_from_max_tokens`, `test_build_audit_submission_resolves_s3` (metadata contract) | `adapters/bedrock/parse.py`, `records.py` |
| AC-2 coverage envelope-only (INV-2) | `test_emit_coverage_uses_cursor_watermark`, `test_emit_coverage_is_structurally_body_free`, `test_coverage_never_reads_body_inv2`, `test_cursor_sanitized_into_evidence` | `adapters/bedrock/replay.py::emit_coverage` + `observation_coverage_service.record_checkpoint` |
| AC-3 audit + S3 resolution | `test_build_audit_submission_resolves_s3`, `test_s3_body_denied_when_bucket_not_allowlisted`, `test_s3_fetch_failure_fails_soft`, `test_oversized_inline_body_rejected` | `adapters/bedrock/parse.py` (`validate_s3_path`, `_guarded_resolver`), `replay.py::_default_s3_resolver` |
| AC-4 idempotent replay | `test_backfill_idempotent_per_cursor` (coverage + audit), `test_malformed_record_skipped_not_aborting` | `replay.py::replay_backfill` (duplicate-cursor gate) |
| AC-5 source_model + enum | `test_map_source_model` (param), `test_ingest_enum_includes_bedrock` | `parse.py::map_source_model`, `routers/ingest.py:36` |
| AC-6 STORY-336 clean | `test_adapters_in_product_scan_and_clean` | `grc/guards/external_model.py::PRODUCT_PACKAGE_DIRS` |
| submit plumbing | `test_submit_audit_sync_persists_with_fake_engine` | `services/audit_submission.py` |

## Review outcomes (independent reviewer + security-auditor, pre-commit)
Fixed before commit: SSRF/confused-deputy S3 fetch → scheme check + deny-by-default
bucket allowlist (`validate_s3_path`); unbounded body read → inline + S3 size caps;
cursor bypassed `_safe_ident` → sanitized (INV-2); audit branch not idempotent →
duplicate-cursor gate; `submit_audit_sync` initial commit outside try → wrapped in
rollback; per-record `db.rollback()` on failure. Cleanups: removed dead
`NormalizedObservation`, fixed `_parse_timestamp` docstring, aligned metadata keys to
the AC-1 contract, strengthened the INV-2 test to a structural signature check.
Deferred (logged): `services/audit_submission` imports `routers.scan._persist_traces`
— a pre-existing layering pattern shared by 4 routers; relocating it is a
cross-cutting refactor out of this story's scope.
