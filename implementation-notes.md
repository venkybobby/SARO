# STORY-407 — Demo Corpus Builder (Synthetic Bedrock Invocation Logs)
Stage: standard

## Lifecycle
- [x] discover   (dependency-reality pass — STORY-406 found already built/merged on main)
- [x] shape      (AskUserQuestion → Decision Log: build-406-first, plant-all-gate-covered, scripts/+fixtures location)
- [x] preview    (skipped — CLI-only, no UI per story Non-Goals)
- [x] plan
- [x] build
- [x] verify     (independent reviewer + security-auditor both ran; all findings fixed
                   and pinned with regression tests; change-debrief.html generated)
- [ ] sell       (SummitCare demo-facing — on request, not yet requested)

## Discover — dependency reality (verified vs current code, memory was stale)
STORY-407 generates synthetic Amazon Bedrock model-invocation-log JSON in an S3
key layout so the STORY-406 adapter can discover+ingest it, feeding the STORY-405
core to produce 6 planted findings + a gap attestation. Verified ground truth:

- **STORY-406 Bedrock adapter: DOES NOT EXIST.** No S3-log discovery/ingest code.
  `bedrock-runtime`/`bedrock-agent-runtime` are on the STORY-336 forbidden-endpoint
  denylist (grc/guards/external_model.py). NOTE: reading AWS-written invocation
  *logs* from S3 (s3:GetObject) is passive evidence ingest, NOT calling an inference
  endpoint — so a log adapter is architecturally allowed; it just isn't built.
  The team is actively speccing it (untracked specs/stories/saro-evaluability-gate-results.md
  — "spec both modes, implement one"; backfill/replay of historical log corpus is
  the intended SummitCare demo path).
- **STORY-405 core: PARTIAL.** engine.py:run_audit (4-gate) + services/
  observation_coverage_service.py (record_checkpoint / coverage_report / gap detection)
  exist — but as an INBOUND PUSH model (client posts output → SARO audits), not an
  S3-log puller.
- **Evidence Corpus Factory: NO unified entity.** Distributed: tests/fixtures/
  synthetic_phi.py (fabricated HIPAA-18), tests/fixtures/fp_baseline/corpus.json
  (per-domain positives/hard_negatives/benign_pool), per-rule fixtures.positive_text
  in rule_packs/*/v1.0.0/rules.yaml.
- **Rule coverage for the 6 planted UCs:** UC-1 PHI (AIGP-PRIV-1/GOVERN-4.2) ✓,
  UC-2 hallucination (MEASURE-2.5) ✓, UC-6 benign-FP ✓. UC-3 missing-disclaimer,
  UC-4 prompt-injection (RP-INJ-BOUNDARY is Wave-2, needs STORY-335), UC-5
  off-allowlist modelId (an ENVELOPE check the content engine does not perform) —
  NO firing rule today. Matches the story's own blocking Open Question #2.
- **Repo conventions:** CLI scripts in top-level scripts/ (seed_demo.py etc.,
  standard preamble: ROOT=Path(__file__).parent.parent, dotenv, logging). Test
  fixtures in tests/fixtures/. Rule/YAML under rule_packs/{fw}/{ver}/rules.yaml.
- **STORY-336 guard: LIVE** in .github/workflows/quality-gates.yml (python -m
  grc.guards.external_model). The builder + its path must import zero provider SDKs.

### The fork (owner decision required — changes what gets built)
AC-4.1 end-to-end ("adapter ingest → core eval → exactly 6 findings") CANNOT pass
today: no adapter, 3/6 rules absent. Options put to owner via AskUserQuestion.

## Decision Log
Q1 dependency gap (owner)? → **Build STORY-406 adapter FIRST, then STORY-407 on top**
  so the end-to-end path is real. Two stories in this execution: (406) a Bedrock
  invocation-log adapter that discovers NDJSON.gz under the S3 key layout (local-dir
  OR S3 backend), parses multi-record objects, emits coverage checkpoints from the
  ENVELOPE ONLY (INV-2: never reads bodies for the heartbeat), and runs the existing
  output-audit on prompt+output to produce findings; (407) the deterministic demo
  corpus builder that writes that format. Consequence: adapter is a NEW subsystem.
  Design anchors from specs/stories/saro-evaluability-gate-results.md decisions:
   - #1 source_model: modelId → "bedrock" catch-all; anthropic.* → "claude".
   - #2 watermark: monotonic stream-cursor record_checkpoint is the primitive;
     implement BACKFILL/replay first (SummitCare demo = replay of historical corpus).
   - #3 S3 bodies: audit branch may s3:GetObject read-only; COVERAGE branch forbidden
     from body reads — prove it with a test (INV-2 as attestation evidence).
Q2 rule coverage (owner)? → **Plant all 6 UCs in the corpus; gate the automated
  assertion to UCs the pinned demo rule pack actually fires (UC-1 PHI, UC-2 hallucination,
  UC-6 benign-FP).** Author NO new rules here. UC-3 disclaimer / UC-4 prompt-injection /
  UC-5 off-allowlist-modelId documented as blocked on separate rule stories (story Open Q2).
  The run-summary + E2E check must state which UCs are asserted vs. planted-not-yet-firing.
Q3 locations (owner)? → scripts/demo_corpus_builder.py + scripts/demo_manifest.yaml;
  Bedrock schema fixture at tests/fixtures/bedrock/model_invocation_log.schema.json.
Q4 adapter location (mine)? → NEW top-level package adapters/bedrock_invocation_log.py.
  The STORY-336 guard scans grc/routers/services/middleware + top-level *.py — NOT adapters/.
  Governance-forward: ADD "adapters" to PRODUCT_PACKAGE_DIRS so the new ingestion path is
  PROVABLY under the no-external-model guard (strengthens the invariant; good examiner story).
  Adapter uses boto3 s3 ONLY (lazy import) — s3 is not forbidden; never touches bedrock-runtime.
Q5 gap model (mine; makes AC-5.1 deterministic)? → CORRECTED (code review caught the
  original wording): emit_coverage (existing STORY-406 code) writes ONE checkpoint PER
  RECORD, not per hour — this manifest's 66 records land as 1-2 checkpoints per populated
  hour. What's actually guaranteed: objects are hour-batched (AC-2.3) and every non-gap
  hour gets ≥1 clean record, so the ONLY interval between consecutive checkpoints that
  exceeds cadence is the declared gap hour. Builder validates planted `at` timestamps fall
  in populated hours. New coverage fn reconcile_backfill_gaps(cadence=3600s explicit, NOT
  the 300s global) walks ordered checkpoints (tiebreak on watermark_position — ties in
  watermark_timestamp occur in practice and Postgres has no stable order without one; a
  code-review finding, fixed + pinned by test_reconcile_backfill_gaps_is_deterministic_on_tied_timestamps)
  and opens+closes a gap for each inter-checkpoint interval > cadence → EXACTLY the one
  deliberate gap. Honest + reproducible.
Q6 findings source (mine)? → Planted outputs seeded from rule-pack fixtures.positive_text /
  fp_baseline positives (guaranteed to fire the engine's deterministic keyword scan); clean
  traffic from benign_pool (guaranteed zero). UC-6 false-positive = a benign sentence that
  trips one keyword (e.g. "crashed on CI" → AI System Safety). Verify exact firing by running
  the engine in the E2E test — assert, don't assume.

## Plan (ordered by tweak-likelihood)
Base: origin/main (has record_checkpoint/coverage_report/detect_gaps; NO emit_observation — fine).
Bundles STORY-406 (adapter) + STORY-407 (builder) on one branch; 407 is the ask, 406 the enabler.

1. DATA/SCHEMA (tweak-likely): tests/fixtures/bedrock/model_invocation_log.schema.json —
   doc-grounded JSON Schema of the Bedrock ModelInvocationLog, with $comment provenance
   (source URL, retrieval date, schemaVersion). Field-by-field from the AWS reference. (AC-1.2)
2. MANIFEST (tweak-likely): scripts/demo_manifest.yaml — seed, window, cadence_seconds(3600),
   clean_traffic.count(60), planted[6 UCs w/ corpus refs + at-timestamps + fictional-name note],
   observation_gap{start,end}. Builder is manifest-driven (FR-3, AC-3.2).
3. ADAPTER (STORY-406): adapters/bedrock_invocation_log.py —
   - map_source_model(modelId)->closed vocab ("claude" for anthropic.*, else "bedrock") (dec#1)
   - LocalLogStore + S3LogStore(boto3 s3 lazy); iter_keys/read_bytes; discover(window) parses
     yyyy/mm/dd/hh from key.
   - parse_ndjson_gz; record_to_observation(ENVELOPE ONLY — INV-2) vs record_to_audit_input(bodies).
   - replay_backfill(db, store, window): per hour-bucket record_checkpoint(envelope) + per record
     run_output_audit(bodies)->findings; then reconcile_backfill_gaps. Returns a summary.
4. COVERAGE SERVICE (additive): services/observation_coverage_service.reconcile_backfill_gaps(
   db,*,tenant,system,adapter,window,cadence_seconds) — interior-gap detection over a CLOSED
   historical window; reuses _finalize_gap_hash. detection_method="backfill_reconciliation".
5. GUARD: NO CHANGE NEEDED — origin/main's grc/guards/external_model.py ALREADY lists "adapters"
   in PRODUCT_PACKAGE_DIRS (confirmed post-checkout; my earlier read was the COV-002 branch state).
   So the new adapters/ package is already provably under the no-external-model guard. Nice.
6. BUILDER (STORY-407): scripts/demo_corpus_builder.py — deterministic (seeded) Bedrock NDJSON.gz
   in the S3 key layout to --out or --s3-bucket; envelope fidelity (FR-1), synthetic provenance
   (requestMetadata + accountId 999888777666, FR-6), deterministic gzip mtime (AC-3.1), run
   summary (FR-7). No hardcoded scenarios — all from manifest + corpus.
7. TESTS:
   - tests/test_story406_bedrock_adapter.py: discovery/window, parse multi-record, source_model
     map, INV-2 (observation branch provably never reads bodies), reconcile detects exactly the gap.
   - tests/test_story407_demo_corpus_builder.py: schema-fixture diff (AC-1.1/1.2), determinism
     byte-identical (AC-3.1), seed-change (AC-3.2), S3-layout mirror (AC-2.1), provenance (AC-6.1),
     and the E2E: build→adapter ingest→engine eval→exactly the 3 COVERED planted findings fire +
     zero on clean + gap attestation reports the gap (AC-4.1 gated, AC-5.1). UC-3/4/5 planted,
     asserted present-in-corpus but documented not-yet-firing.
8. VERIFY: python -m grc.guards.external_model green; full gate suite; two rehearsal runs identical.

## Deviations
1. Q5 design note originally claimed "one checkpoint per populated hour" — WRONG. STORY-406's
   emit_coverage writes one checkpoint PER RECORD, not per hour. Caught by the reviewer agent;
   corrected in the Decision Log (Q5). No correctness impact (the gap logic never relied on the
   false claim), but it surfaced the REAL bug below.
2. reconcile_backfill_gaps initially had no secondary sort key — tied watermark_timestamp rows
   (this exact manifest has 5 tied pairs) would reconcile non-deterministically on Postgres
   (SQLite's insertion-order preservation masked it in tests). Reviewer finding, CONFIRMED via
   direct inspection of the generated corpus. Fixed: sort on (watermark_timestamp,
   watermark_position); pinned by test_reconcile_backfill_gaps_is_deterministic_on_tied_timestamps.
   Conservative choice: fixed in-branch rather than deferred, since it directly threatens the
   story's core "byte-identical reproducibility" promise.
3. adapters/bedrock/source.py (new S3-layout reader) shipped with two real vulnerabilities,
   independently found and experimentally verified by both review agents: path traversal in
   LocalLogStore.read_bytes (no containment check) and a decompression bomb (gzip.decompress()
   has no output-size bound — verified 150KB compressed -> 339MB decompressed). Both fixed
   in-branch (key-shape validation + resolved-path containment; separate MAX_DECOMPRESSED_BYTES
   cap via incremental read) before commit — conservative choice, no partial-fix/defer option
   considered given these are exploitable in new product-path code, not pre-existing.
4. No specs/stories/STORY-407.md existed when the reviewer ran (spec content lived only in this
   notes file's Decision Log). Created retroactively per repo convention (CLAUDE.md story
   workflow) with full Given/When/Then ACs + traceability table, aligned to what was actually
   built rather than the original (partially obsolete) STORY-407-demo-corpus-builder.md request.
5. Known residual, NOT fixed (informational, out of this story's scope per security-auditor):
   ObservationGap has no UNIQUE constraint (unlike ObservationCheckpoint), a pre-existing gap in
   the coverage module generally that reconcile_backfill_gaps inherits but does not introduce or
   worsen. Recommend a follow-up FND against the module; not a blocker for this story.
