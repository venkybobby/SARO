# SARO SOC 2 Type II Readiness Roadmap v1.0

**Document version:** 1.0
**Status:** DRAFT — for internal planning
**Last updated:** 2026-05-22
**Owner:** Venky (Lead Engineer) | Jordan Lee (Backend/Infra)

> This document outlines SARO's path to SOC 2 Type II attestation.
> Target attestation window: Q4 2026 – Q1 2027.

---

## 1. Overview

SOC 2 (Service Organization Control 2) is an auditing standard developed by the AICPA that evaluates service organisations against the Trust Service Criteria (TSC). SARO is targeting **Type II** attestation (operational effectiveness over a minimum 6-month observation period).

**Target TSC scope:**
- Security (CC) — **required**
- Availability (A) — **in scope**
- Confidentiality (C) — **in scope**
- Processing Integrity (PI) — **deferred to Phase 2**
- Privacy (P) — **deferred to Phase 2**

---

## 2. Trust Service Criteria Mapping

### 2.1 Security (CC — Common Criteria)

| Criterion | Control | Status | Owner |
|---|---|---|---|
| CC1.1 — COSO Principle 1: Integrity and Ethics | Code of conduct, SARO Non-Negotiables in CLAUDE.md | Implemented | Venky |
| CC1.2 — Board oversight | Governance review process documented | Gap |  |
| CC2.1 — Communication (internal) | Slack / GitHub Issues / PRs | Implemented | All |
| CC2.2 — External communication | docs/COMPLIANCE_CLAIMS_MATRIX.md | Implemented | Venky |
| CC3.1 — Risk assessment | TRACE risk scores, Bayesian scoring | Implemented | Alex Rivera |
| CC3.2 — Risk identification | MIT taxonomy risk classification | Implemented | Alex Rivera |
| CC4.1 — Control monitoring | pytest CI, Prometheus, Sentry | Partial | Jordan Lee |
| CC5.1 — Logical access controls | JWT RBAC, persona permissions | Implemented | Jordan Lee |
| CC5.2 — Infrastructure access | Railway access controls | Partial | Jordan Lee |
| CC6.1 — Logical access provisioning | SAML SSO, SCIM provisioning | Implemented (SPEC-F2) | Jordan Lee |
| CC6.2 — Privileged access | super_admin role, MFA enforcement | Implemented | Jordan Lee |
| CC6.3 — Access removal | User deactivation API | Gap |  |
| CC6.6 — Logical access changes | AuditEvent immutable log | Implemented | Jordan Lee |
| CC6.7 — Data transmission controls | TLS 1.2+, JWT | Implemented | Jordan Lee |
| CC6.8 — System component destruction | Data deletion API (SPEC-F3 PATCH trace) | Partial | Jordan Lee |
| CC7.1 — Configuration management | Railway TOML, Dockerfile | Implemented | Jordan Lee |
| CC7.2 — Infrastructure monitoring | Railway Observability, Sentry | Partial | Jordan Lee |
| CC7.3 — Vulnerability management | pip-audit, OWASP scan (CI Monday) | Implemented | Sam Patel |
| CC7.4 — Incident response | docs/incident-response-plan.md | Implemented | Jordan Lee |
| CC7.5 — Anomaly detection | Drift sentinel, KS-test | Implemented | Alex Rivera |
| CC8.1 — Change management | Conventional Commits, PR reviews | Implemented | All |
| CC9.1 — Risk mitigation | Remediation workflow (SPEC-F3) | Implemented | Jordan Lee |
| CC9.2 — Vendor management | Sub-processors list (docs/sub-processors.md) | Implemented | Venky |

### 2.2 Availability (A)

| Criterion | Control | Status | Owner |
|---|---|---|---|
| A1.1 — Availability commitments | SLA targets defined in MSA | Gap |  |
| A1.2 — System availability | Railway health checks, `/health` endpoint | Implemented | Jordan Lee |
| A1.3 — System recovery | Supabase PITR, Railway restarts | Implemented | Jordan Lee |

### 2.3 Confidentiality (C)

| Criterion | Control | Status | Owner |
|---|---|---|---|
| C1.1 — Confidential information identification | DPA template, PII redaction in traces | Implemented | Venky |
| C1.2 — Confidential information disposal | Data deletion on contract termination (DPA §3.6) | Implemented (policy) | Venky |

---

## 3. Gap Analysis

### Critical Gaps (must fix before audit window opens)

| Gap | Description | Effort | Owner | Target |
|---|---|---|---|---|
| G-01 | Formal board/management oversight meeting minutes | Low | Venky | Q3 2026 |
| G-02 | Documented vendor risk assessment process for all sub-processors | Medium | Jordan Lee | Q3 2026 |
| G-03 | Formal user access removal SLA (CC6.3) | Low | Jordan Lee | Q3 2026 |
| G-04 | Penetration test (annual external) | High | External vendor | Q3 2026 |
| G-05 | Formal SLA / uptime commitment documentation | Low | Venky | Q3 2026 |
| G-06 | Employee background check policy | Medium | Venky | Q3 2026 |
| G-07 | Security awareness training programme with records | Medium | Sam Patel | Q3 2026 |
| G-08 | Change advisory board (CAB) process for production changes | Low | Jordan Lee | Q3 2026 |

### Medium Priority Gaps (fix during observation period)

| Gap | Description | Effort | Owner | Target |
|---|---|---|---|---|
| G-09 | Formalised disaster recovery test | Medium | Jordan Lee | Q4 2026 |
| G-10 | Asset inventory (hardware + software + SaaS) | Medium | Jordan Lee | Q4 2026 |
| G-11 | Encryption key rotation policy documented | Low | Jordan Lee | Q4 2026 |
| G-12 | Formal access review (quarterly) with records | Low | Venky | Q4 2026 |

---

## 4. Implementation Roadmap

### Phase 1: Foundation (Q2–Q3 2026)

| Task | Owner | Deadline |
|---|---|---|
| Appoint DPA/security lead | Venky | 2026-06-15 |
| Engage SOC 2 readiness consultant | Venky | 2026-06-30 |
| Select audit firm (Big 4 or specialist) | Venky | 2026-07-15 |
| Complete gap analysis (G-01 to G-08) | Jordan Lee | 2026-08-31 |
| External penetration test | External | 2026-08-31 |
| Implement security awareness training (LMS) | Sam Patel | 2026-08-31 |

### Phase 2: Observation Period (Q3–Q4 2026)

**Observation window: 6 months minimum**
Start: **2026-08-01** | End: **2027-01-31**

| Task | Owner | Deadline |
|---|---|---|
| Begin evidence collection (policies, logs, access reviews) | Jordan Lee | 2026-08-01 |
| Quarterly access review #1 | Venky | 2026-09-30 |
| Quarterly access review #2 | Venky | 2026-12-31 |
| Mock audit with readiness consultant | External | 2026-11-30 |
| Address mock audit findings | Jordan Lee | 2026-12-31 |

### Phase 3: Attestation (Q1 2027)

| Task | Owner | Deadline |
|---|---|---|
| Submit evidence package to audit firm | Jordan Lee | 2027-01-15 |
| Fieldwork with auditor | All | 2027-01-31 |
| Respond to auditor queries | Jordan Lee | 2027-02-15 |
| Receive SOC 2 Type II report | External | 2027-03-31 |

---

## 5. Budget Estimate

| Item | Estimated Cost (USD) |
|---|---|
| SOC 2 readiness consultant (120 hrs @ $250/hr) | $30,000 |
| External penetration test | $15,000–$25,000 |
| Audit firm (SOC 2 Type II) | $25,000–$50,000 |
| Security awareness training platform (annual) | $3,000–$8,000 |
| Internal engineering time (320 hrs @ $150/hr) | $48,000 |
| **Total estimate** | **$121,000–$161,000** |

---

## 6. Evidence Repository

Evidence will be collected in `/docs/soc2-evidence/` (not committed — stored in secure document management system):

```
soc2-evidence/
├── policies/          # Access control, incident response, change management
├── procedures/        # Runbooks, on-call guides
├── access-reviews/    # Quarterly RBAC review records
├── pentest-reports/   # Annual penetration test reports
├── training-records/  # Security awareness completion records
├── vendor-risk/       # Sub-processor assessments
└── incidents/         # Security incident records
```

---

## 7. References

- AICPA Trust Service Criteria 2017 (with 2022 updates)
- SARO CLAUDE.md — Non-Negotiables (immutable security posture)
- docs/COMPLIANCE_CLAIMS_MATRIX.md — Compliance boundary definitions
- docs/legal/saro-dpa-template-v1.0.md — Data Processing Agreement template
- docs/sub-processors.md — Sub-processor register
- docs/incident-response-plan.md — Incident response procedures

---

*Last updated: 2026-05-22 | Owner: Venky (Lead) | Jordan Lee (Backend/Infra)*
*Review cycle: Quarterly*
