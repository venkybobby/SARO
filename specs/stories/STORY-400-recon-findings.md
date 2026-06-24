# STORY-400 — Recon Spike Findings (Epic 14, Phase 1)

**Status:** done · read-only · no production code changed
**Date:** 2026-06-23
**Purpose:** Resolve the assumptions that decide whether STORY-401 *extends* or *creates*,
and whether STORY-402 has a real substrate to dispatch into. Each downstream story's
create-vs-extend decision below is now determinate.

---

## 1. Policy model — CREATE (none exists)

No policy/trigger-config governance entity exists. Closest entities:

| Entity | File | What it holds | Tenant-scoped? |
|---|---|---|---|
| `TenantRiskConfig` | [models.py:684](../../models.py) | Gate-3 domain weights, keyword suppressions, weight ceiling | ✓ `tenant_id` FK, unique (1:1 tenant) |
| `ClientConfig` | [models.py:414](../../models.py) | SSO/SCIM/IDP/MFA enterprise identity config | ✓ 1:1 tenant |

`TenantRiskConfig` is **scoring tuning**, not per-policy trigger/routing config — conceptually
distinct from what Epic 14 needs (`trigger_mode`, `latency_budget_ms`, `on_timeout`,
`sample_rate`, `policy_version` *per policy*, not per tenant).

**Decision:** STORY-401 **creates a new `Policy` model** (one row per policy, tenant-scoped),
not an extension of `TenantRiskConfig`.

## 2. Evaluation callable — clean seam, no refactor needed

Entry: `engine.run_audit(batch, audit_id) → AuditReportOut` ([engine.py:889](../../engine.py)).
4-gate pipeline, each gate returns an immutable `_GateResult` (decision + rationale in `.details`):

- Gate 1 data quality — `_gate1_data_quality` ([engine.py:1121](../../engine.py))
- Gate 2 fairness — `_gate2_fairness` ([engine.py:1187](../../engine.py))
- Gate 3 risk classification — `_gate3_risk_classification(batch, risk_config)` ([engine.py:1282](../../engine.py)) ← already parameterized by config
- Gate 4 compliance mapping — `_gate4_compliance_mapping(flags)` ([engine.py:1493](../../engine.py))

**Decision:** STORY-402's router dispatches by wrapping the `(batch, policy) → (decision, rationale)`
call around `run_audit`/the gate seam. Gates return values (not mutate), so a dispatcher can
intercept and route cleanly. No engine refactor required.

## 3. Async substrate — FastAPI BackgroundTasks (Phase-1), queue deferred

No Celery/RQ/Redis queue. `fastapi.BackgroundTasks` is the established async mechanism
(`routers/evaluations.py`, `routers/ingest.py`, `routers/demo.py`, `routers/hf_processor.py`),
each spawning a thread with its own DB session.

- **Adequate** for Phase-1 mirror/sample enqueue (non-blocking return).
- **Not** sufficient for sustained 500/s bursty peak (thread-based, no persistence/retry/dead-letter).

**Decision (recorded here, built later per pack §3):** STORY-402 uses `BackgroundTasks` as the
enqueue substrate for Phase 1; a durable queue (Celery+Redis / SQS / Pub-Sub) is the recommended
Phase-2 upgrade for high-throughput. Flagged, not built in this pack.

## 4. Tenant pattern — tenant_id FK + Postgres RLS + app-layer filter

Three-layer pattern that STORY-401/404 must match exactly:

1. **FK column** `tenant_id UUID FK tenants.id ondelete=CASCADE` on every audit-scoped table
   (`Audit` [models.py:96](../../models.py), `AuditTrace` [models.py:260](../../models.py), `ScanReport`).
2. **RLS policy** `USING (tenant_id::text = current_setting('app.current_tenant', true))` — see
   `migrations/026_create_compliance_readiness_items.sql`.
3. **App-layer capture** at insert from `current_user.tenant_id` (`routers/scan.py:273`).

## 5. Synthetic-PHI fixture — does NOT exist for product tests; build first

Only an **offline** PII redactor exists: `qa_lab/labeling.py:redact_pii` (email/SSN/IPv4/phone/card
regexes), tested in `tests/test_story338_offline_labeling.py`. That is qa_lab-only (STORY-336
keeps it out of the product path).

**Decision:** STORY-403 requires a new shared product fixture
`tests/fixtures/synthetic_phi.py` (HIPAA-18-labeled synthetic records, never real member data),
**built before** the redaction sidecar tests. Shared by 403 redaction tests + later shadow-mode eval.

---

## Infrastructure notes

- **Migrations:** numbered `migrations/NNN_*.sql`, applied by `apply_pending_migrations()`
  ([database.py:202](../../database.py)), tracked in `schema_migrations` (SHA-256 checksum,
  modification-locked by trigger). **No Alembic.** Latest committed on `main` = `025`;
  `026_create_compliance_readiness_items.sql` is already claimed by in-flight work on
  other branches (chub / trace-view), so STORY-401 takes **`027`** to avoid a collision
  when those merge. → STORY-401 ships a SQLAlchemy model + a numbered `027_*.sql` migration
  (not Alembic). Gaps are harmless: `apply_pending_migrations` globs+sorts whatever `*.sql`
  are present.
- **TRACE/audit writer:** `services/trace_service.py` (6-step timeline) +
  `services/hash_chain_service.py` (`build_event_payload`/`compute_event_hash`/`verify_chain`,
  SHA-256 chain). Persisted via `routers/scan.py:_persist_traces()` (per-event `event_hash`+`prev_hash`).
  → STORY-404 **extends** the existing hash-chain service for per-tenant chain heads + Parquet export.
- **Ingestion entry:** `POST /api/v1/scan` ([routers/scan.py:242](../../routers/scan.py)) → `BatchIn`
  (≥50 samples) → `run_audit` → `_persist_traces`.

## Downstream determinacy

| Story | Decision | Adaptation from pack text |
|---|---|---|
| 401 | **CREATE** new `Policy` model + `027_*.sql` migration | "Alembic" → SARO numbered-SQL migration |
| 402 | Wrap gate seam; `BackgroundTasks` enqueue | queue upgrade flagged for Phase 2 |
| 403 | Build `tests/fixtures/synthetic_phi.py` first | fixture is a new shared asset |
| 404 | **EXTEND** `hash_chain_service` for per-tenant chains + Parquet | reuse, don't reinvent crypto |

**Acceptance check:** all five items answered; no production code changed. ✓
