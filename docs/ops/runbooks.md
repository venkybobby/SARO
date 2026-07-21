# SARO Alert Runbooks

**Story:** STORY-368 · Companion: [alerts.md](alerts.md) · Incident process:
[../incident-response-plan.md](../incident-response-plan.md)

One runbook per alert: **symptom → likely cause → first action**. Written to be
followed at 2am by someone who did not write the code and is not fully awake, so
each starts with the single command that tells you the most.

**Before anything else:** if customer evidence integrity might be affected,
STORY-371's incident process takes precedence over restoring service quickly —
a fast recovery that corrupts the audit chain costs more than the outage.

---

## A1 — Service down

**Symptom:** canary cannot reach `/health` for two consecutive runs.

**First command**
```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://saro-backend.fly.dev/health
fly status -a saro-backend
```

| Likely cause | Signal | First action |
|---|---|---|
| Machine stopped/crashed | `fly status` shows stopped | `fly machine restart -a saro-backend`; then check `fly logs` for the crash |
| Bad deploy | failure began at a release | `fly releases -a saro-backend`, roll back (see `release-rollback.md`, STORY-375) |
| Out of memory | OOM in `fly logs` | restart to restore service, then size the machine — do not just keep restarting |
| Fly platform incident | Fly status page degraded | nothing to fix locally; post to the status page (STORY-372) and wait |

**Do not** redeploy as a first reflex — if the cause is a bad image, redeploying
the same image repeats the outage.

---

## A2 — Database unreachable

**Symptom:** `saro_db_reachable == 0` or `/health` shows `db_ok: false`.

**First command**
```bash
curl -sS https://saro-backend.fly.dev/health | jq
# then check the Supabase project status page / dashboard
```

| Likely cause | Signal | First action |
|---|---|---|
| Supabase paused or in maintenance | project dashboard | wait/resume; the app returns 503 on DB paths by design |
| Credential rotated without updating Fly | auth_failure in logs | re-set `DATABASE_URL` (secrets-runbook §3), verify `/health` |
| Connection pool exhausted | timeouts under load, app otherwise fine | restart the app to drop leaked connections, then look for the leak — a restart is symptom relief, not the fix |
| Wrong pooler URL after config change | "Tenant or user not found" | the username needs the project-ref suffix — see the startup log message in `main.py` |

**Evidence note:** while the DB is unreachable, evaluations fail rather than
producing partial evidence. That is the intended failure mode; do not add a
bypass to "keep things working".

---

## A3 — Schema mismatch after deploy

**Symptom:** `/health` returns `schema_mismatch`.

**First command**
```bash
curl -sS https://saro-backend.fly.dev/health | jq '.missing_migrations'
```

| Likely cause | Signal | First action |
|---|---|---|
| Migration in the image never applied | missing migration ids listed | apply the pending migrations, re-check `/health` |
| Deploy raced ahead of the migration step | began exactly at a release | roll back to the previous release, apply migrations, redeploy |
| Migration failed halfway | error in deploy logs | **do not** hand-patch the schema; restore/repair via the documented migration path so `schema_migrations` stays truthful |

---

## A4 — Ingestion stalled

**Symptom:** `saro_ingestion_lag_seconds > 5400` (90 min).

**First command**
```bash
curl -sS -H "Authorization: Bearer $METRICS_TOKEN" \
  https://saro-backend.fly.dev/metrics | grep saro_ingestion_lag_seconds
```

| Likely cause | Signal | First action |
|---|---|---|
| Client-side export stopped | lag grows steadily, SARO healthy | contact the customer — the export is on their side; SARO is read-only (INV-6) and cannot restart it |
| Cross-account role broken | AssumeRole errors in logs | check the role ARN/external id in the tenant's log-source config (STORY-408) |
| Pull job not running | no ingest log lines | restart/trigger the pull; confirm the schedule |
| Genuinely no traffic | customer sent no invocations | **not an incident.** Confirm with the customer before escalating |

**`-1` means unknown, not zero.** A tenant that has never ingested has no
watermark; that is a provisioning state, not a stall.

---

## A5 — Elevated error rate

**Symptom:** 5xx > 5% over 30 min (min 20 requests).

**First command**
```bash
fly logs -a saro-backend | grep -i 'unhandled_request_exception' | tail -50
```

| Likely cause | Signal | First action |
|---|---|---|
| Regression in a recent deploy | started at a release | roll back first, diagnose after |
| Downstream (DB/Redis) degraded | errors cluster on one path | check A2; Redis failures should fail *open* on rate limiting |
| One tenant sending malformed input | errors cluster on ingest | the adapter should skip bad records — a 5xx here is a bug worth an FND |
| Load beyond capacity | latency up, errors follow | scale the machine; then decide whether the limit is the right one |

---

## A6 — Canary evaluation failed (API healthy)

**Symptom:** the end-to-end evaluation fails while `/health` is OK.

**First command**
```bash
gh run list --workflow=canary.yml --limit 5
gh run view --log-failed
```

| Likely cause | Signal | First action |
|---|---|---|
| Rule-pack load failure | pack load error in logs | a malformed pack refuses to load by design — fix or roll back the pack version |
| Demo tenant credentials rotated | 401 from the canary | re-seed demo credentials (secrets-runbook), update the workflow secret |
| Engine regression | evaluation returns unexpected shape | check the last engine change; the conformance and regression suites should have caught it — if they did not, that gap is itself an FND |
| Migration changed a contract | began after a migration | verify the API contract test suite ran on that PR |

---

## A7 — Backup verification failed

**Symptom:** the backup/restore verification job fails.

Placeholder until STORY-370 lands `scripts/verify_restore_integrity.py`. Until
then, treat a failure as **unverified backups** and escalate: an unverified
backup is a belief, not a control.

---

## Escalation

Solo-operator model. If an incident exceeds ~2 hours without a path to
resolution, or customer evidence integrity is in question, follow the
notification and escalation steps in the incident response plan and the support
model (STORY-371) rather than continuing to debug alone.
