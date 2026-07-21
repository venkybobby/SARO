# SARO Service Level Agreement — DRAFT v0.1

> **DRAFT — NOT FOR EXTERNAL USE.** This is an engineering-authored starting
> point for a contract term. It has **not** been reviewed by counsel and must
> not be sent to a customer, attached to a proposal, or referenced in a
> procurement response until it has been. Numbers here are chosen to be
> defensible against the current architecture (see
> [../ops/slo.md](../ops/slo.md) §1), not to be attractive.

**Story:** STORY-369 · **Owner:** Venky · **Status:** DRAFT, pending
counsel + owner review · **Applies to:** pilot-phase engagements

---

## 1. Service commitment

SARO targets **99.5% monthly availability** of the SARO API.

**Why 99.5% and not 99.9%.** SARO currently runs a single machine in a single
region (`dfw`) with a managed database dependency and no automated failover.
99.9% permits 43 minutes of unavailability per month — less than a single bad
deploy plus rollback can consume. Committing to it would be a number we could
not honour or measure. 99.5% permits approximately 3 hours 39 minutes per month
and reflects what the architecture can actually deliver.

**Upgrade path.** Multi-machine and multi-region deployment, automated failover,
and continuous metric retention are the prerequisites for a higher tier. A
higher commitment should follow that work, not precede it.

---

## 2. How availability is measured

Availability is measured by an automated probe of `GET /health` executed **every
30 minutes**, counting a probe as successful when the endpoint returns HTTP 200
and reports database connectivity.

```
Availability % = (successful probes / total probes in the month) × 100
```

**Measurement granularity is 30 minutes**, disclosed deliberately: an
interruption shorter than the probe interval may not be recorded, and a single
failed probe may be counted as up to 30 minutes of unavailability. Both parties
should read the figure as accurate to within that interval, not to the second.

Availability is measured **at the SARO API boundary**. Customer network paths,
identity providers, and the customer's own cloud log exports are outside it.

---

## 3. Exclusions

Unavailability arising from the following is excluded from the calculation:

1. **Scheduled maintenance** announced per §4.
2. **Customer-side causes** — customer network, credentials, IdP/SSO
   configuration, or a customer-owned log export that has stopped. SARO reads
   customer-owned storage read-only and cannot restart a customer's export.
3. **Upstream provider outages** — Fly.io or Supabase platform incidents. Stated
   plainly rather than buried: SARO inherits its hosting providers'
   availability and cannot exceed it.
4. **Force majeure** and events outside SARO's reasonable control.
5. **Customer use outside documented limits**, including request volumes beyond
   agreed rate limits.

---

## 4. Maintenance windows

- **Standard window:** Sundays 02:00–04:00 UTC.
- **Notice:** at least 72 hours in advance for planned work expected to cause
  interruption.
- **Emergency maintenance** (security fixes, data-integrity risk) may occur
  without notice; notification follows as soon as practicable.
- Announcements are posted per the status and degradation communication
  procedure (STORY-372).

---

## 5. Support and incident response

**Support severity definitions, response targets, and escalation are defined in
the support model and the incident response plan — not in this document.**

| Topic | Authoritative source |
|---|---|
| Severity levels (S1–S4), response and resolution targets | [`../ops/support-model.md`](../ops/support-model.md) §2–§3 |
| Security-incident notification timelines | [`../ops/support-model.md`](../ops/support-model.md) §4 |
| Incident detection, containment, customer notification | `docs/incident-response-plan.md` |
| Security-incident notification commitments | `docs/incident-response-plan.md` |

This is a deliberate pointer rather than a copy. Duplicating a severity table
into a contract creates two sources that drift, and the version a customer holds
is the one that is hardest to correct.

> ✅ **FND-064 reconciled (STORY-371).** The support model now exists and the
> incident response plan (v1.1) states response targets the current alerting
> channel can actually deliver. This document is no longer blocked on that
> reconciliation.
>
> ⚠️ **Still required before external use:** (1) counsel review, and (2) a
> **named backup responder** — the support model §5 records that none exists,
> which means an S1 during operator absence has no cover. A customer is entitled
> to know that before signing, and it should be closed rather than disclosed if
> the pilot converts.

---

## 6. Remedies

**No service credits are offered during the pilot phase.** Stated explicitly
rather than omitted: a customer should know the commitment is a good-faith
operational target backed by measurement, not a financially-backed guarantee.
Credit structures, if any, are a commercial decision for the production
agreement.

---

## 7. Reporting

On request, SARO will provide the availability figure for a completed month,
together with the probe data it was computed from and any incidents recorded
under the incident response plan.

---

## 8. Review

This draft is reviewed alongside the SLO document. Any change to the
architecture that alters what is achievable (multi-region, failover, retention)
requires this document to be revisited **before** a higher commitment is offered.

---

*Not legal advice. Requires review by qualified counsel before use in any
customer agreement.*
