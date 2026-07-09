# STORY-410 — Operator Ingest CLI & Demo-Tenant Reset
Stage: standard

## Lifecycle
- [x] discover   (recon-first mandate from story: confirmed pipeline funcs exist, no CLI/reset utility does)
- [x] shape      (AskUserQuestion → Decision Log: click framework, slug-allowlist demo guard)
- [x] preview    (skipped — CLI-only, no UI per story Non-Goals)
- [x] plan
- [x] build
- [x] verify     (gates 1-7 green; security-auditor PASS; reviewer REQUEST CHANGES →
                   4 findings fixed (S3 parity test, Audit-family isolation test +
                   SQLite FK pragma, AuditEvent/Notification reset scope, discover()
                   error wrapping) → re-verified all gates green; change-debrief.html generated)
- [ ] sell       (not design-partner-facing this story; on request only)

## Discover — recon findings (mandatory per story instruction, verified against current main)

STORY-410 asks for a `saro ingest` CLI command chaining discover → replay_backfill →
engine audit → reconcile_backfill_gaps, plus `saro demo reset`. Recon (Explore agent)
confirmed:

- **Pipeline functions all exist and are proven** by the STORY-407 E2E test
  (`tests/test_story407_demo_corpus_builder.py:218`,
  `test_e2e_exactly_covered_findings_fire_and_gap_is_attested`):
  - `discover_object_keys` / `iter_backfill_records` — `adapters/bedrock/source.py`
  - `replay_backfill(db, records, config, *, submit=..., do_coverage=True, do_audit=True)`
    → `BackfillResult` — `adapters/bedrock/replay.py:135`
  - `reconcile_backfill_gaps(db, *, tenant_id, system_id, adapter_id, window_start,
    window_end, cadence_seconds)` — `services/observation_coverage_service.py:360`
  - `SARoEngine(db).run_output_audit(audit_id, raw_output, prompt, source_model)` —
    `engine.py:1097`
  - The test's `submit` callback (lines 241-251) is exactly the wiring `saro ingest`
    needs to replicate as first-class orchestration code, not a test-only closure.
  **Verdict: REUSE — no new pipeline logic. This story is CLI orchestration only.**

- **No `saro` CLI entry point exists anywhere in the main repo.** `main.py` is
  FastAPI-only (HTTP). Two in-repo CLI precedents: `saro-data-framework/src/
  saro_data_framework/cli.py` (click, subcommand groups) and `scripts/*.py`
  (argparse: `seed_demo_tenant.py`, `demo_corpus_builder.py`, `post_merge_cleanup.py`).
  **Verdict: BUILD.**

- **No tenant-reset utility, no `is_demo` column.** Demo tenant is identified today
  only by slug convention in `scripts/seed_demo_tenant.py:32-34` (`name="SARO Demo
  Tenant"`, `slug="saro-demo"`, `demo@saro-platform.io`). `Tenant` model
  (`models.py:44-61`) has no demo flag. **Verdict: BUILD**, guard via slug allowlist
  (Decision Log Q2) — no migration.

- **Duplicate-ingest idempotency is already structural**, not something this story
  needs to add: `ObservationCheckpoint` has `UNIQUE(tenant_id, system_id, adapter_id,
  watermark_position)` (`models.py:749`); `replay_backfill` catches the IntegrityError
  on a repeat cursor and increments `audits_skipped_duplicate` instead of re-auditing
  (`adapters/bedrock/replay.py:166-187`). Gap reconciliation dedupes by
  `(tenant, system, adapter, gap_start, detection_method)` before insert
  (`observation_coverage_service.py:420-432`) — no unique constraint backs it (this is
  the known residual STORY-409/FR-4.2 fixes later; out of scope here per STORY-410
  Non-Goals: "no scheduling/daemon", nothing about touching ObservationGap).
  **AC-3.1 resolved: option (a), naturally idempotent — no new dedupe code required,
  only a test pinning the behavior.**

- `Audit` model itself has no unique constraint on `(tenant_id, request_id)` — the
  idempotency boundary is the checkpoint/cursor, not the audit row. Re-running the
  same corpus produces the same checkpoints (duplicates absorbed) and therefore no
  new `submit()` calls, therefore no new Audit rows. Confirmed by reading
  `replay.py:166-187` directly, not inferred.

## Decision Log
Q1 CLI framework (owner)? → **click.** Matches `saro_data_framework/cli.py`'s existing
  subcommand-group pattern (`saro ingest ...`, `saro demo reset ...`); better ergonomics
  for nested subcommands and typed options than argparse, and it's already a repo
  dependency so no new package.

Q2 Demo-tenant structural guard, no `is_demo` column exists (owner)? → **Slug
  allowlist, no migration.** A module-level constant (or env-overridable config)
  `DEMO_TENANT_SLUGS = {"saro-demo"}` matching `seed_demo_tenant.py`'s existing
  convention. `saro demo reset` resolves the tenant by id, looks up its slug, and
  refuses (non-zero exit, no delete) unless the slug is in the allowlist — there is no
  flag combination that bypasses this (AC-4.1: no `--force` escape hatch, per spec).
  Keeps the story schema-change-free; if a second demo tenant is ever needed the
  allowlist just grows.

Q3 Re-run/idempotency behavior (AC-3.1, informed by recon not interview)? →
  **(a) idempotent**, already true by construction (see Discover). `saro ingest` run
  twice on the same corpus produces zero new findings/checkpoints/gaps; pin with a
  test that asserts row counts are unchanged after a second run, not a new dedupe
  mechanism.

## Plan (ordered by tweak-likelihood)

1. **CLI surface (tweak-likely):** `cli.py` at repo root (or `scripts/saro_cli.py` —
   confirm which during BUILD by checking for an existing `if __name__` convention;
   default to repo-root `cli.py` since this is a first-class operator surface, not a
   one-off script) — `click` group `saro` with subcommands `ingest` and `demo reset`.
   Verify: `python cli.py --help` shows both subcommands.
2. **`saro ingest` orchestration (FR-1):** wraps `discover_object_keys` →
   `iter_backfill_records` → `replay_backfill(..., submit=<run_output_audit per
   record>)` → `reconcile_backfill_gaps`, parameterized by `--adapter`, `--source`,
   `--tenant`, `--window`, `--dry-run`. Verify: `pytest tests/test_cli_ingest.py -k
   local_source_parity -q` reproduces STORY-407 E2E's exact findings/gap/
   coverage_attested state (AC-1.1).
3. **S3 source parity (FR-1 AC-1.2):** same command against `--source s3://...` using
   the existing `S3LogStore`. Verify: `pytest tests/test_cli_ingest.py -k
   s3_source_parity -q` (moto-mocked S3, matching STORY-407's test conventions).
4. **Failure/partial-batch handling (AC-1.3):** non-zero exit + failing object key in
   the error message; objects ingested before the failure reported as ingested in the
   summary. Verify: `pytest tests/test_cli_ingest.py -k partial_batch_failure -q`.
5. **Run summary + `--json` (FR-2):** counts, findings grouped by category with
   requestId + timestamp, gaps, `coverage_attested`, elapsed time. Verify: `pytest
   tests/test_cli_ingest.py -k summary_output -q` (both text and `--json` schema).
6. **Re-run idempotency test (FR-3, AC-3.1):** run twice, assert unchanged row counts.
   Verify: `pytest tests/test_cli_ingest.py -k rerun_idempotent -q`.
7. **`saro demo reset` (FR-4):** slug-allowlist guard (refuses non-demo tenant, no
   bypass flag), `--yes` requirement (dry-preview without it), deletes findings/
   dispositions/checkpoints/gaps scoped to `tenant_id`. Verify: `pytest
   tests/test_cli_demo_reset.py -k refuses_non_demo_tenant -q` and `-k
   requires_yes_flag -q`.
8. **Two-tenant isolation test (AC-4.3, security-relevant):** seed two tenants
   (one demo, one not — reset targets the demo one), assert the other tenant's rows
   are byte-for-byte untouched. Verify: `pytest tests/test_cli_demo_reset.py -k
   tenant_isolation -q`.
9. **Reset → re-ingest parity (AC-4.4):** reset then re-ingest same corpus/seed,
   assert identical to a first-run ingest. Verify: `pytest tests/test_cli_demo_reset.py
   -k reset_reingest_parity -q`.
10. **Guard cleanliness (FR-5):** confirm new CLI code makes zero hosted-model calls
    and never passes bodies into coverage code paths. Verify: `python -m
    grc.guards.external_model` (STORY-336 guard) stays green; grep-based test asserting
    the CLI module imports only `adapters`/`services`/`engine`, no provider SDKs.
11. **Full gate suite (close):** ruff, mypy, pytest unit/integration/regression,
    quality ratchet, bandit — see engineering-standards.md gates 1-7.

## Deviations
1. Findings are attributed via a request-id/timestamp index captured by a thin
   `_tracking_submit` wrapper around the real `_default_submit`, not by reading the
   engine's private `_sample_findings` attribute (which is how STORY-407's own test
   captures findings — appropriate for a test, not production orchestration).
   `saro ingest` uses the actual production submit path (persists real Audit/
   ScanReport/AuditTrace rows) and reads findings back from the persisted
   `AuditTrace` rows the TRACE View itself reads. Same findings fire either way.
2. Pre-commit correction: an early draft computed `coverage_attested` from "did any
   gap exist" rather than calling the real `coverage_report()`. Wrong — a window can
   be fully attested (≥1 observation recorded) AND contain a disclosed gap; that's
   the point of gap attestation. Caught by re-reading
   `services/observation_coverage_service.py`'s own docstring before commit; fixed
   to call `coverage_report()` per observed system_id.
3. `tests/_sqlite_for_update_shim.py` — SQLite can't parse the Postgres-only
   `SELECT ... FOR UPDATE` `routers/scan.py`'s `_persist_traces` uses for real
   concurrent-write serialization. Test-only monkeypatch strips the clause,
   consistent with conftest.py's existing PG_UUID/PG_JSON dialect shims.
   Production code unchanged.
4. CLI file location: repo-root `cli.py` (alongside main.py/engine.py/database.py),
   not scripts/ — first-class operator surface, invoked `python cli.py ingest ...`.
   No pyproject.toml/setup.py exists to wire a pip-installable console-script entry
   point; out of scope, noted rather than silently added.
5. AC-1.2 (S3 parity) initially covered by unit-level backend-selection only
   (`_make_store` returns S3LogStore for `s3://...`) — no live/mocked round-trip,
   since `moto` isn't a project dependency (STORY-407's suite has none either).
   **reviewer flagged this as a MAJOR gap** (plan promised a moto-mocked test that
   was silently dropped). Fixed: added `test_s3_source_parity`, a full ingest run
   against a fake boto3-shaped client (`S3LogStore`'s existing injectable `client`
   param — no new dependency), proving identical findings/gap/coverage_attested vs.
   the local-source path.
6. AC-4.3 (tenant isolation) initially only seeded ObservationCheckpoint/
   ObservationGap/Disposition — never the Audit family. **reviewer flagged this as
   MAJOR**: `demo_reset`'s bulk `.delete()` of Audit relies on DB-level
   `ON DELETE CASCADE` to clear ScanReport/AuditMetadata/AuditTrace (bulk delete
   bypasses ORM-level cascade), and the story itself calls this "load-bearing given
   the previously found cross-tenant timeline leak" — the highest-risk table family
   was untested. Also: SQLite doesn't enforce FKs (or cascade) without
   `PRAGMA foreign_keys=ON`, so even a correct assertion could have passed
   vacuously. Fixed: enabled the pragma on the test engine, extended
   `_seed_tenant_data` to seed Audit+ScanReport+AuditMetadata+AuditTrace (+
   AuditEvent+Notification, see #7) for both tenants, and asserted both that the
   demo tenant's full family is gone (cascade proof) and the other tenant's
   survives untouched.
7. **reviewer minor finding:** `demo_reset` didn't clear `AuditEvent`/`Notification`
   rows, undermining AC-4.4's "reset → re-ingest is identical to a first-run
   ingest" claim for any rehearsal that includes a disposition/acknowledgment step
   (which writes AuditEvent rows via the self-audit spine). Fixed: added both to
   `demo_reset`'s tenant-scoped delete set.
8. **reviewer minor finding:** `discover_object_keys(...)` in `_run_ingest` was
   uncaught — a source-level failure (bad bucket, permissions) would surface as a
   raw traceback instead of AC-1.3's promised clear operator-facing message. Fixed:
   wrapped in try/except raising `CliError`; pinned by
   `test_discover_failure_is_a_clear_cli_error`.
9. **reviewer minor/accepted, no code change:** flagged the correlation-ID logging
   gap (no structured request-scoped logging in cli.py) as relevant to STORY-409's
   future daemon-mode design, not a blocker here — deferred to that story.
   Also flagged the three sibling story spec files (408/409/411) as scope beyond
   "STORY-410 implementation" — confirmed intentional: filed in the same session
   per the operator's stated build sequence, markdown-only, no behavior change.
10. **Round 2 review (REQUEST CHANGES) — process gap, not a code defect:** the two
    real bugs fixed in items 7/8 (`AuditEvent`/`Notification` leak,
    unguarded `discover_object_keys`) closed without going through the FND ledger,
    despite the repo's own "no bug fix without a regression test" rule and the
    FND-039..047 precedent of logging reviewer-found bugs within the same PR cycle.
    Fixed: filed FND-048 (AuditEvent/Notification leak) and FND-049 (discover
    traceback), each with a dedicated `tests/regression/test_fnd_0??_*.py` pinning
    test, `manifest.yaml` entry, and `quality/findings.md` row, matching the
    existing format exactly. Round 3 (scoped closure check): reviewer confirmed
    both tests are non-vacuous, exercise the real CLI entry points, and the
    manifest/ledger cross-consistency tests pass. **Final verdict: APPROVE.**
