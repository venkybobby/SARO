# Maintenance Windows & Degradation Communication

**Story:** STORY-372 · **Owner:** Venky · Companion:
[alerts.md](alerts.md) · [support-model.md](support-model.md) ·
SLA: [../legal/sla-draft-v0.1.md](../legal/sla-draft-v0.1.md) §4

---

## 1. Status page

`https://sarofrontend.fly.dev/status.html` — probes `GET /health` live in the
browser on load and every 60 seconds.

**Why live rather than canary-fed.** A status page rendering a cached file can
display "all systems operational" during an outage. That is worse than having no
status page at all, because it is read precisely when things are broken and it
gives the wrong answer with an air of authority. Live probing cannot go stale.

**Limitation, stated on the page itself:** it is served by the frontend Fly app,
so it shares that app's fate. If the frontend is down, the status page is down.
It is not an independent monitor.

**[HUMAN — OPEN] Independent hosting.** A genuinely independent status page
requires third-party hosting (Statuspage, Better Stack, or a static page on a
different provider) fed by the canary. That means an account, a subscription,
and a vendor entering the security-review surface (Epic 15). Not done
unilaterally. Until then, the honest position is: the status page tells you
about the backend, and its own availability is not guaranteed.

---

## 2. Announcing planned maintenance

Per the SLA: **72 hours' notice** for planned work expected to cause
interruption; standard window **Sundays 02:00–04:00 UTC**.

1. **Decide whether it is customer-visible.** Deploys that do not interrupt
   service are not maintenance events and should not be announced — announcing
   routine deploys trains customers to ignore the channel.
2. **Send notice** (email, from the support address) at least 72 hours ahead:
   - what will be unavailable, and what will keep working
   - the window in **UTC and the customer's local time**
   - expected duration, distinct from the window length
   - what happens to in-flight work (evaluations, exports, ingestion backlog)
3. **Post the window** on the status page footer if it is imminent.
4. **On completion**, confirm within the same thread — including if it
   overran. Silence after a maintenance window reads as "still broken".

## 3. Announcing unplanned degradation

1. **Confirm before announcing.** A retracted incident notice costs more trust
   than a five-minute delay.
2. **First message within the S1/S2 response target** ([support-model.md](support-model.md) §3),
   even when the cause is unknown — say what is affected and that you are
   investigating. "We don't know yet" is a legitimate and useful update.
3. **Update at least hourly** while an S1 is open, even with no news. Gaps get
   filled with worse assumptions than the truth.
4. **On resolution**, state what was affected, for how long, and whether
   evidence integrity was involved. If it was, the incident response plan's
   notification obligations apply and take precedence over a status update.
5. **Post-mortem** within 10 business days (IRP §10) for S1.

## 4. What not to do

- **Do not** mark something operational that has not been verified operational.
- **Do not** describe an outage as "degraded performance" when the service is
  down. The status vocabulary has to survive being read by someone who is
  already annoyed.
- **Do not** announce maintenance retroactively to cover an unplanned outage.
  It is the fastest way to lose a compliance customer's trust, and an evidence
  platform trades on exactly that.
