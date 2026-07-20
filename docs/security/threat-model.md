# SARO Threat Model (STRIDE) — Pre-Pentest Baseline

**Story:** STORY-365 · **Owner:** Venky · **Created:** 2026-07-20
**Surfaces:** `sarofrontend.fly.dev` (React/Vite) · `saro-backend.fly.dev`
(FastAPI) · Supabase PostgreSQL. Primary region `dfw` (docs/ARCHITECTURE.md).

## 1. Trust boundaries & data flows

```
Browser ──HTTPS──> Fly edge ──> sarofrontend (static)
Browser ──HTTPS──> Fly edge ──> saro-backend (JWT auth) ──TLS──> Supabase (RLS)
Operator CLI ────────────────> saro-backend (JWT)
Client log exports (S3/blob/GCS, customer-owned) ──read-only pull──> adapters
GitHub Actions ──deploy token──> Fly · ──schedule──> canary/evidence jobs
```

Assets: tenant audit evidence (TRACE chains, attestations), JWT signing key,
DB credentials, cross-account role ARNs, demo credentials. SARO holds **no
payment data**; PHI posture is zero-retention by construction (INV-2).

## 2. STRIDE by surface

### Backend API (saro-backend.fly.dev)
| Threat | Vector | Mitigation (pointer) | Residual |
|---|---|---|---|
| **S**poofing | Credential stuffing on login | Per-IP auth rate limit 10/min (`middleware/rate_limiter.py`); JWT expiry | No MFA — roadmap; document in pentest RoE |
| **T**ampering | Evidence mutation | SHA-256 hash-chained traces + `GET /api/v1/audit/verify-chain`; RPV immutable snapshots | Postgres-level protection depends on RLS + grants (STORY-366 extends) |
| **R**epudiation | Admin action denial | Self-audit events; STORY-366 append-only admin audit log | Coverage of all admin routes enforced by test from STORY-366 |
| **I**nfo disclosure | Cross-tenant reads | RLS + app-layer tenant filters; probes: `tests/test_pt009_tenant_isolation_concurrency.py`, `tests/test_story365_route_authz.py` (every route 401/403 unauthenticated) | Route suite is authn-only for breadth; per-route wrong-tenant probes remain per-feature tests |
| **D**oS | Evaluate/ingest saturation | Per-IP 60/min on `/api/v1/scan`, `/api/v1/ingest`; body-size caps in adapters (FND-2) | No global per-tenant limit (deliberate — load review pending); Fly edge absorbs L3/4 |
| **E**oP | Role escalation | `require_role`/persona deps on routers; probe suite fails any route lacking auth | Persona enforcement narrow in places (GAP_ANALYSIS §1 Epic 9 note) |

### Frontend (sarofrontend.fly.dev)
| Threat | Mitigation | Residual |
|---|---|---|
| XSS → token theft | Token in localStorage (`saro_token`); React escaping; backend CSP is deny-all (API responses can't be framed/executed) | localStorage is XSS-readable — httpOnly-cookie migration is a known tradeoff to raise at pentest |
| Clickjacking | `X-Frame-Options: DENY` + `frame-ancestors 'none'` (backend); frontend host headers to verify in pentest | Verify Fly static-site headers |
| Supply chain | npm audit/osv gate (STORY-367); lockfile committed | — |

### Supabase
| Threat | Mitigation | Residual |
|---|---|---|
| Direct DB access w/ leaked creds | Creds only in Fly secrets (STORY-363 runbook); rotation procedure | Rotation execution is OPEN [HUMAN] (runbook §4) |
| RLS bypass via service key | Service key never client-side; backend is the only DB principal | Confirm no anon-key exposure in frontend build |
| Backup exfiltration | Provider-managed encryption at rest (shared-responsibility, ARCHITECTURE.md §SOC2) | DR evidence pending STORY-370 rehearsal |

## 3. Route authorization inventory

Mechanically enforced, not hand-maintained: `tests/test_story365_route_authz.py`
probes **every** registered route unauthenticated and fails on anything outside
the justified public allowlist (8 exact routes + SSO handshake prefix). Role
requirements live as router dependencies (`require_role` /
`require_role_or_persona`) — grep `dependencies=[Depends(require_role` for the
per-route table; privileged families: traces, trace-export, scan, clients,
tenants, rules/versions, evf admin, self-audit.

## 4. Findings from this pass

| ID | Finding | Severity | Disposition |
|---|---|---|---|
| TM-F1 | Jira OAuth callback accepts optional, unsigned `state` used directly as tenant id (routers/remediation.py) — no CSRF/state integrity on token binding | Medium | Follow-up task spawned; fix = signed state issued at /oauth/jira/start, verified in callback |
| TM-F2 | No MFA on password login | Low (pilot phase) | Roadmap; SSO/SAML path exists for enterprise tenants |
| TM-F3 | JWT in localStorage (frontend) | Info | Raise at pentest; httpOnly-cookie migration has CORS-credentials implications (main.py CORS comment) |

## 5. Hardening delivered in STORY-365

Security headers middleware (`middleware/security_headers.py`: nosniff,
X-Frame-Options DENY, deny-all CSP with relaxed docs-page variant, HSTS on
https, Referrer-Policy no-referrer) · evaluate/ingest per-IP rate limit ·
route-authz probe suite in CI (pytest gate) · CORS: `ALLOWED_ORIGINS` must be
set to `https://sarofrontend.fly.dev` in Fly secrets (LIVE-003; wildcard branch
logs a warning and disables credentials).
