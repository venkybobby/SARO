# SARO Database Schema — Live Supabase Audit

Project: `SARO` (`fktfhtygvwqlmoazmhdf`, `us-west-1`, Postgres 17.6). Row counts
below are live (`pg_stat_user_tables.n_live_tup`, queried 2026-07-29), cross-checked
against `models.py` and the 51-file migration history in
`migrations/` (tracked separately in the app's own `schema_migrations` table,
distinct from Supabase's own migration-history tool, which only shows the
9 migrations applied out-of-band during earlier sessions).

**61 tables total. 33 have data, 28 are empty.** Per your request, each empty
table below is investigated against the actual router/model code — not just
listed — to distinguish "unused feature" from "broken feature" from
"genuinely dead code."

## Populated tables

| Table | Rows | Purpose |
|---|---|---|
| `audit_traces` | 1,661 | TRACE evidence rows — one per gate check/domain flag/rule application, hash-chained |
| `mit_risks` | 1,408 | Reference: MIT AI Risk Repository taxonomy |
| `sample_findings` | 775 | Per-sample Gate-3 domain-flag evidence |
| `audits` | 170 | Every scan/audit run (batch + single-output) |
| `scan_reports` | 132 | 1:1 with `audits` — the computed report JSON, scores |
| `observation_checkpoints` | 76 | Log-ingestion watermark reports from client adapters |
| `nist_ai_rmf_controls` | 72 | Reference: NIST AI RMF 1.0 subcategories |
| `ai_incidents` | 72 | Reference: AI incident corpus used for TF-IDF similarity matching |
| `audit_metadata` | 67 | 1:1 with `audits` — source model, ingestion method, S3 offload keys |
| `governance_rules` | 47 | Reference: cross-framework governance rule citations |
| `eu_ai_act_rules` | 41 | Reference: EU AI Act article-level obligations |
| `aigp_principles` | 28 | Reference: AIGP principle definitions |
| `schema_migrations` | 49 | The app's own migration-tracking table (see `database.py:apply_pending_migrations`) |
| `product_events` | 13 | First-party PHI-free product analytics |
| `observation_gaps` | 5 | Detected log-ingestion cadence gaps |
| `persona_permissions` | 4 | The 4 real personas — see [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md) |
| `demo_requests` | 3 | Public demo-signup form submissions |
| `tenants` | 3 | Tenant rows |
| `users` | 3 | User rows |
| `rule_pack_snapshots` | 2 | Immutable, hash-chained published rule-pack versions |
| `aims_documents` | 1 | AIMS ("Model Inventory" page) document lifecycle rows |
| `client_configs` | 1 | Enterprise client SSO/SCIM/MFA config |
| `evaluation_runs` | 1 | Offline evaluation-framework run history |
| `tenant_log_source_configs` | 1 | Cross-account Bedrock log-source binding (STORY-408) |
| `enhanced_traces` | 8 | Chain-of-thought / executive-summary cache per audit |
| `playing_with_neon` | 20 | **Not a SARO table** — a Supabase quickstart sample table auto-created by the Neon integration wizard; unrelated to the app, safe to ignore/drop |

## Empty tables — investigated

Grouped by why they're empty. Confidence noted per row: **Confirmed** (traced
to specific code/config), **Likely** (strong circumstantial evidence, not
100% traced), **Worth checking** (a real question raised by this audit, not
yet answered).

### Feature exists end-to-end, simply never used yet (expected)

| Table | Why empty |
|---|---|
| `github_integrations`, `github_scan_results` | **Confirmed.** Requires a `super_admin` to call `POST /api/v1/github/configure` with a real PAT. Nobody has. |
| `evf_sme_engagements`, `evf_engagement_transitions`, `evf_validation_gates`, `evf_qco_registry`, `evf_publication_events`, `evf_expiry_notifications` | **Confirmed by design.** Per `docs/COMPLIANCE_CLAIMS_MATRIX.md`'s EVF section, no framework has entered External SME Validation yet (all four are "Internal Review Only" as of 2026-06-02). This isn't a bug — the business process these tables track hasn't started. |
| `grc_registry_entries`, `grc_registry_audit`, `grc_evidence_records` | **Confirmed.** Endpoints exist (`routers/grc_registry.py`), require an explicit `POST /api/v1/grc/registry` call; no frontend page found calling this router, so nothing has ever been registered. |
| `tenant_risk_configs` | **Confirmed.** Only created via `PUT /api/v1/risk-config`; engine falls back to defaults until a tenant customizes it. No tenant has. |
| `tenant_rule_pack_pins` | **Confirmed.** Only created when a tenant explicitly pins a rule-pack version via its endpoint; nobody has. |
| `hf_sample_queue` | **Confirmed.** Only populated by the external `saro-data-framework`/`saro_data` tooling pulling HuggingFace datasets — not part of the live scan path. |
| `pilot_feedback` | **Confirmed.** Only created via `POST /api/v1/feedback`; nobody has submitted in-product feedback yet. |
| `dispositions`, `disposition_transitions` | **Likely.** Endpoint requires a user to acknowledge/remediate/escalate/waive a specific finding — this is a newer, more formal workflow (`STORY-DISP-001`) layered on top of the simpler `remediation.py` flow, which does have usage patterns elsewhere. Plausible nobody has used the formal disposition flow yet. |
| `insight_actions` | **Likely.** `GET /api/v1/insights` derives insights live without needing this table; it's only written when a user explicitly accepts/snoozes/dismisses one via `POST .../action`. |
| `risk_metadata` | **Likely.** Lazily created only on the first `PATCH /api/v1/risks/{id}` (owner/status override). The risk register reads audits directly and only joins this table when present. |
| `compliance_readiness_items` | **Likely.** The readiness checklist appears to combine derived (computed-on-the-fly) items with manually-toggled ones; rows here only get created when an admin manually toggles an item via `PUT /api/v1/compliance/readiness/{key}`. |
| `ai_systems`, `system_audits` | **Confirmed no frontend caller.** `routers/systems.py` has full CRUD, but no page in `frontend/src/pages/` was found calling `/api/v1/systems`. This is a backend-only feature right now — see §10 of the Feature Catalog on the 3 overlapping AI-inventory mechanisms. |

### Likely genuine gaps — worth a closer look

| Table | Issue |
|---|---|
| **`policies`** | **Confirmed dead-on-arrival.** `models.py`, `schemas.py` (`PolicyCreate`/`PolicyUpdate`/`PolicyOut`), and a full `services/policy_service.py` all exist — but a repo-wide check of all 47 router files found **no HTTP endpoint anywhere exposes this table**. It cannot receive data through the API in its current state, regardless of how long the app runs. If this feature (STORY-401, "governance policy trigger config") is meant to be live, a router needs to be written and mounted in `main.py`; if it was superseded, the model/schema/service should be removed rather than left as silent dead weight. |
| **`controls`, `control_framework_mappings`** | **Worth checking.** `main.py`'s startup sequence explicitly calls a control-library seed step (`scripts.seed_control_library.seed_controls`) on every boot. Given that, these tables being empty in the live DB is unexpected — either the seed script is failing silently, is gated behind a condition not currently met, or the live app hasn't been restarted since this seeding was added. Worth checking Fly.io/Railway deploy logs for seed-step errors. |
| **`registered_ai_systems`** | **Likely orphaned.** Created by migration `005_add_registered_ai_systems.sql` ("REM-002"), but no router in the current 47-file `routers/` directory was found referencing it. Likely superseded by one of the three newer inventory tables (`ai_systems`, `aims_documents`, or `grc_registry_entries`) and left behind. |
| **`usage_meters`, `usage_statements`, `usage_meter_idempotency`** | **Worth checking.** `routers/metering.py` can *read* and *issue statements*, but this audit did not find the scan/ingest pipelines (`scan.py`, `ingest.py`, `output_audit.py`) calling any metering *increment* function. With 170 audits already run, if metering were wired into the scan path you'd expect non-zero counts. Worth a direct check of whether `services/metering_service` is actually invoked from the audit-creation code paths. |
| **`observation_lag_samples`** | **Worth checking.** Its siblings `observation_checkpoints` (76 rows) and `observation_gaps` (5 rows) are populated by the same feature area and clearly working. Lag-sample aggregation (p50/p95/max latency per window) looks like it requires a separate scheduled/batch job that isn't currently running — the checkpoint/gap-detection endpoints don't appear to write to this table directly. |
| **`notifications`** | **Worth checking.** `routers/scan.py:61-115` dispatches a notification whenever `overall_risk_score` crosses 0.60/0.80. With 170 audits and 132 scan reports on record, zero notifications is either because none of those scores actually crossed the threshold (plausible, not verified) or the dispatch path is silently failing. A direct query of `scan_reports.report_json` risk scores would resolve this in one step if you want it checked. |

## Roles-related tables (see [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md) for full detail)

- `users.role` — DB-CHECK-constrained to `super_admin`/`operator` only (migration `044_users_role_check.sql`, FND-093 — this is the migration immediately preceding this audit).
- `users.persona_role` — free-text, no DB constraint, only app-layer-validated through one endpoint.
- `persona_permissions` — 4 rows: `compliance_lead`, `risk_officer`, `ai_auditor`, `admin`. No row for `super_admin` or `operator` (they use `.role` checks instead, not persona lookups) — meaning a user whose `persona_role` happens to be set to `"super_admin"` (this exists in the live data — see ROLES doc) gets no match in this table.

## Migration system note

Two separate mechanisms exist and can drift from each other:
1. **The app's own migration runner** (`database.py:apply_pending_migrations`),
   tracked in the `schema_migrations` table (49 rows, files `000_...` through
   `044_users_role_check.sql`), globs only `*.sql` files — two `.py`-based
   migrations (`008_remediation_note.py`, `009_hash_chain_columns.py`) exist
   in the same directory but are **never auto-applied**; they require manual
   execution.
2. **Supabase's own tracked migration history** (the `list_migrations` tool),
   which shows only 9 entries — a different, smaller subset applied directly
   via the Supabase MCP/dashboard in past sessions, not the full 51-file
   history. These two systems are not the same ledger; don't assume one
   implies the other is up to date.

Additionally, `database.py`'s `ensure_app_schema()` runs a "self-heal" step on
every startup that **drops and recreates** any table not in a `_SAFE_ALTER_COLS`
allowlist if its live columns don't match the ORM's expected columns — this
is how schema drift gets silently repaired (or, for tables outside the safe
list, silently destroyed and rebuilt empty) without a human noticing.
