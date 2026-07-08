# STORY-406 — Bedrock Invocation-Log Adapter
Stage: standard

## Lifecycle
- [x] discover   (adapter subsystem is new — no `adapters/` package existed; territory mapped below)
- [x] shape      (1a brainstorm skipped — change is specified by the evaluability-gate results doc; 1b interview answered by user, Decision Log below)
- [ ] preview    (skipped — backend-only, no user-facing surface)
- [ ] plan
- [ ] build
- [ ] verify
- [ ] sell       (n/a — not design-partner-facing this pass; SummitCare demo is a follow-on)

## Context / Source of truth
Input = evaluability-gate results (`saro-evaluability-gate-results.md`, provided by user).
STORY-406 is referenced but never written: `migrations/036_observation_coverage.sql:12`
and `specs/stories/STORY-COV-001.md:79,88,96` both defer the "live Bedrock-adapter
heartbeat emission" to this story. This story delivers the adapter core.

## DISCOVER — territory + unknown-unknowns
- No `adapters/` package exists yet — this is a new product-path subsystem.
- Two consumers the adapter must feed:
  - Audit ingest: `IngestRequest` (`routers/ingest.py:44`) — needs `prompt`+`raw_output`
    (both `min_length=1`), `source_model` (narrow `Literal`, `:36`), `tenant_id`,
    `vertical`, `metadata`. Engine entry: `SARoEngine.run_output_audit(...)`.
  - Coverage heartbeat: `record_checkpoint(...)` (`services/observation_coverage_service.py:174`)
    — `(tenant_id, system_id, adapter_id, watermark_position, watermark_timestamp)`,
    idempotent per UNIQUE key, de-identified by construction (INV-2: positions/timestamps only).
- `emit_observation` (`:238`) OVERRIDES `watermark_position` with a time bucket
  `obs:{floor(ts/bucket)}` — good for live tail, WRONG for resumable backfill replay.
  Backfill must call `record_checkpoint` directly with a monotonic stream cursor.
- STORY-336 guard (`grc/guards/external_model.py`): `ast.walk` catches imports at ANY
  nesting depth (lazy imports do NOT evade it); `bedrock-runtime`/`bedrock-agent-runtime`
  are forbidden endpoint literal substrings (`:102-103`). boto3 `s3`/`logs` are NOT
  denylisted. → Adapter is clean iff it reads logs (s3/logs) and never references a
  `bedrock-runtime` client or endpoint literal, and makes zero hosted-model calls.
- Rule-pack schema mismatch: loader expects `{slug}/{version}/rules.yaml` with
  `rule_id/domain_trigger/obligation`; shipped packs are top-level `*_v1.0.yaml` with
  `id/name/severity/category/check_type`. → Promoting RP-* rules is NOT a clean drop-in;
  deferred to a follow-on (Wave 1/2 per the gate doc).

## Decision Log
| # | Question | Answer | Architectural consequence |
|---|---|---|---|
| D1 | `source_model` for Bedrock's model zoo — widen `Literal` per model, or collapse? | Keep narrow enum; add ONE `"bedrock"` catch-all. `anthropic.*`→`"claude"`; all other Bedrock modelIds→`"bedrock"`. True identity preserved in `system_id`+`metadata`. | One-line enum change (`ingest.py:36`), no per-model treadmill. Audit `source_model` filter stays usable by adapter family; exact model lives in `system_id` (=modelId) and `metadata.modelId`. |
| D2 | Watermark mode — time-bucket vs monotonic cursor; which mode built first? | Monotonic stream-cursor `record_checkpoint` is the primitive; time-bucketed `emit_observation` is the live-tail layer on top. Spec BOTH modes, implement BACKFILL first. | Adapter's coverage branch calls `record_checkpoint` directly with a stream cursor (S3 object key+line, or CloudWatch event id) as `watermark_position`. Live-tail is a thin follow-on reusing the same cursor. |
| D3 | S3-externalized bodies — may the audit branch fetch them? | Yes — `s3:GetObject`, read-only, on the AUDIT branch only. Coverage branch FORBIDDEN from any body/S3 read. Add a test asserting coverage reads only the envelope (proves INV-2). | Adapter splits into two branches with an enforced seam: coverage(envelope-only) and audit(may resolve bodies). The INV-2 test is itself attestation evidence. |

## Claim ceiling (write into ADR/compliance later)
The invocation-log layer observes MODEL behavior (intended actions: `toolUse`, `stopReason`),
not SYSTEM behavior (execution, approvals, planner state live outside this log). Any external
claim from adapter-derived rules must be scoped to "model-invocation-level evidence."
Enforcement-level claims require a future harness adapter.

## Decision Log (cont. — confirmation tool failed; user said "continue" → conservative defaults, logged)
| # | Question | Answer | Consequence |
|---|---|---|---|
| D4 | How does the backfill audit branch submit to the engine? | New standalone `services/audit_submission.submit_audit_sync` (synchronous — backfill has no request context). Existing HTTP route `_run_audit_background` left UNTOUCHED (conservative: don't disturb the hot path). Adapter takes an injected `submit` callable; default wires to the service. | Adapter is unit-testable with a fake `submit`; no routers/ hot-path refactor. Mild duplication of row-creation logic vs the route — logged as a follow-up consolidation candidate. |
| D5 | Scope of THIS story? | Adapter core only (AC-1..6). RP-* rules are follow-on (also blocked by rule-pack loader/schema mismatch). Adapter emits `toolConfig`/`toolUse`/`stopReason`/truncation into `metadata` so Wave-1 rules can consume it later. | Bounded, reviewable story; claim ceiling preserved. |
| D6 | boto3 dependency (not installed; optional in requirements.txt) | Lazy-import boto3 ONLY in the default S3 resolver; parser + coverage branch stay dependency-free. S3 resolver is injected → tests never need AWS. | INV-2 becomes STRUCTURAL: `emit_coverage` takes only an `Envelope`, so it *cannot* read a body. Coverage branch also never imports boto3. |

## Lifecycle (cont.)
- [x] build
- [x] verify (gates 1–7 green; independent reviewer + security-auditor run pre-commit)

## Deviations
- D4 conservative variant chosen: standalone sync submission service instead of refactoring
  `routers/ingest.py:_run_audit_background` to share it. Aggressive option (shared core called by
  both route + adapter) deferred to avoid touching the HTTP hot path in this story.
- REV#3 (layering: `services/audit_submission` imports `routers.scan._persist_traces`): NOT fixed
  in this story. It is a pre-existing pattern — `routers/{ingest,output_audit,hf_processor}.py` and
  `tests/` all already `from routers.scan import _persist_traces`. Relocating it to a service touches
  5 call sites across 4 routers = cross-cutting refactor beyond STORY-406 scope. Follow-up candidate.

## Review findings addressed (pre-commit, before any merge)
| Finding | Severity | Resolution |
|---|---|---|
| SEC FND-1 SSRF/confused-deputy S3 fetch of untrusted `s3Path` | HIGH (blocker) | `validate_s3_path`: `s3://` scheme + deny-by-default bucket allowlist on `BedrockAdapterConfig`; `_guarded_resolver` enforces it even for an injected resolver. Tests: `test_s3_body_denied_when_bucket_not_allowlisted`. |
| SEC FND-2 unbounded body read (memory DoS) | MED | `MAX_INLINE_BODY_CHARS` / `MAX_S3_BODY_BYTES` caps; `head_object` size pre-check + bounded read. Test: `test_oversized_inline_body_rejected`. |
| SEC FND-3 / REV#2 cursor bypassed `_safe_ident` | MED/MAJOR | `emit_coverage` routes cursor through `_safe_ident`. Test: `test_cursor_sanitized_into_evidence`. |
| SEC FND-4 initial commit outside try → session poison cascade | MED | wrapped initial insert+commit in try/rollback. |
| SEC FND-5 non-IntegrityError left session dirty | LOW | per-record `db.rollback()` in replay except blocks (localized; shared service untouched). |
| REV#1 audit branch not idempotent | MAJOR | duplicate-cursor gate skips re-audit. Test asserts `r2.audits_submitted==0`. |
| REV#4 weak INV-2 test | MINOR | added `test_emit_coverage_is_structurally_body_free` (signature proof). |
| REV#5 metadata key casing vs AC | MINOR | aligned to AC-1 camelCase; asserted in `test_build_audit_submission_resolves_s3`. |
| REV#6 dead `NormalizedObservation` | MINOR | removed. |
| REV#7 wrong `_parse_timestamp` docstring | MINOR | corrected. |
| REV#8 S3 fail-soft untested | MINOR | `test_s3_fetch_failure_fails_soft`. |
