# STORY-COV-002 — Live observation-checkpoint emission (COV-001 AC-1, un-deferred)
Stage: standard

## Lifecycle
- [x] discover   (reframe below — the "STORY-406 Bedrock adapter" premise was wrong for SARO)
- [x] shape      (interview → Decision Log; owner picked all-paths / coalesce / opportunistic-sweep)
- [x] preview    (skipped — backend emission wiring; no new UI surface)
- [x] plan
- [x] build
- [x] verify    (change-debrief.html regenerated; independent reviewer + security-auditor below)
- [ ] sell       (n/a)

## Review outcomes (both agents)
- security-auditor: PASS (INV-2 enforced every path; tenant isolation intact; fail-open; no new write surface).
- reviewer: REQUEST-CHANGES → ALL resolved in-PR:
  - SF1 (session-poison race): record_checkpoint wrapped add→flush→commit in try/except IntegrityError
    → rollback → None (collision surfaced at AUTOFLUSH, not just commit — the FND-047 test caught that).
    Logged FND-047 (pinned) + ledger + manifest.
  - SF2 (unbounded sweep): detect_gaps now GROUP BY (tenant,system,adapter) max(watermark) DB-side;
    only stale keys fetch a row. NOT a recency filter (would hide the stale keys we must detect).
  - SF3 (quiet-tenant honesty): coverage_report adds observation_events + coverage_attested + caveat;
    methodology text discloses emission-driven detection. Pinned by test_quiet_window_is_not_attested.
  - Nits: docstring throttling wording fixed; added concurrent-collision + quiet-window body tests.

## Discover — the reframe
COV-001 deferred AC-1's "live-adapter heartbeat emission" pending STORY-406 (a
Bedrock adapter contract). Recon shows that dependency was a mis-frame: SARO has
no streaming poller of client model endpoints, and by its non-negotiables it
never calls external models. SARO's REAL observation event is inbound — a client
pushes an AI output and SARO audits it:
  - grc/orchestrator.run_audit_by_id  (evidence-backed GRC evaluation; HAS system_id;
    already the hook site for DISP-001 + MTR-001, fail-open pattern established)
  - routers/ingest._run_audit_background (single-output SDK ingest; has source_model +
    tenant, NO system_id)
Each completed audit IS proof SARO was observing that system at that time. So AC-1
is implementable NOW against the real architecture — no fictional adapter needed.
The checkpoint interface record_checkpoint() already exists and is unit-tested;
this story WIRES it to the live audit path.

## Decision Log
Q1 emission sites (owner)? → ALL live audit paths. grc/orchestrator.run_audit_by_id +
  routers/ingest._run_audit_background + routers/scan.{scan_batch, scan_data_batch}.
  Each hooks fail-open, matching the established DISP/MTR pattern (local import, try/except,
  never block or add failure to the audit).
Q2 granularity (owner)? → COALESCE into time buckets. watermark_position = "obs:{floor(ts /
  saro_coverage_bucket_seconds)}"; the existing UNIQUE(tenant,system,adapter,watermark) makes
  the 2nd+ audit in a bucket an idempotent no-op. New config saro_coverage_bucket_seconds=60
  (< cadence 300 so an active window always leaves a heartbeat).
Q3 gap sweep (owner)? → ALSO trigger an opportunistic detect_gaps sweep. Fires ONLY when a
  fresh checkpoint (new bucket) is created — so it's throttled to once/bucket/system, not
  once/audit. Fail-open, config-gated (saro_coverage_auto_sweep=True). Residual (documented):
  a fully-quiet tenant never self-sweeps — the existing POST /detect-gaps + a future scheduler
  cover that; this is opportunistic, not a scheduler.

Q4 identity mapping (mine; INV-2)? → system_id/adapter_id per site, ALL passed through a new
  _safe_ident() token-guard so free text can NEVER reach the evidence store (INV-2):
    - GRC:            system_id = sys_id or "unknown",     adapter_id = "grc-evaluation"
    - ingest:         system_id = source_model (closed vocab), adapter_id = "sdk-ingest"
    - scan_batch:     system_id = dataset_name (sanitized), adapter_id = "batch-scan"
    - scan_data_batch:system_id = model_type   (sanitized), adapter_id = "batch-scan"
  _safe_ident: if value fails ^[A-Za-z0-9:._\-+/=]{1,255}$, collapse to "op_"+sha256[:16]
  (opaque, deterministic — still coalesces per distinct source, never leaks content).

Q5 honesty of the coverage claim (mine; compliance-guard)? → SARO is push-model: a gap means
  SARO received NO observations for that (system, adapter) for > cadence. It is NOT a claim
  the client's system was down. Update coverage_report methodology text + service docstring to
  say exactly this. No schema change (emission rides existing columns).

## Plan (ordered by tweak-likelihood)
1. DATA/CONFIG: add saro_coverage_bucket_seconds (60) + saro_coverage_auto_sweep (True) to config.py.
   Verify: python -c "from config import settings; print(settings.saro_coverage_bucket_seconds)"
2. SERVICE: observation_coverage_service.emit_observation() + _safe_ident()/_SAFE_TOKEN.
   Coalesce + fail-open sweep. Update coverage_report methodology text + module docstring (Q5).
   Verify: pytest tests/test_cov002_live_emission.py -q (new)
3. WIRING (mechanical, fail-open, matches MTR): 4 call sites emit a checkpoint post-audit.
   Verify: integration test asserts a checkpoint row after ingest + after run_audit_by_id.
4. TESTS: tests/test_cov002_live_emission.py — coalescing dedup, _safe_ident INV-2 hashing,
   sweep opens a gap for a quiet system, fail-open (emit swallows a broken db), per-site wiring.
   Verify: full gate suite.

## Deviations
None yet.
