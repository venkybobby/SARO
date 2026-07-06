# STORY-RPV-001 — Versioned, Immutable Rule-Pack Snapshots
Stage: standard

## Lifecycle
- [x] discover   (recon: read evf_qco_registry/evf_publication_events pattern (mig 012),
                  services/hash_chain_service.py canonical hash, rule ORM models, migration
                  runner (sorted *.sql + schema_migrations checksums), SQLite test harness)
- [x] shape      (skipped brainstorm — STORY has ACs; interview → Decision Log below)
- [x] preview    (skipped — backend-only; UI for browsing versions is explicit out-of-scope)
- [x] plan
- [x] build
- [x] verify    (change-debrief.html generated)
- [x] sell       (n/a — not design-partner-facing this pass)

## Decision Log
Q1 hash primitive: reuse existing or invent new? → REUSE services/hash_chain_service
  compute_event_hash semantics (sha256(json.dumps({**payload,"prev_hash":prev or "GENESIS"},
  sort_keys=True))). Snapshot content_hash + chain hash use the same canonical-JSON sorted-keys
  discipline already proven in the audit chain; no new crypto.

Q2 snapshot lifecycle: draft-then-publish vs publish-on-create? → PUBLISH-ON-CREATE
  (append-only, like evf_publication_events). A snapshot row is frozen at insert; no mutable
  draft snapshot. Immutability = "no UPDATE/DELETE ever"; AC-2 trigger is BEFORE UPDATE OR DELETE.

Q3 immutability enforcement layer (SQLite harness can't run pg triggers)? → BOTH: service-layer
  guard (raises before any UPDATE/DELETE; unit-testable on SQLite) + DB trigger in migration 028
  (defense-in-depth on real Postgres; verified via Supabase MCP). Mirrors the evf split
  (app-enforced qco + trigger-enforced publication_events).

Q4 which rows are includable (AC-3)? → validation_status='SME_VALIDATED' only.
  DRAFT_UNVALIDATED in scope means publish REFUSED with a listing of blocking (table,id) rows.
  LEGACY_UNREVIEWED is includable-with-caveat behind config flag SARO_SNAPSHOT_INCLUDE_LEGACY
  (default TRUE; caveat text stored on the snapshot). The NIST table has no validation_status
  column so it is treated as LEGACY_UNREVIEWED (same flag + caveat).

Q5 content storage: full row JSON vs hash-only? → store per-framework row-id manifest with a
  per-row hash + counts in snapshot_manifest (JSON), NOT full rule text. content_hash covers the
  canonical serialization of the FULL included rows so tamper is still detectable; diff compares
  current working rows vs the snapshot manifest (ids + per-row hash).

Q6 semver: who sets the version? → caller supplies target semver; service validates format
  (rule_service.validate_semver) and that it is strictly greater than the latest published;
  auto-suggest next patch when omitted.

Q7 empty publish (AC edge)? → if canonical content_hash == latest published content_hash,
  REFUSE (no empty versions).

## Deviations
- DEV-1 (from reviewer B1): the story's Traceability cites migration
  `radar_scan1_validation_status_columns`, which lived only in Supabase, not the
  repo. The ORM models declared `validation_status` with no backing repo DDL, so a
  fresh deploy would 500 on publish (UndefinedColumn) or fail-closed everywhere.
  Conservative fix: exported the live radar columns migration into the repo as
  `migrations/029_radar_scan1_validation_status_columns.sql` (idempotent ALTER ADD
  COLUMN IF NOT EXISTS, faithful to the live DDL incl. NOT NULL DEFAULT
  'LEGACY_UNREVIEWED'). The aggressive option (also exporting the delta-DATA
  migration now) was declined — that is CHUB-011's companion task; only the schema
  is needed for the RPV-001 gate.

## Review outcomes (both agents, addressed in-PR)
- B1 (both): missing validation_status migration -> migration 029 added. PINNED by
  the live-schema check (columns confirmed present on Supabase) + existing gate tests.
- B2 (both): verify_chain trusted stored content_hash -> now re-derives
  _content_hash(manifest); manifest tampering flagged. PINNED:
  test_verify_chain_detects_manifest_tamper.
- S1 (reviewer): diff mislabeled status-retired rows as updated -> diff now uses the
  includable set. PINNED: test_diff_reports_status_retirement_as_retired.
- S2 (reviewer): chain order relied on created_at + random-UUID tiebreak -> now
  follows prev_hash->record_hash links (_ordered_chain), created_at only as a
  broken-chain fallback. PINNED: test_chain_order_follows_hash_links.
- S3 (reviewer): stale notes -> this section + stage checkboxes updated.
- Security-auditor VERDICT: PASS. Reviewer VERDICT: REQUEST-CHANGES -> all blockers
  and should-fixes resolved above; re-verify gates green before commit.
- N-items (rate limit on publish; include_legacy default True): accepted as-is —
  publish is super_admin/operator-gated; legacy-default confirmed by owner decision.
