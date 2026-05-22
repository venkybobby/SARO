# SARO Incident Response Plan

**Version:** 1.0  
**Owner:** Venky (Product Owner)  
**Last Reviewed:** May 2026  
**Next Review Due:** May 2027  
**Classification:** CONFIDENTIAL

---

## Purpose

This plan defines SARO's procedures for detecting, containing, and recovering from incidents that could affect customers, data, or regulatory compliance.

---

## 1. False Negative Discovery

**Definition:** A false negative occurs when SARO fails to flag a genuine AI risk or policy violation.

### Detection Triggers
- Customer or auditor reports a missed finding
- Post-hoc review of exported evidence packs identifies uncaught violations
- Internal QA batch regression identifies score drift

### Response Procedure
1. **Triage (0–2 hours):** On-call engineer validates the report. If confirmed, escalate to Severity 2.
2. **Impact Assessment (2–8 hours):** Identify affected audits, tenants, and date range.
3. **Containment (8–24 hours):** Temporarily disable affected rule pack. Notify affected tenants.
4. **Root Cause Analysis (24–72 hours):** Review rule matching logic, scoring thresholds. Patch rule pack.
5. **Re-audit (72 hours–5 days):** Re-run affected audits with patched rules. Provide corrected evidence packs.
6. **Post-Incident Review (within 7 days):** Update rule tests to prevent recurrence.

### Customer Communication
Send notification within 24 hours of confirmation: subject line "SARO Audit Finding Correction Notice", including affected audit IDs, impact description, and corrective actions taken.

---

## 2. System Downtime

**Definition:** SARO API or frontend is unavailable or degraded (>5% error rate for >5 minutes).

### Detection Triggers
- Railway health check failure
- Uptime monitor alert (target: 99.5% monthly)
- Customer-reported 503/504 errors

### Response Procedure
1. **Detect (0–5 min):** Automated alert fires; on-call engineer acknowledges.
2. **Assess (5–15 min):** Check Railway dashboard, Supabase health, recent deploys.
3. **Rollback if needed (15–30 min):** Revert to last known-good deploy on Railway.
4. **Restore (30–120 min):** Full service restoration SLA.
5. **Post-Mortem (within 48 hours):** RCA, timeline, preventive measures.

### SLA
- Detection-to-acknowledgement: 15 minutes
- Restoration: 2 hours (P1), 8 hours (P2)

---

## 3. Rule Pack Errors

**Definition:** A rule pack produces incorrect results (false positives, schema errors, or version conflicts).

### Detection Triggers
- Automated per-rule regression tests fail in CI
- Customer audit shows unexpected findings referencing wrong framework version
- Framework drift alert detects version mismatch

### Response Procedure
1. **Quarantine (0–4 hours):** Mark affected pack version as `deprecated`. Pin tenants to last known-good version.
2. **Diagnosis (4–24 hours):** Diff pack versions. Identify changed rules. Run known-positive/negative tests.
3. **Fix and Release (24–72 hours):** Patch rule pack. Increment PATCH version. Run full regression.
4. **Re-notify (within 5 days):** Tenants who ran audits against the erroneous pack receive correction notices.

---

## 4. Data Breach

**Definition:** Unauthorized access, disclosure, or exfiltration of audit data, PII, or credentials.

### Detection Triggers
- Supabase anomaly alert (unusual query volumes, off-hours access)
- TruffleHog/gitleaks scan finds committed credential
- Customer reports receiving another tenant's data (RLS failure)

### Response Procedure
1. **Contain (0–1 hour):** Revoke compromised credentials immediately. Enable Supabase maintenance mode if needed.
2. **Assess (1–4 hours):** Determine scope — which tenants, which data, which timeframe.
3. **Notify DPA (within 72 hours):** File breach notification with the relevant Data Protection Authority per GDPR Article 33.
4. **Notify Affected Tenants (within 72 hours):** Provide: what happened, what data was involved, steps taken, what the tenant should do.
5. **Forensics (1–5 days):** Audit Supabase logs. Preserve evidence. Engage external security firm if needed.
6. **Remediate (5–14 days):** Patch vulnerability. Rotate all credentials. Enable additional monitoring.

### Breach Notification Template
Subject: "SARO Data Security Notice — Action Required"
Content: Date/time of incident, nature of data exposed, actions SARO has taken, actions tenant should take, contact for questions.

---

## 5. Communication Protocol

### Internal Communication
- **Severity 1 (Critical):** Immediate Slack alert to #incidents channel + direct page to on-call engineer + Product Owner
- **Severity 2 (High):** Slack alert within 15 minutes + engineer response within 1 hour
- **Severity 3 (Medium):** Slack alert within 1 hour + response within 4 hours

### External Communication (Customer-Facing)
- All external communications drafted by Product Owner and reviewed before sending
- Status page (if available) updated within 30 minutes of confirmed incident
- Email notifications sent from: security@saro.ai

### Regulatory Communication
- GDPR data breach notification to DPA: within 72 hours
- Customer notification for data breach: within 72 hours
- False-negative correction: within 24 hours of confirmation

---

## 6. Severity Classification

| Severity | Description | Examples | Response SLA |
|----------|-------------|---------|-------------|
| P1 — Critical | Data breach, complete outage, RLS failure | Tenant data exposed, API down >30min | 1-hour response, 2-hour restore |
| P2 — High | Partial outage, false-negative in active audit, rule pack error | API degraded >20%, missed finding confirmed | 4-hour response, 8-hour restore |
| P3 — Medium | Minor feature degradation, delayed audits | Export failing, dashboard slow | 24-hour response |
| P4 — Low | Cosmetic issues, non-critical bugs | Typo in UI, chart display error | Next sprint |

---

## 7. Escalation Matrix

| Role | Responsibility | Contact |
|------|----------------|---------|
| On-Call Engineer | First responder; contain and assess | Slack @oncall |
| Product Owner (Venky) | Customer communication; P1/P2 decisions | Direct |
| Legal Counsel | Data breach regulatory notification | Retained counsel |
| Compliance SME | Rule pack and false-negative incidents | External |

---

## 8. SLAs

| Incident Type | Detection | Acknowledgement | Resolution |
|---------------|-----------|----------------|-----------|
| System Downtime (P1) | Automated (<5 min) | 15 min | 2 hours |
| Data Breach | Automated or reported | 1 hour | 72 hours (notification) |
| False Negative | Customer report | 24 hours | 5 days (corrected exports) |
| Rule Pack Error | CI or customer report | 4 hours | 72 hours |

---

## 9. Annual Review Schedule

This plan is reviewed annually and updated after any P1 or P2 incident.

| Review Type | Frequency | Owner | Next Due |
|-------------|-----------|-------|----------|
| Annual review | Yearly | Product Owner | May 2027 |
| Post-incident review | After P1/P2 | On-call Engineer | Within 7 days of incident |
| Tabletop exercise | Bi-annually | Product Owner + Engineer | November 2026 |

---

*End of Incident Response Plan v1.0*
