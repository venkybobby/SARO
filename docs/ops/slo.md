# SARO Internal SLOs

**Story:** STORY-369 · **Owner:** Venky · **Status:** targets defined;
**continuous measurement not yet in place** (see §4 — this is stated rather than
glossed, because an SLO you cannot measure is an aspiration).

Companion docs: [alerts.md](alerts.md) · [runbooks.md](runbooks.md) ·
external draft: [../legal/sla-draft-v0.1.md](../legal/sla-draft-v0.1.md)

---

## 1. What the infrastructure can actually support

Any SLO number that ignores this is fiction, so it comes first.

| Fact | Source | Consequence |
|---|---|---|
| Single region (`dfw`) | `fly.toml` `primary_region` | A regional Fly incident is a full outage. No failover exists. |
| `min_machines_running = 1` | `fly.toml` | One machine. A restart, OOM, or bad deploy is a full outage, not a degraded one. |
| `auto_stop_machines = 'off'` | `fly.toml` | No cold-start latency, but also no scale-to-zero cost saving — deliberate. |
| Supabase is a hard dependency | `docs/ARCHITECTURE.md` | Availability is the **product** of SARO's and Supabase's, never SARO's alone. |
| Canary probes every 30 min | `.github/workflows/canary.yml` | Outages shorter than ~30 min may not be observed at all (§4). |
| Alerting is email, not paging | `alerts.md` §3 | Overnight detection-to-response is best-effort. |

**Therefore: 99.9% is not achievable or measurable today**, and claiming it
would be a commitment the architecture cannot honour. 99.9% allows 43 minutes of
downtime per month — less than the time a single bad deploy plus rollback takes,
on a single machine, detected by a 30-minute probe.

---

## 2. Service Level Indicators (SLIs)

Each SLI names the metric it is computed from. An SLI without a wired-up signal
is not an SLI.

| SLI | Definition | Signal (STORY-368) |
|---|---|---|
| **Availability** | Fraction of canary probes where `/health` returns 200 and `db_ok` is true | `canary.yml` probe results |
| **Database reachability** | Fraction of scrapes where the DB answered | `saro_db_reachable` |
| **API latency** | p50 / p95 request duration | `saro_http_request_duration_seconds` (histogram buckets) |
| **Ingestion freshness** | Age of the newest observation watermark | `saro_ingestion_lag_seconds` |
| **Evaluation liveness** | Synthetic end-to-end evaluation succeeds | `canary_evaluation.py` |

---

## 3. Objectives (targets)

Internal targets. They are **deliberately stricter than the external SLA** so
there is room to breach an objective and fix it before breaching a commitment.

| SLO | Target | Window | Rationale |
|---|---|---|---|
| Availability | **99.5%** | calendar month | ≈3h39m/month. Achievable on one machine with restarts and a small number of deploys; not so loose it tolerates a bad week. |
| Database reachability | 99.5% | calendar month | Cannot exceed the provider's own availability; tracked separately so a SARO fault is distinguishable from a Supabase fault. |
| API latency p50 | ≤ 250 ms | rolling 7 days | Bucket boundary in the histogram; "feels responsive" for dashboard reads. |
| API latency p95 | ≤ 2.5 s | rolling 7 days | Bucket boundary. Evaluations are the heavy path; 2.5s is honest for synchronous scoring, not aspirational. |
| Ingestion freshness | lag < 90 min, 99% of probes | calendar month | Matches alert A4 exactly — an SLO that disagrees with the alert threshold trains the operator to ignore one of them. |
| Evaluation liveness | ≥ 99% of canary evaluations succeed | calendar month | Liveness of the product path, distinct from the API being up. |

**Error budget.** 99.5% monthly ≈ 3h39m. Once consumed, the next change should
be reliability work, not a feature — the budget is the decision rule, not a
score to report.

---

## 4. Measurement — what is and is not in place today

**This section exists so nobody reads §3 as "achieved".**

| Requirement | Status |
|---|---|
| Signals emitted | ✅ `/health`, `/metrics`, canary (STORY-368) |
| Probe history retained | ✅ implicitly — GitHub Actions run history |
| Metrics **retained over time** | ❌ **not in place.** No Prometheus/TSDB is deployed. `/metrics` is point-in-time, and counters reset on process restart. |
| Latency SLO computable | ❌ blocked on the above — p50/p95 over a window needs retained samples |
| Availability SLO computable | ◐ approximable from canary run history at 30-minute granularity |

**Measurement floor.** With 30-minute probes, availability is measured in
30-minute buckets: an outage shorter than one interval can be missed entirely,
and a single failed probe counts as up to 30 minutes of downtime. The measured
figure is therefore **coarse in both directions**, and no availability claim
finer than that granularity is supportable.

**To make §3 measurable** (not scheduled here — sizing note for the owner):
deploy a scraper with retention (Fly metrics + Grafana Cloud free tier, or
self-hosted Prometheus), point it at `/metrics` with `METRICS_TOKEN`, and
compute the windows from retained series.

---

## 5. Review

Reviewed after any P1 incident and at least quarterly. If a target is missed two
months running, the honest action is to **change the target or the
architecture** — not to relabel the incidents.
