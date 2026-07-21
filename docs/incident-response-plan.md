# SARO Incident Response Plan

**Version:** 1.1  
**Owner:** Venky (Product Owner)  
**Last Reviewed:** 2026-07-21 (v1.1 — response-time reconciliation)  
**Next Review Due:** May 2027  
**Classification:** CONFIDENTIAL

> **v1.1 changelog — corrections, and why they matter.** v1.0 committed to
> automated detection in "<5 min", 15-minute acknowledgement, and 1-hour P1
> response. Those numbers pre-dated SARO's alerting: the canary probes every 30
> minutes and requires two consecutive failures before alerting, over an email
> channel that is not a pager, operated by one person. They were not
> deliverable, and this document is **customer-facing** via
> `GET /api/v1/governance/ir-plan`. Raised as FND-064 and corrected here:
>
> - Detection and response times now match the measured system
>   ([ops/alerts.md](ops/alerts.md), [ops/support-model.md](ops/support-model.md)).
> - **Severity levels and response targets now live in the support model.** This
>   document links to them rather than keeping a second copy that can drift.
> - Security-incident **notification** commitments are stated separately from
>   response targets — a 72-hour notification clock is achievable where a
>   15-minute response clock was not.
> - The escalation matrix now describes the actual solo-operator model, not an
>   on-call rotation and Slack channel that do not exist.
> - Superseded Railway references replaced with Fly.io ([ARCHITECTURE.md](ARCHITECTURE.md)).
>
> **Nothing here reduces a contractual obligation.** Where a signed BAA or DPA
> specifies shorter timelines, the agreement governs.

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
- Synthetic canary failure (`/health` non-200 or `db_ok: false`) — see [ops/alerts.md](ops/alerts.md) A1/A2
- Fly.io machine or platform incident
- Customer-reported 503/504 errors

### Response Procedure
1. **Detect (≤60 min):** the canary probes every 30 minutes and alerts after two
   consecutive failures. Sub-30-minute interruptions may not be observed at all
   ([ops/slo.md](ops/slo.md) §4).
2. **Acknowledge:** per the support model — 1 business hour for S1 in hours;
   best-effort outside hours.
3. **Assess:** `fly status`, Supabase health, recent releases — first commands in
   [ops/runbooks.md](ops/runbooks.md) A1.
4. **Rollback if needed:** revert to the last known-good Fly release.
5. **Restore:** continuous effort once engaged; mitigation target 4 business
   hours for S1.
6. **Post-mortem (within 10 business days):** using the template in §10.

### Response targets
Severity definitions and response/mitigation targets are maintained in
**[ops/support-model.md](ops/support-model.md) §3** — the single source. They are
not restated here, because two copies of a commitment table is how the
commitment drifts.

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

**Maintained in [ops/support-model.md](ops/support-model.md) §2–§3.** S1–S4
definitions and their response, mitigation, and resolution targets live there so
there is exactly one source. (v1.0 kept a P1–P4 table here with targets that
contradicted the alerting; see the v1.1 changelog.)

Mapping for anyone holding an older document: **P1≡S1, P2≡S2, P3≡S3, P4≡S4.**

---

## 7. Escalation Matrix

Honest solo-operator model — see [ops/support-model.md](ops/support-model.md) §5.

| Role | Responsibility | Contact |
|------|----------------|---------|
| Operator (Venky) | First and, in practice, only responder — detect, contain, assess, communicate | Email / direct |
| Named backup responder | Cover when the operator is unreachable | **[HUMAN — OPEN] not yet named** — the single largest gap in this plan |
| Legal Counsel | Breach regulatory notification | Retained counsel |
| Compliance SME | Rule-pack and false-negative incidents | External |

There is **no on-call rotation and no paging integration**. Alerting is
GitHub Actions failure → operator email ([ops/alerts.md](ops/alerts.md) §3).
[ops/support-model.md](ops/support-model.md) §6 states what a paging tier would
change, for an owner deciding whether to fund one.

---

## 8. Detection and notification commitments

Split deliberately: *detection* is bounded by instrumentation, *notification* by
obligation. Conflating them is what produced v1.0's undeliverable numbers.

| Incident type | Automated detection | Customer notification |
|---------------|--------------------|------------------------|
| System downtime | ≤60 min (canary, alerts.md A1) | On confirmation; status page per STORY-372 |
| Database unavailable | ≤30 min (alerts.md A2) | On confirmation if customer-visible |
| Confirmed reportable security incident | Varies — may be customer-reported | **≤72 hours** from confirmation (support-model §4) |
| False negative in an audit | Customer report only — no automated signal | On confirmation, with corrected exports to follow |
| Rule-pack error | CI regression suite, or customer report | On confirmation |

Where a signed BAA/DPA specifies shorter notification timelines, **the agreement
governs**; the above is a floor, not a cap.

---

## 9. Annual Review Schedule

This plan is reviewed annually and updated after any P1 or P2 incident.

| Review Type | Frequency | Owner | Next Due |
|-------------|-----------|-------|----------|
| Annual review | Yearly | Operator | May 2027 |
| Post-incident review | After S1/S2 | Operator | Within 10 business days |
| Tabletop exercise | Bi-annually | Operator | January 2027 (last: 2026-07-21, [ops/tabletop/](ops/tabletop/)) |

---

## 10. Post-mortem template

Blameless. The purpose is to change the system, not to establish who erred — a
post-mortem that produces an apology and no code change has failed.

```markdown
# Post-mortem: <short title>

**Incident ID:** INC-YYYY-NN   **Severity:** S1|S2   **Date:** YYYY-MM-DD
**Author:** <name>             **Status:** draft | final

## Summary
Two or three sentences a customer could read. What broke, who was affected,
for how long.

## Customer impact
- Tenants affected:
- Functions affected:
- Duration (first impact → mitigation → resolution):
- Evidence integrity affected? (**yes/no** — if yes, this is the headline)

## Timeline (UTC)
| Time | Event |
|---|---|
| | First impact (may precede detection) |
| | Detected — by what signal |
| | Acknowledged |
| | Mitigated |
| | Resolved |

**Detection gap:** first impact → detected = ____.
Was the delay within the ≤60 min target? If not, why?

## Root cause
The technical cause. Then keep asking "why" until you reach something
changeable — a missing test, an absent guard, an unstated assumption.

## What went well
Name the controls that worked; they are worth protecting in future changes.

## What did not
Including anything that made diagnosis slower than it needed to be.

## Actions
| # | Action | Type (prevent/detect/mitigate) | Owner | Due | Tracking ID |
|---|---|---|---|---|---|

At least one action must be **detect** or **prevent**. "Be more careful" is not
an action.

## Follow-ups filed
- FND / STORY ids:
- Regression test pinning the fix:
```

---

*End of Incident Response Plan v1.1*
