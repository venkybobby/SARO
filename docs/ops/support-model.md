# SARO Support Model

**Story:** STORY-371 · **Owner:** Venky · **Version:** 1.0 · 2026-07-21
**Status:** current source of truth for severity levels and response targets.
Referenced by [../legal/sla-draft-v0.1.md](../legal/sla-draft-v0.1.md) §5 and
[../incident-response-plan.md](../incident-response-plan.md).

> **This document exists to replace commitments SARO could not keep.** The
> previous response targets (15-minute acknowledgement, 1-hour P1 response,
> "<5 min" automated detection) were written before the alerting was built and
> did not survive contact with it — see FND-064. What follows is what the
> current operating model can actually deliver.

---

## 1. The operating model, stated plainly

SARO is operated by **one person**. There is no on-call rotation, no follow-the-sun
coverage, and no paging tier. Alerting is GitHub Actions failure → operator
email ([alerts.md](alerts.md) §3), which is checked during working hours and
opportunistically outside them.

A customer evaluating SARO should price that in. Targets below are honest for
that model; §6 states exactly what changes if a paging tier is funded.

**Support hours:** Monday–Friday, 09:00–18:00 America/Chicago, excluding US
public holidays. Outside these hours, response is **best-effort with no
committed time**.

---

## 2. Severity definitions

| Severity | Definition | Examples |
|---|---|---|
| **S1 — Critical** | Service unusable, evidence integrity at risk, or a suspected security/tenant-isolation incident | API down; cross-tenant data visible; audit chain verification failing; credential exposure |
| **S2 — High** | Major function degraded with no workaround; evidence still trustworthy | Evaluations failing for one tenant; ingestion stalled >4h; export broken |
| **S3 — Medium** | Function impaired with a workaround, or non-urgent correctness issue | A rule-pack producing a suspected false positive; dashboard slow; report formatting wrong |
| **S4 — Low** | Cosmetic, documentation, or enhancement request | UI copy, chart labels, feature requests |

Severity is set by impact, not by who reports it. A customer may propose a
severity; SARO confirms or adjusts it and says why.

---

## 3. Response and resolution targets

**Response** = a human has acknowledged and begun work. **Mitigation** = impact
reduced or a workaround provided. **Resolution** = underlying cause fixed.

| Severity | Response (in hours) | Response (outside hours) | Mitigation target | Resolution target |
|---|---|---|---|---|
| **S1** | 1 business hour | Best-effort; no commitment. Realistically next morning unless already noticed | 4 business hours | Continuous effort once engaged until mitigated |
| **S2** | 4 business hours | Next business day | 2 business days | Next scheduled release |
| **S3** | 2 business days | — | Next scheduled release | Backlog, prioritised |
| **S4** | 5 business days | — | — | Backlog, no commitment |

**Detection is separate from response.** Automated detection of an availability
incident is **≤60 minutes** (30-minute canary interval + the two-consecutive-failure
rule in [alerts.md](alerts.md) A1). Faults with no automated signal — a wrong
score, a subtly malformed export — are detected on customer report only.

**The honest bit:** an S1 that begins at 02:00 on a Saturday will most likely be
acknowledged on Monday morning unless the operator happens to see the email.
Anyone who needs better than that needs §6.

---

## 4. Security incident notification (a stricter, separate clock)

Response targets above are about *engineering effort*. Notification is a
different obligation and is committed to independently, because a 72-hour clock
is achievable with email while a 15-minute one is not:

| Obligation | Commitment |
|---|---|
| Notify an affected customer of a confirmed reportable security incident | Without unreasonable delay, and **no later than 72 hours** after confirmation |
| Notify of a suspected incident under investigation | As soon as SARO has enough information to be useful, without waiting for full RCA |
| Provide known scope (data categories, tenants, time window) | With the initial notification, updated as the investigation proceeds |
| Post-incident report | Within **10 business days** of resolution |

Where a signed BAA or DPA specifies shorter timelines, **the agreement
governs** — this document is the floor, not a cap. HIPAA breach-notification
obligations flow through the BAA (see `compliance/baa/`).

---

## 5. Channels and escalation

| Purpose | Channel |
|---|---|
| Support requests, S2–S4 | Email to the designated support address |
| Suspected security incident, S1 | Email marked **SECURITY**, to the security contact |
| In-product | Feedback widget (STORY-382) — triage, **not** an incident channel |

**Escalation path (honest, solo-operator):**

1. **Operator (Venky)** — first and, in practice, only responder.
2. **If unreachable >4 business hours during an active S1:** the customer should
   escalate directly to the named commercial contact in their agreement.
3. **Named backup:** **[HUMAN — OPEN]** no backup responder is currently named.
   This is the single largest gap in this model: a solo operator who is ill or
   on a flight has no cover. Options are (a) name a trusted engineer with
   emergency access, (b) contract a retainer, or (c) disclose the gap to pilot
   customers and price accordingly. **Do not leave this blank before the pilot
   converts.**
4. **Specialist support** stays as-is: legal counsel for breach notification,
   compliance SME for rule-pack correctness disputes.

---

## 6. What changes with a paging tier

For an owner deciding whether to fund it. Nothing below is committed today.

| | Today (email) | With paging (e.g. PagerDuty/Pushover) |
|---|---|---|
| S1 response, in hours | 1 business hour | 30 minutes |
| S1 response, out of hours | Best-effort, no commitment | 1 hour, 24×7 |
| Detection → notification | ≤60 min, seen when email is checked | ≤60 min, pushed to a device |
| Cost | £0 | Subscription + the human cost of being on call |

The technical work is small — the canary's failure step gains a webhook. **The
commitment is the expensive part**, and it should not be offered until someone
is genuinely willing to be woken.

---

## 7. Review

Reviewed with the SLO/SLA documents, and after any S1. If a target is missed
twice, change the target or the operating model — do not relabel the incidents.
