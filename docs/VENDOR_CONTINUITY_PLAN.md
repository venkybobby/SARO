# Vendor Continuity Plan

> **Status:** v1.0 · CANONICAL · Owner: Venky (Lead) · 2026-06-12 · PT-012 AC-3 (Deal Condition #6)
> Neutralises the solo-founder / viability objection. Suitable as an MSA exhibit.

## 1. Infrastructure freeze

The stack is frozen on **Fly.io + Supabase + Postgres staging** (`ARCHITECTURE.md`):
- `fly.toml` / `frontend/fly.toml`: `auto_stop_machines = 'off'`, health-check timeout `5s`.
- Railway / Koyeb / Neon references are SUPERSEDED in canonical docs (`DOCUMENT_REGISTER.md`).
- A provider change despite the freeze requires a **documented exception with customer notice**
  (≥30 days per DPA sub-processor change procedure), never a silent migration.

## 2. Backup operational coverage

| Function | Primary | Backup coverage | Runbook |
|---|---|---|---|
| Deploy | Lead | GitHub Actions `deploy.yml` is push-button; any engineer with Fly.io access can deploy from `main` | `deploy.yml` + `health-check.sh` |
| Database restore | Backend/Infra | Supabase Point-in-Time Recovery; documented RPO ≤ 24h, RTO ≤ 4h target | this doc §4 |
| Incident response | Lead | `incident-response-plan.md` escalation tree; on unavailability, escalate to backup contact then provider support | `incident-response-plan.md` |
| Customer communication | Lead | Status page + email template; named backup notifier | `incident-response-plan.md` |

## 3. Key-person mitigation & hiring sequence

| Critical role | Held by | Succession |
|---|---|---|
| Backend / Infra | Jordan Lee | Documented runbooks (deploy/restore/IR); hire backend engineer with 30–90 day overlap on departure |
| Product / Compliance | Venky | Compliance Claims Matrix + EVF process are documented & machine-enforced; hire compliance lead with overlap |

Cross-training checklist maintained; runbooks are versioned in this repo (integrated-delivery rule).

## 4. Restore procedure (summary)

1. Provision Fly.io apps from `fly.toml` / `frontend/fly.toml` (`flyctl deploy`).
2. Restore Supabase database via PITR to the target timestamp.
3. Set required secrets (`JWT_SECRET_KEY`, `DATABASE_URL`, `EXPORT_HMAC_SECRET`, …) per `.env.example`.
4. Verify `GET /health` returns 200 and chain integrity via `GET /api/v1/audit/verify-chain`.

## 5. Escrow linkage

Source-code escrow and release conditions are defined in `ESCROW_AGREEMENT.md` and are referenceable
in the MSA. Release conditions are objective (e.g., 30-day unremediated outage), never discretionary.
