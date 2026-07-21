# SARO Alert Rules & Thresholds

**Story:** STORY-368 · **Owner:** Venky (operator) · Companion: [runbooks.md](runbooks.md)

Every threshold below is a **choice with a reason**. An unjustified number gets
tuned by whoever is most annoyed by it at the time, which is how alerting decays
into noise and then into being ignored.

Sizing note: this is a solo-operator model. Fewer, higher-signal alerts beat
comprehensive coverage nobody reads — an alert that fires weekly and is dismissed
weekly is worse than no alert, because it trains the operator to dismiss.

---

## 1. Signals

| Source | What it gives |
|---|---|
| `GET /health` | `ok` / `degraded` / `schema_mismatch`, `db_ok`, version. 503 when unhealthy. |
| `GET /metrics` | Bearer-token gated. Global aggregates only — **no tenant labels** (INV-3). |
| Canary workflow | End-to-end liveness every 30 min; failure notifies via GitHub. |

Metrics counters are **process-local and reset on restart**. They support rate
and ratio questions ("what fraction of requests failed in the last hour"), not
lifetime totals. Do not build an alert that assumes a counter's absolute value.

---

## 2. Alert rules

### A1 — Service down (P1)
**Condition:** canary cannot reach `GET /health`, or it returns non-200, for two
consecutive runs (~30 min apart).
**Why two:** a single failure is indistinguishable from a Fly machine restart or
a transient network blip. Two consecutive misses means it is not self-healing.
**Detection latency:** ≤60 min.

### A2 — Database unreachable (P1)
**Condition:** `saro_db_reachable == 0`, or `/health` reports `db_ok: false`.
**Why immediate (no consecutive-run requirement):** unlike the app, the database
has no restart-and-recover path that resolves on its own, and every evidence
write is blocked while it is down.

### A3 — Schema mismatch after deploy (P1)
**Condition:** `/health` returns `schema_mismatch`.
**Why:** the running image expects migrations the database does not have. Serving
in this state risks writing evidence against a schema that will change. This is
deploy-triggered, so it is checked in the post-deploy canary as well.

### A4 — Ingestion stalled (P2)
**Condition:** `saro_ingestion_lag_seconds > 5400` (**90 minutes**).
**Why 90:** the mirror-async pull is assumed **hourly**. 90 minutes tolerates one
missed cycle plus scheduling jitter, but catches two consecutive misses.
**If the pull cadence changes, this number must change with it** — it is derived
from the cadence, not chosen independently.
**Special value:** `-1` means *unknown* (no checkpoints exist yet) and must not
be treated as "zero lag". A fresh tenant with no ingest yet is not an incident.

### A5 — Elevated error rate (P2)
**Condition:** `5xx` responses exceed **5%** of requests over a 30-minute window,
with a floor of 20 requests in the window.
**Why the floor:** without it, one failed request during a quiet night is 100%
and pages the operator for nothing.
**Why 5%:** normal steady state is ~0%; 5% is unambiguously wrong while
tolerating a brief restart.

### A6 — Canary evaluation failed (P2)
**Condition:** the synthetic end-to-end evaluation fails while `/health` is OK.
**Why separate from A1:** the API being up while an evaluation cannot complete is
a *different* fault — usually a rule-pack, migration, or engine problem — and has
a different first action.

### A7 — Backup integrity manifest not captured (P2)
**Condition:** the scheduled `scripts/verify_restore_integrity.py snapshot` run
fails, or the newest off-platform manifest is older than 48 hours.
**Why 48h:** with daily capture, one missed run is tolerable; two consecutive
misses mean a restore would have no recent reference to verify against.
**Why it matters:** a restore verified only by SARO's internal chain verifiers
proves self-consistency, **not** completeness — a truncated chain hashes
correctly. Without a manifest, silent evidence loss is undetectable.
See [dr-backup.md](dr-backup.md) §4.

---

## 3. Delivery channel

**Chosen: GitHub Actions failure notifications → operator email.**

Rationale, honestly: it is the channel the operator already watches daily, needs
no new vendor (an analytics/paging SaaS is a security-review question — see
Epic 15), costs nothing, and has no additional secret to rotate. Its weakness is
real and stated: **email is not a pager.** Overnight detection is best-effort,
and the SLA (STORY-369) must not promise faster response than this channel can
support.

**Upgrade path** when a pilot's severity commitments require it: add a Pushover
or PagerDuty webhook to the canary workflow's failure step. Deliberately *not*
done now — an unwatched paging integration is worse than an honest email.

**[HUMAN — OPEN]** Confirm the destination address, and whether a paging tier is
wanted before the SummitCare pilot converts.

---

## 4. What is deliberately NOT alerted

- **Per-tenant volume or error rates.** Metrics carry no tenant labels by design
  (INV-3); that view lives in-product behind authorization.
- **Latency SLO burn.** Defined in STORY-369 once there is enough measured data
  for a target to be honest rather than invented.
- **Individual rule-pack findings.** Those are product output for the customer's
  review, not operational events for the operator.
