# SARO — Canonical Architecture of Record

> **Status:** v1.0 · CANONICAL · Owner: Jordan Lee (Backend/Infra) · Reviewer: Venky (Lead) · 2026-06-12
> PT-005 / PT-012. This is the **single source of truth** for SARO's infrastructure. Any document
> that references the stack must match this file or be marked SUPERSEDED in `DOCUMENT_REGISTER.md`.

## Stack of record

| Layer | Service | Notes |
|---|---|---|
| Backend API | **Fly.io** — FastAPI + uvicorn (`saro-backend`) | `fly.toml`, `auto_stop_machines = 'off'`, health-check timeout 5s |
| Frontend | **Fly.io** — React/Vite (`sarofrontend`) | `frontend/fly.toml`, `auto_stop_machines = 'off'` |
| Database | **Supabase PostgreSQL** | Row-Level Security for tenant isolation |
| Evidence staging | **Postgres staging tables** | No Redis dependency for evidence persistence |
| Cache | Redis (optional) | Non-evidence paths only |
| CI/CD | GitHub Actions → `flyctl deploy` (`.github/workflows/deploy.yml`) | Health smoke after deploy |

Primary region: `dfw`. The stack is **frozen** on Fly.io + Supabase per the vendor-continuity plan
(PT-012); a provider change requires a documented exception with customer notice (see
`VENDOR_CONTINUITY_PLAN.md`), never a silent migration.

## Superseded / legacy references (do NOT treat as current)

| Legacy reference | Status | Canonical replacement |
|---|---|---|
| Railway (`saro-production-*.up.railway.app`) | SUPERSEDED — interim host during migration | Fly.io `saro-backend` |
| Koyeb | SUPERSEDED — earliest deployment target | Fly.io `saro-backend` |
| Neon PostgreSQL | SUPERSEDED — migrated 2026-05-08 | Supabase PostgreSQL |

Documents still containing legacy references (`deployment-context.md`, `MIGRATION_RUNBOOK.md`,
interim DPAs) carry a SUPERSEDED header pointing here; see `DOCUMENT_REGISTER.md`.

## Health & verification

- `GET /health` → `{"app":"SARO","version":"<app.version>","db_ok":true}` (200 from the deployed machine is the release gate).
- Engine/rule-pack provenance: `GET /api/v1/trace/{id}/export` embeds `engine_version` + `rule_pack_hash` (PT-008); `GET /api/v1/reports/engine/integrity` exposes the current rule-pack hash.

## Shared-responsibility split (SOC 2 / PT-004)

| Concern | SARO | Provider (Fly.io / Supabase) |
|---|---|---|
| Application code, authz, audit trail | ✔ | — |
| Tenant isolation (RLS + app-layer filters) | ✔ | RLS enforcement engine |
| Host / hypervisor / physical security | — | ✔ (inherit provider attestations) |
| Encryption at rest / backups | config | ✔ managed |
| Network edge / TLS termination | config | ✔ |
