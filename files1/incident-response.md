# Command: /saro:incident-response

Draft or update SARO's Incident Response Plan — one of the three critical gaps required before external sharing.

## Usage

```
/saro:incident-response [draft | update | review]
```

- `draft` — generate initial Incident Response Plan document
- `update [section]` — update a specific section
- `review` — assess current IRP completeness against enterprise requirements

## Incident Response Plan Structure

When drafting, produce a Word document (.docx) with these sections:

### 1. Scope & Purpose
- Applies to SARO v8.0 and all subsequent versions
- Covers AI model failures, compliance breaches, data incidents, and security events
- Verticals: Finance, Healthcare, Technology, Government

### 2. Incident Classification

| Severity | Definition | Response SLA |
|----------|-----------|-------------|
| P0 — Critical | Production down, data breach, compliance violation with regulatory notification required | 1 hour |
| P1 — High | Compliance engine failure, drift undetected >24h, auth bypass | 4 hours |
| P2 — Medium | Single-vertical degradation, report generation failure | 24 hours |
| P3 — Low | UI issues, non-critical performance degradation | 72 hours |

### 3. Response Team

| Role | Responsibility | Contact |
|------|---------------|---------|
| Incident Commander | Venky R | Triage, external comms, escalation decisions |
| ML Lead | Alex Rivera | Model failure analysis, SHAP/drift investigation |
| Backend Lead | Jordan Lee | API/DB restoration, Koyeb rollback |
| QA Lead | Sam Patel / Taylor Kim | Regression verification post-fix |

### 4. Detection & Alerting
- Drift Sentinel circuit breaker triggers
- Koyeb health check failures
- Neon PostgreSQL connection drops
- Redis session invalidation storms
- OWASP security scan alerts

### 5. Response Playbooks

#### AI Model Drift Incident
1. Drift Sentinel fires circuit breaker
2. Alex Rivera investigates KS-Test / CUSUM output
3. Affected vertical isolated
4. Compliance evidence frozen (audit trail locked, no writes)
5. Root cause documented
6. Model retrain or rollback executed
7. SEC Proof chain verified post-recovery

#### Data Breach / Security Incident
1. Affected endpoints taken offline (Jordan Lee)
2. Redis sessions invalidated platform-wide
3. JWT secret rotated
4. Neon audit log frozen
5. External notification assessment (Venky — within 72h for GDPR-scope)
6. OWASP re-scan

#### Compliance Engine Failure
1. Identify which engine (Drift Sentinel / SEC Proof / eKYC Shield / Fairness)
2. Compliance evidence generation paused
3. Affected customers notified (Venky)
4. Engine restored and back-tested against fixtures
5. Compliance artefacts re-generated and verified

### 6. Communication Templates
- Internal Slack alert template
- Customer notification template (P0/P1)
- Regulatory notification template (if required)

### 7. Post-Incident Review
- Within 5 business days of P0/P1 resolution
- Output: root cause analysis doc, corrective actions, updated playbook

### 8. Data Retention for Incident Records
- Incident logs retained for 7 years (SEC Rule 17a-4 alignment)
- Post-incident reports stored in compliance artefact store

### 9. Plan Review Cadence
- Reviewed quarterly by Venky
- Updated after every P0/P1 incident

## Critical Gap Status

This command tracks one of the **three critical gaps** blocking external sharing:
> ⚠️ Until this IRP is complete and reviewed, flag all external sharing and demo prep tasks as BLOCKED on this item.
