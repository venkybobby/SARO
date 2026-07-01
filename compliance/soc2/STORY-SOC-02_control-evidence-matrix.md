# STORY-SOC-02 — Control-to-Evidence Matrix (TSC → SARO controls → gaps)

**Epic:** 15 — Trust & Compliance Enablement · **Workstream:** SOC 2 Type II
**Status:** DRAFT — matrix built from in-repo discovery; **[HUMAN] security-owner validation pending**
**Depends on:** STORY-SOC-01 (scope: Security + Confidentiality + Availability)
**Owner (artifact):** Jordan Lee (Backend/Infra) · **Reviewer:** Venky (Lead)
**Human gate:** Security owner validates the matrix + prioritizes gap remediation

> **Purpose.** The honest inventory: which controls SARO **actually** has, which are missing. This is
> where overclaiming is the risk — so **no control is claimed without a pointer to where it lives**
> (ADR-004 spirit). Every "Gap" row is surfaced as a candidate follow-on story with an owner.
>
> **Method.** Controls were discovered by reading the repo (`auth.py`, `models.py`, `services/`,
> `routers/`, `middleware/`, `migrations/`, `.github/workflows/`, `quality/`, `docs/`). Pointers are
> `path` + symbol/line. Line numbers may drift with edits; the file + symbol is the durable anchor.
> **Posture: SARO holds no SOC 2 report — this is readiness evidence, "in progress / roadmap."**

---

## 1. Legend

- **Status:** ✅ Implemented (evidence in-repo) · 🟡 Partial (exists but incomplete) · ⛔ Gap (no evidence — follow-on story)
- **Severity** (for gaps): 🔴 High (blocks audit window) · 🟠 Medium (fix during observation) · 🟡 Low
- Every ✅/🟡 row carries an **evidence pointer**. Every ⛔ row carries a **severity + owner**.

---

## 2. Security — Common Criteria (CC) [required]

| CC | Control | Status | Actual SARO control (pointer) | Evidence source for auditor |
|---|---|---|---|---|
| CC1.1 | Integrity & ethics | 🟡 | SARO Non-Negotiables + scope locks: `CLAUDE.md`, `ADR-004-compliance-scope-locks.md` | Docs; commit history showing enforcement |
| CC1.2 | Board / management oversight | ⛔ | No meeting minutes / governance cadence in-repo | — |
| CC2.1 | Internal communication | ✅ | GitHub PRs/Issues; conventional-commit convention | PR/issue history, CI logs |
| CC2.2 | External communication | ✅ | `docs/COMPLIANCE_CLAIMS_MATRIX.md`, `docs/sub-processors.md` | Published docs |
| CC3.1 / CC3.2 | Risk assessment & identification | ✅ | 4-gate scoring `engine.py`; GRC gate/checks `grc/gate.py`, `grc/checks/`; risk tiering `grc/tiering.py` | Engine tests; `grc/` test suite |
| CC4.1 | Control monitoring | 🟡 | CI gates `.github/workflows/ci.yml`, `quality-gates.yml`; rate-limit Prometheus counter `middleware/rate_limiter.py:58-66` | CI run history; Prometheus metrics |
| CC5.1 | Logical access controls | ✅ | JWT `auth.py:119-148` (`create_access_token`/`_decode_token`); RBAC `auth.py:245-266` (`require_role`); personas `auth.py:269-292` | Auth code; authz tests |
| CC5.2 | Infrastructure access | 🟡 | Fly.io + Supabase console access (provider IAM) — **not documented in-repo**; roadmap CC5.2 marked "Railway/Partial" is **stale** | Provider IAM export (manual) |
| CC6.1 | Access provisioning | ✅ | SAML 2.0 SSO `routers/sso.py`; SCIM `routers/clients.py` (`/scim/v2/{tenant_id}`, token rotate) | SSO/SCIM config; `routers/sso.py` tests |
| CC6.2 | Privileged access | 🟡 | `super_admin` role `auth.py`; MFA gated by `ClientConfig.mfa_required` `routers/sso.py:350-360` — **MFA is config-optional, not enforced org-wide** | Role assignments; MFA policy config |
| CC6.3 | Access removal / deprovisioning | ⛔ | `User.is_active` flag exists (`models.py:76`, enforced `auth.py:189-190`) but **no deactivation/deletion API endpoint** (see Gap G-SOC-01) | — |
| CC6.6 | Logical access change logging | ✅ | Immutable `AuditEvent` `models.py:464-483`; SSO events `routers/sso.py` (`_write_audit_event`) | AuditEvent table export |
| CC6.7 | Data transmission controls | ✅ | DB `sslmode=require` `config.py:33`; Argon2id password hashing `auth.py:50-114` (bcrypt fallback); SCIM token SHA-256 hashed `routers/clients.py` | Config; auth tests |
| CC6.8 | Component destruction | 🟡 | Retention + tombstone `services/retention_service.py`; GDPR erasure `routers/governance.py` (72h SLA) | Retention config; deletion certificates |
| CC7.1 | Configuration management | ✅ | `fly.toml`, `frontend/fly.toml`, `Dockerfile`, Pydantic `config.py` | Repo config files |
| CC7.2 | Infrastructure monitoring | 🟡 | Structlog JSON `main.py:80-98`; health `/health`; **Sentry DSN documented but NOT initialized** (see Gap G-SOC-02) | Log samples; health checks |
| CC7.3 | Vulnerability management | ✅ | CI `ci.yml`: Bandit (high-sev gate) + Safety + TruffleHog secret scan; `.safety-policy.yml`; pre-commit `detect-secrets` | CI security-job run history |
| CC7.4 | Incident response | ✅ | `docs/incident-response-plan.md` v1.0 (P1–P4 SLAs, escalation, breach comms) | IR plan; incident records (during window) |
| CC7.5 | Anomaly detection | ✅ | Drift sentinel / KS-test in `engine.py`; rate limiter `middleware/rate_limiter.py` (100 rpm/tenant, 10 rpm/IP auth) | Drift config; rate-limit metrics |
| CC8.1 | Change management | ✅ | CI gates (lint/test/security/e2e) `ci.yml`; quality ratchet `quality-gates.yml` + `quality/baseline.json`; regression manifest `tests/regression/manifest.yaml` | CI logs; ratchet history; PR reviews |
| CC9.1 | Risk mitigation | ✅ | Remediation guidance in scoring output; GRC hard rules `grc/hard_rules.py`, sign-off `grc/signoff.py` | Engine output; `grc/` tests |
| CC9.2 | Vendor management | 🟡 | `docs/sub-processors.md` (**stale — lists Railway/Streamlit**; reconcile to Fly.io + Supabase); `docs/VENDOR_CONTINUITY_PLAN.md`; DPA templates | Sub-processor register (post-reconcile) |

---

## 3. Confidentiality (C) [recommended in scope]

| C | Control | Status | Actual SARO control (pointer) | Evidence source |
|---|---|---|---|---|
| C1.1 | Confidential-info identification | ✅ | Edge redaction Safe Harbor HIPAA-18 `services/edge_redaction.py` (STORY-403); content-free audit events `services/audit_emitter.py` (STORY-404) | Redaction SLIs; audit schema test |
| C1.2 | Confidential-info retention | ✅ | Per-tenant retention (default 90d) `routers/governance.py`; `services/retention_service.py` (`calculate_retention_cutoff`) | Retention policy config |
| C1.3 | Confidential-info disposal | ✅ | GDPR erasure endpoint + deletion certificate `services/retention_service.py` (`generate_deletion_certificate`); tombstone preserves chain integrity | Deletion certificates |
| — | Data-minimization intake | ✅ | Accepts only `prompt` + `raw_output` (Non-Negotiable 1); no raw-content retention (`audit_emitter.py` AC-4) | Engine input contract; schema tests |
| — | No-secondary-use / no training on customer data | ✅ | Core scoring makes zero external-model calls; external-model guard `grc/guards/external_model.py` | Guard test in `quality-gates.yml` |

---

## 4. Availability (A) [recommended in scope]

| A | Control | Status | Actual SARO control (pointer) | Evidence source |
|---|---|---|---|---|
| A1.1 | Availability commitments (SLA) | ⛔ | No formal SLA/uptime commitment in-repo (see Gap G-SOC-05) | — |
| A1.2 | System availability | ✅ | `/health` endpoint; Docker `HEALTHCHECK` `Dockerfile:46-47`; Fly.io health checks `fly.toml` (`auto_stop_machines='off'`) | Health-check config; uptime logs (during window) |
| A1.3 | System recovery | 🟡 | Supabase PITR (RPO ≤24h / RTO ≤4h target, `docs/VENDOR_CONTINUITY_PLAN.md`); restore runbook — **DR test not yet exercised** (see Gap G-SOC-06) | Continuity plan; DR test record (pending) |
| A1.4 | Capacity / backup ops | ✅ | Backup-operator coverage + restore procedure `docs/VENDOR_CONTINUITY_PLAN.md`; escrow linkage `ESCROW_AGREEMENT.md` | Continuity plan |

---

## 5. Gap list — candidate follow-on stories (AC-2)

> Each gap is a **candidate follow-on story** (SOC-02 does not build controls — SOC-01 §1). Owners
> from the CLAUDE.md team table. Severity per §1.

| Gap ID | TSC | Description | Severity | Owner | Suggested follow-on |
|---|---|---|---|---|---|
| **G-SOC-01** | CC6.3 | **No user deprovisioning/deactivation API.** `is_active` exists but only settable via direct DB access; no `DELETE`/deactivate endpoint. | 🔴 High | Jordan Lee | STORY: user-deactivation endpoint + access-removal SLA |
| **G-SOC-02** | CC7.2 | **Sentry documented but not initialized** (`SENTRY_DSN` in `.env.example`, no SDK init in `main.py`). Error tracking not operational. | 🟠 Medium | Jordan Lee | STORY: wire Sentry init + verify error capture |
| **G-SOC-03** | CC5.1 | **No logout / token-revocation endpoint** (FND-002 open in `tests/regression/manifest.yaml`). Sessions end only on JWT expiry. | 🟠 Medium | Jordan Lee | STORY: logout + token revocation (already tracked FND-002) |
| **G-SOC-04** | CC7.3 | **No `pip-audit`** (Safety + Bandit + TruffleHog present). SBOM/dependency-audit coverage partial. | 🟡 Low | Sam Patel | STORY: add pip-audit to CI security job |
| **G-SOC-05** | A1.1 | **No formal SLA / uptime commitment** documented. | 🟠 Medium | Venky | STORY: publish SLA + uptime commitment |
| **G-SOC-06** | A1.3 | **DR / restore not exercised** — runbook exists, no test record. | 🟠 Medium | Jordan Lee | STORY: run + record DR test |
| **G-SOC-07** | CC1.2 | **No board/management oversight cadence** (minutes, governance review). | 🟡 Low | Venky | STORY: governance review cadence + minutes |
| **G-SOC-08** | CC6.2 | **MFA is config-optional, not org-wide enforced** (`mfa_required` per-tenant). No blanket privileged-access MFA policy. | 🟠 Medium | Jordan Lee | STORY: enforce MFA for privileged/all tenants |
| **G-SOC-09** | CC5.2 | **Infrastructure access (Fly.io/Supabase IAM) not documented in-repo**; roadmap reference is stale (Railway). | 🟠 Medium | Jordan Lee | STORY: document infra access model + review |
| **G-SOC-10** | CC9.2 | **`docs/sub-processors.md` is stale** (Railway/Streamlit vs PT-012 Fly.io + Supabase). | 🟠 Medium | Venky | STORY: reconcile sub-processor register to ARCHITECTURE.md |
| **G-SOC-11** | CC1.1 | **No employee background-check / security-awareness-training policy + records** (roadmap G-06/G-07). | 🟠 Medium | Sam Patel / Venky | STORY: training + background-check policy |
| **G-SOC-12** | CC4.1 | **No formal quarterly access-review records** (roadmap G-12). | 🟡 Low | Venky | STORY: quarterly access review + records |
| **G-SOC-13** | CC7.3 | **No annual external penetration test** (roadmap G-04). | 🔴 High | External vendor | STORY: engage external pentest |
| **G-SOC-14** | CC6.7 | **No documented encryption-key rotation policy** (roadmap G-11). | 🟡 Low | Jordan Lee | STORY: key-rotation policy |

> **Roadmap reconciliation:** `docs/soc2-readiness-roadmap-v1.0.md` marked several of the above as
> "Implemented." This matrix **corrects** those to their true state where in-repo evidence disagrees
> (esp. CC5.2 Railway→Fly.io, CC6.2 MFA optional, CC7.2 Sentry not wired, CC6.3 no deprovision API).

---

## 6. Evidence-source summary (AC-3)

Every ✅/🟡 control names its auditor evidence source in the tables above. Categorized:

| Evidence type | Where | Controls it backs |
|---|---|---|
| **Source code + tests** | `auth.py`, `grc/`, `services/`, `engine.py`, `tests/regression/` | CC3, CC5, CC6.x, CC9, C1.x |
| **CI run history** | `.github/workflows/ci.yml`, `quality-gates.yml` | CC4.1, CC7.3, CC8.1 |
| **Config files** | `fly.toml`, `config.py`, `.safety-policy.yml`, `Dockerfile` | CC6.7, CC7.1, A1.2 |
| **Immutable audit log** | `AuditEvent` table (`models.py`), `audit_emitter.py` hash chain | CC6.6, C1.x |
| **Policies / docs** | `docs/incident-response-plan.md`, `VENDOR_CONTINUITY_PLAN.md`, DPA templates | CC7.4, CC9.2, C1.2/1.3, A1.3 |
| **Runtime metrics** | Prometheus counters, `/health`, structlog | CC4.1, CC7.2, CC7.5, A1.2 |
| **Manual exports (gap)** | Provider IAM (Fly.io/Supabase), access reviews | CC5.2, CC6.2 — need capture (SOC-03) |

---

## 7. Security-owner validation — **[HUMAN] gate (AC-4)**

> The security owner validates this matrix and prioritizes gap remediation. Claude Code cannot
> validate or accept the control claims. This block stays open until a human signs off.

| Field | Value |
|---|---|
| **Matrix reviewed by security owner** | ⬜ (proposed owner: Jordan Lee / Venky) |
| **All control pointers verified accurate** | ⬜ |
| **Gap severities + owners ratified** | ⬜ |
| **Gap remediation prioritized (which before window)** | ⬜ |
| **Sign-off date** | _____________________ |

---

## 8. Definition of done (tests)

- [x] **Every in-scope criterion mapped** — CC1–CC9, C1.x, A1.x (§2–§4).
- [x] **No unbacked control claim** — every ✅/🟡 row has a pointer; gaps carry no claim.
- [x] **Gaps enumerated with owners** — §5, G-SOC-01…14, severity + owner + follow-on.
- [x] **Evidence source named per control** — §2–§4 tables + §6 summary.
- [ ] **Security owner validates** — §7 human gate, open.

## CHANGES MADE
- Built the TSC → SARO control map for the three in-scope categories (Security CC, Confidentiality C,
  Availability A), each ✅/🟡 row carrying a concrete in-repo pointer and a named evidence source.
- Enumerated 14 gaps (G-SOC-01…14) with severity + owner as candidate follow-on stories.
- Corrected the readiness-roadmap's optimistic "Implemented" states where in-repo evidence disagrees.

## THINGS I DIDN'T TOUCH
- Building any missing control (each gap is its own follow-on — SOC-01 scope).
- `docs/soc2-readiness-roadmap-v1.0.md` and `docs/sub-processors.md` — flagged stale, not rewritten.
- Any runtime code — pure discovery/documentation.

## POTENTIAL CONCERNS
- **The readiness roadmap overclaims vs reality.** Several controls it marks "Implemented" are
  partial or gaps here (MFA optional, Sentry not wired, no deprovision API, Railway references). If
  the roadmap goes to the auditor unreconciled, it reads as an overclaim — reconcile before fieldwork.
- **Line numbers will drift.** Pointers use file + symbol as the durable anchor; re-verify at audit time.
- **G-SOC-01 (no deprovision API) and G-SOC-13 (no pentest) are 🔴 High** — likely block the window
  opening; prioritize first.
- **Provider-side controls (CC5.2, CC6.2 infra)** need manual IAM exports; not capturable in-repo (SOC-03).
