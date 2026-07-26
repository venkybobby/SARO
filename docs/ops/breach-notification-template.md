# Breach Notification Templates (FND-067)

> **Status:** DRAFTED — `[HUMAN — COUNSEL REVIEW]` required before ANY external
> use. These templates exist so customer-facing breach wording is never drafted
> under incident time pressure (`quality/findings.md` FND-067); they are not
> legal advice and have not yet been reviewed by counsel.
>
> Commitment served: `docs/ops/support-model.md` §4 — notify an affected
> customer of a confirmed reportable security incident **without unreasonable
> delay, and no later than 72 hours after confirmation**. The notification
> clock is separate from the response clock (see FND-064).
>
> Recipient: the tenant's recorded `security_contact_email`
> (`tenants.security_contact_email`, set via
> `PUT /api/v1/clients/security-contact`). If NULL, escalate to the tenant's
> admin users and record that fallback in the incident log.

## Rules of use

1. Facts only — state what is confirmed, what is under investigation, and when
   the next update will come. Never speculate about cause or blame.
2. No compliance claims — these notices are evidence of process, not
   certification (`docs/COMPLIANCE_CLAIMS_MATRIX.md` applies to them).
3. Every send is recorded in the incident timeline (who, when, to whom,
   template version).
4. `[HUMAN — COUNSEL REVIEW]` markers gate each template; a marker may only be
   removed by a commit recording the reviewing counsel and date.

---

## 1. Initial notification (within the 72-hour window)

`[HUMAN — COUNSEL REVIEW]`

```
Subject: [SARO] Security incident notification — {INCIDENT_ID}

Dear {SECURITY_CONTACT_NAME},

We are writing to notify you of a confirmed security incident affecting your
SARO tenant ({TENANT_NAME}).

What happened (confirmed facts only):
  {CONFIRMED_FACTS — systems involved, time window, discovery method}

What data or capability was involved:
  {AFFECTED_SCOPE — data categories, features; state plainly if still under
   investigation}

What we have done so far:
  {CONTAINMENT_ACTIONS — e.g. credential rotation, session revocation,
   access suspension, with timestamps}

What we are asking of you:
  {CUSTOMER_ACTIONS — e.g. rotate API keys, review audit events; "none at
   this time" if none}

Next update: no later than {NEXT_UPDATE_TIMESTAMP}.

Incident reference: {INCIDENT_ID}. Reply to this address or contact
{RESPONDER_CONTACT} with questions.

{RESPONDER_NAME}, SARO
```

---

## 2. Update notification (recurring until closure)

`[HUMAN — COUNSEL REVIEW]`

```
Subject: [SARO] Incident {INCIDENT_ID} — update {UPDATE_NUMBER}

Dear {SECURITY_CONTACT_NAME},

Update on the security incident reported {INITIAL_NOTICE_DATE}.

New confirmed findings since the last update:
  {NEW_FACTS — or "none; investigation continues"}

Actions taken since the last update:
  {ACTIONS_WITH_TIMESTAMPS}

Revised scope (if changed):
  {SCOPE_DELTA — state plainly when scope narrowed or widened, and why}

Next update: no later than {NEXT_UPDATE_TIMESTAMP}.

{RESPONDER_NAME}, SARO — incident {INCIDENT_ID}
```

---

## 3. Closure notification

`[HUMAN — COUNSEL REVIEW]`

```
Subject: [SARO] Incident {INCIDENT_ID} — closure notice

Dear {SECURITY_CONTACT_NAME},

The security incident reported {INITIAL_NOTICE_DATE} is now closed.

Final summary of what happened:
  {FINAL_FACTS}

Final assessment of impact to your tenant:
  {FINAL_SCOPE}

Remediation completed:
  {REMEDIATION_SUMMARY — controls added, with references to the relevant
   findings ledger entries where shareable}

Preventive changes:
  {PREVENTIVE_ACTIONS — e.g. new regression pins, gates, monitoring}

The full incident timeline is retained per our retention policy and is
available for your auditors on request.

{RESPONDER_NAME}, SARO — incident {INCIDENT_ID}
```

---

*Owner: Venky (Lead) · Created 2026-07-25 per FND-067 · Counsel review:
`[HUMAN — COUNSEL REVIEW]` pending — record reviewer + date here when done.*
