# STORY-410 — Operator Ingest CLI & Demo-Tenant Reset

**Status:** done — see Traceability + Decision Log below (implementation-notes.md has the full Decision Log/Deviations)
**Status (original):** Ready for build — **DEMO-CRITICAL, build first**
**Depends on:** STORY-406 (adapter, merged), STORY-407 (source reader + builder, merged)
**Blocks:** SummitCare demo rehearsal
**Delivery rule:** Integrated into the single SARO repo.

## Recon first (mandatory, per STORY-407 lesson)

Before writing any code, recon current `main` for an existing operator entry point that chains `discover → replay_backfill → engine audit → reconcile_backfill_gaps`, and for any existing tenant-reset utility. If either exists, reuse and report — do not rebuild. The only currently known executable path is the STORY-407 E2E test, which is not an operator surface.

## Problem Statement

The full pipeline is proven only inside a pytest test. The demo (and any future pilot operation) needs a first-class command an operator can run live: ingest a corpus from S3 or local disk, evaluate it, reconcile coverage, and print a human-readable summary. Separately, rehearsals require returning the demo tenant to a clean state deterministically; today the only state reset lives inside the E2E test harness.

## Goals

1. One command runs the entire backfill pipeline against an S3 or local source and exits non-zero on any failure.
2. A summary output that doubles as the demo operator's verification sheet (records, findings by category with requestIds, gaps, attestation status).
3. A tenant-scoped reset command safe enough that it structurally cannot touch a non-demo tenant.

## Non-Goals

- No scheduling/daemon mode (STORY-409).
- No cross-account auth (STORY-408); source is local path or a bucket the current credentials can already read.
- No new rules, no UI changes.

## Functional Requirements

### FR-1: `saro ingest` command (P0)
```
saro ingest --adapter bedrock --source {s3://bucket[/prefix] | ./path} \
            --tenant <tenant_id> --window <ISO8601>..<ISO8601> [--dry-run]
```
- Chains: source discovery → bounded read/gunzip → `replay_backfill()` → engine `run_output_audit()` per record → `reconcile_backfill_gaps()` — all existing code; this story adds orchestration only.
- `--dry-run`: discover and parse, report counts, write nothing.

**AC-1.1:** Given the STORY-407 canonical corpus in a local directory, when `saro ingest` runs, then the resulting findings, gap, and `coverage_attested` state are identical to what the STORY-407 E2E test asserts (UC-1, UC-2, UC-6 fire; exactly one gap containing the declared missing hour).
**AC-1.2:** Given the same corpus in S3, same result.
**AC-1.3:** Given an unreadable source, malformed object, or engine error, the command exits non-zero with a clear message identifying the failing object key; no silent partial success. Partial-batch behavior: objects already ingested before the failure are reported in the summary as ingested.
**AC-1.4:** `--dry-run` performs zero writes (verified by test asserting no new findings/checkpoints/gaps rows).

### FR-2: Run summary (P0)
**AC-2.1:** On success, print: source, tenant, window, objects discovered/read, records parsed, findings count grouped by risk category with each finding's `requestId` and timestamp, gaps found (with windows), `coverage_attested` value, and elapsed time. Machine-readable variant via `--json`.

### FR-3: Re-run behavior (P0)
**AC-3.1:** Running the same ingest twice against the same tenant either (a) is idempotent (no duplicate findings/checkpoints), or (b) refuses with a message directing to `saro demo reset` — pick whichever the existing engine/coverage persistence semantics support with least new code, document the choice in the spec traceability table. Do NOT silently create duplicates; a test pins the chosen behavior.

### FR-4: `saro demo reset` command (P0)
```
saro demo reset --tenant <tenant_id> --yes
```
- Deletes findings, dispositions, observation checkpoints, and gaps for the given tenant only.

**AC-4.1:** Refuses to run unless the tenant is flagged as a demo tenant (structural safeguard — a `is_demo` flag or a configured demo-tenant allowlist; NOT a `--force` override). There is no flag combination that resets a non-demo tenant.
**AC-4.2:** Requires `--yes`; without it, prints what would be deleted and exits.
**AC-4.3:** Tenant isolation test: seed two tenants with data, reset one, assert the other is byte-for-byte untouched. (This is load-bearing given the previously found cross-tenant timeline leak — treat as a security-relevant test, not a convenience test.)
**AC-4.4:** After reset + re-ingest of the same corpus with the same seed, results are identical to a first-run ingest (the rehearsal loop this exists for).

### FR-5: Guard cleanliness (P0)
**AC-5.1:** STORY-336 CI guard stays green; new CLI code makes no hosted-model calls. INV-2 untouched: the CLI never passes bodies into coverage code paths.

## Verification (all-or-nothing)
- [ ] AC-1.1/1.2 parity with E2E assertions, both backends
- [ ] Idempotency-or-refuse behavior pinned by test (AC-3.1)
- [ ] Two-tenant isolation test for reset (AC-4.3)
- [ ] Full existing suite passes unmodified; guard green
- [ ] Manual: full demo rehearsal loop (reset → ingest → verify on screens → reset → ingest → identical) run twice

## Open Questions (blocking) — resolved
1. CLI framework: **click** — matches `saro-data-framework/src/saro_data_framework/cli.py`'s existing subcommand-group pattern; no existing top-level `saro` entry point (main.py is FastAPI-only). Repo-root `cli.py`, alongside main.py/engine.py/database.py.
2. Duplicate-ingest persistence semantics: **(a) idempotent**, already true by construction — `ObservationCheckpoint` has `UNIQUE(tenant_id, system_id, adapter_id, watermark_position)`; `replay_backfill` catches the collision and skips re-auditing. No new dedupe code needed.
3. Demo-tenant structural guard (no `is_demo` column exists): slug allowlist (`DEMO_TENANT_SLUGS = {"saro-demo"}`), matching `scripts/seed_demo_tenant.py`'s existing convention — zero schema change.

## Traceability (AC → test → file)

| AC | Test | File |
|---|---|---|
| AC-1.1 | `test_local_source_parity` | `tests/test_cli_ingest.py` |
| AC-1.2 | `test_source_selection_local_vs_s3`, `test_s3_source_parity` | `tests/test_cli_ingest.py` |
| AC-1.3 | `test_partial_batch_failure_names_failing_key`, `test_discover_failure_is_a_clear_cli_error` | `tests/test_cli_ingest.py` |
| AC-1.4 | `test_dry_run_writes_nothing` | `tests/test_cli_ingest.py` |
| AC-2.1 | `test_local_source_parity` (asserts `--json` shape) | `tests/test_cli_ingest.py` |
| AC-3.1 | `test_rerun_is_idempotent` | `tests/test_cli_ingest.py` |
| AC-4.1 | `test_refuses_non_demo_tenant`, `test_no_flag_bypasses_the_demo_tenant_guard` | `tests/test_cli_demo_reset.py` |
| AC-4.2 | `test_requires_yes_flag_preview_only` | `tests/test_cli_demo_reset.py` |
| AC-4.3 | `test_tenant_isolation_reset_leaves_other_tenant_untouched` | `tests/test_cli_demo_reset.py` |
| AC-4.4 | `test_reset_then_reingest_matches_first_run` | `tests/test_cli_demo_reset.py` |
| AC-5.1 | `test_cli_module_is_guard_clean` | `tests/test_cli_ingest.py` |
| FND-048 (review-found) | `test_demo_reset_deletes_audit_event_and_notification_rows` | `tests/regression/test_fnd_048_demo_reset_clears_audit_event_and_notification.py` |
| FND-049 (review-found) | `test_discover_object_keys_failure_is_a_cli_error_not_a_traceback` | `tests/regression/test_fnd_049_ingest_discover_failure_is_clear_error.py` |
