# SARO v8.0.0 — Migration Runbook

**Migration:** Neon PostgreSQL → Supabase · Koyeb → Railway
**Status:** ✅ COMPLETED 2026-05-08 — Neon decommissioned, Supabase active
**Owner:** Jordan Lee (Backend) + Venky (Lead)

---

## 0. Pre-flight checklist

Complete every item before starting Phase 1.

- [ ] All team members notified of maintenance window
- [ ] Sentry error rate baseline captured (last 24h)
- [ ] Current Neon connection string saved securely (not in git)
- [ ] Supabase project created, `saro-db` project name confirmed
- [ ] Railway project created, `saro-platform` project name confirmed
- [ ] `pg_dump` version ≥ 15 installed locally (`pg_dump --version`)
- [ ] `psql` version ≥ 15 installed locally
- [ ] Rollback decision time agreed: if not green within **30 min** of cutover, roll back
- [ ] `tests/` suite passing on current branch (`python -m pytest tests/ -q`)

---

## Phase 1 — Neon → Supabase (Database)

### 1.1 Export from Neon

```bash
# Set from Neon dashboard → Connection Details
export NEON_URL="postgresql://neondb_owner:[PASSWORD-ROTATED]@ep-spring-wave-ai5rol1x-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
# NOTE: Neon project decommissioned 2026-05-08. Password rotated. This line is for historical reference only.

# Full schema + data dump (custom format for parallel restore)
pg_dump \
  "$NEON_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --verbose \
  --file=saro_neon_export_$(date +%Y%m%d_%H%M%S).dump

# Verify dump is non-empty
ls -lh saro_neon_export_*.dump
```

> **Save the dump file.** It is your rollback artefact. Do not delete until migration is fully verified.

### 1.2 Capture pre-migration record counts (Neon)

```bash
psql "$NEON_URL" <<'SQL'
SELECT 'tenants'       AS tbl, COUNT(*) FROM tenants
UNION ALL
SELECT 'users',               COUNT(*) FROM users
UNION ALL
SELECT 'audits',              COUNT(*) FROM audits
UNION ALL
SELECT 'scan_reports',        COUNT(*) FROM scan_reports
UNION ALL
SELECT 'audit_traces',        COUNT(*) FROM audit_traces
UNION ALL
SELECT 'audit_metadata',      COUNT(*) FROM audit_metadata;
SQL
```

Save this output — you will compare it against Supabase after restore.

### 1.3 Capture hash fingerprints (Neon)

These hashes guard audit record integrity. Verify they are unchanged after restore.

```bash
psql "$NEON_URL" <<'SQL'
-- export_hash distribution across scan_reports
SELECT
  COUNT(*)                               AS total_reports,
  COUNT(export_hash)                     AS with_export_hash,
  MD5(STRING_AGG(export_hash::text, ',' ORDER BY id))
                                         AS export_hash_fingerprint
FROM scan_reports;

-- scan_hash distribution across audit_traces
SELECT
  COUNT(*)                               AS total_traces,
  COUNT(scan_hash)                       AS with_scan_hash,
  MD5(STRING_AGG(scan_hash::text, ',' ORDER BY id))
                                         AS scan_hash_fingerprint
FROM audit_traces;
SQL
```

**Record both `*_fingerprint` values.** These are your integrity anchors.

### 1.4 Prepare Supabase

```bash
# Supabase dashboard → Project Settings → Database → Connection string → URI (pooler, port 6543)
export SUPABASE_URL="postgresql://postgres.fktfhtygvwqlmoazmhdf:[YOUR-PASSWORD]@aws-1-us-west-1.pooler.supabase.com:5432/postgres?sslmode=require"

# For pg_restore use the DIRECT connection (bypasses PgBouncer — needed for COPY protocol)
export SUPABASE_DIRECT="postgresql://postgres.fktfhtygvwqlmoazmhdf:[YOUR-PASSWORD]@db.fktfhtygvwqlmoazmhdf.supabase.co:5432/postgres?sslmode=require"

# Confirm connectivity
psql "$SUPABASE_DIRECT" -c "SELECT version();"
```

### 1.5 Restore to Supabase

```bash
# pg_restore with direct connection (pooler does not support COPY protocol)
pg_restore \
  --dbname="$SUPABASE_DIRECT" \
  --no-owner \
  --no-acl \
  --jobs=4 \
  --verbose \
  saro_neon_export_*.dump 2>&1 | tee restore_log.txt

# Check for errors (warnings about extensions are normal; errors are not)
grep -i "error" restore_log.txt | grep -v "WARNING"
```

### 1.6 Post-restore validation

```bash
# 1. Row count comparison — must match 1.2 exactly
psql "$SUPABASE_DIRECT" <<'SQL'
SELECT 'tenants'       AS tbl, COUNT(*) FROM tenants
UNION ALL
SELECT 'users',               COUNT(*) FROM users
UNION ALL
SELECT 'audits',              COUNT(*) FROM audits
UNION ALL
SELECT 'scan_reports',        COUNT(*) FROM scan_reports
UNION ALL
SELECT 'audit_traces',        COUNT(*) FROM audit_traces
UNION ALL
SELECT 'audit_metadata',      COUNT(*) FROM audit_metadata;
SQL

# 2. Hash chain verification — fingerprints must match 1.3
psql "$SUPABASE_DIRECT" <<'SQL'
SELECT
  COUNT(*)                               AS total_reports,
  COUNT(export_hash)                     AS with_export_hash,
  MD5(STRING_AGG(export_hash::text, ',' ORDER BY id))
                                         AS export_hash_fingerprint
FROM scan_reports;

SELECT
  COUNT(*)                               AS total_traces,
  COUNT(scan_hash)                       AS with_scan_hash,
  MD5(STRING_AGG(scan_hash::text, ',' ORDER BY id))
                                         AS scan_hash_fingerprint
FROM audit_traces;
SQL
```

**If any fingerprint differs: STOP. Do not proceed to Phase 2. Investigate restore log.**

### 1.7 Run SARO test suite against Supabase

```bash
# Point tests at Supabase (direct port for tests — not pooler)
export DATABASE_URL="$SUPABASE_DIRECT"

python -m pytest tests/ -v --tb=short 2>&1 | tee test_supabase.txt

# Must be 100% green before continuing
grep -E "passed|failed|error" test_supabase.txt | tail -5
```

### 1.8 Supabase Row Level Security

```sql
-- Supabase enables RLS by default on new tables.
-- SARO connects as service-role (bypasses RLS), so this is safe — but confirm:
-- Supabase dashboard → Table Editor → each table → RLS tab
-- Ensure service_role has full access or RLS is disabled for SARO tables.

-- Quick check (run in Supabase SQL editor):
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

---

## Phase 2 — Koyeb → Railway (Compute)

### 2.1 Build and validate Docker image locally

```bash
# Build production image
docker build -f Dockerfile -t saro-api:8.0.0 .

# Smoke test: start container with Supabase env vars
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="$SUPABASE_DIRECT" \
  -e REDIS_URL="redis://localhost:6379" \
  -e JWT_SECRET_KEY="local-test-secret-not-for-prod" \
  -e JWT_ALGORITHM="HS256" \
  -e ACCESS_TOKEN_EXPIRE_MINUTES="15" \
  -e PORT=8000 \
  saro-api:8.0.0 &

sleep 8

# Health check
curl -sf http://localhost:8000/health | python3 -m json.tool

# Kill test container
docker ps -q --filter ancestor=saro-api:8.0.0 | xargs docker stop
```

Expected response:
```json
{"app": "SARO", "version": "1.0.0", "db_ok": true, ...}
```

### 2.2 Set up Railway project

```bash
# Install Railway CLI if not already installed
# (adds to PATH — no pip install needed)
curl -fsSL https://railway.app/install.sh | sh

# Login
railway login

# Link to existing Railway project
railway link
```

### 2.3 Configure environment variables on Railway

Set these in **Railway dashboard → saro-api service → Variables** (never CLI — no shell history):

| Variable | Value | Source |
|---|---|---|
| `DATABASE_URL` | Supabase pooler URI (port 6543) | Supabase dashboard |
| `REDIS_URL` | Railway Redis private URL | Railway Redis service |
| `JWT_SECRET_KEY` | 256-bit hex secret | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | `HS256` | Fixed |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Fixed |
| `MIN_BATCH_SAMPLES` | `50` | Match Koyeb value |
| `INCIDENT_TOP_K` | `10` | Match Koyeb value |
| `BAYESIAN_PRIOR_ALPHA` | `1.0` | Match Koyeb value |
| `CONFIDENCE_THRESHOLD` | `0.85` | Match Koyeb value |
| `SENTRY_DSN` | Sentry project DSN | Sentry dashboard |
| `APP_VERSION` | `8.0.0` | Fixed |
| `ENV` | `production` | Fixed |
| `LOG_LEVEL` | `info` | Fixed |
| `CORS_ALLOWED_ORIGINS` | `https://saro.vercel.app` | Vercel project URL |

> `PORT` is injected automatically by Railway. Do **not** set it manually.

### 2.4 Deploy to Railway

```bash
# Trigger deploy from current HEAD
railway up --detach

# Watch logs
railway logs --tail
```

Wait for: `Application startup complete` from uvicorn workers.

### 2.5 Verify Railway deployment

```bash
# Get Railway service URL
export RAILWAY_URL=$(railway domain)

# Health check
curl -sf "https://$RAILWAY_URL/health" | python3 -m json.tool

# Auth smoke test (should return 401)
curl -sf -o /dev/null -w "%{http_code}" "https://$RAILWAY_URL/api/v1/scans"
# Expected: 401

# Confirm version header
curl -I "https://$RAILWAY_URL/health" | grep -i "x-saro-version"
```

### 2.6 Run full test suite against Railway

```bash
export API_BASE_URL="https://$RAILWAY_URL"
python -m pytest tests/ -v --tb=short 2>&1 | tee test_railway.txt
grep -E "passed|failed|error" test_railway.txt | tail -5
```

**All tests must pass before DNS cutover.**

### 2.7 DNS cutover

```
Koyeb CNAME: api.yourdomain.com → <koyeb-service>.koyeb.app
          ↓ change to ↓
Railway CNAME: api.yourdomain.com → <railway-service>.up.railway.app
```

**Steps:**
1. Railway dashboard → saro-api → Settings → Domains → Add custom domain
2. Copy the Railway CNAME target
3. DNS provider → update CNAME record for `api.yourdomain.com`
4. Set TTL to 60s **before** cutover if possible (revert TTL after 24h)
5. Wait for propagation: `watch -n5 dig +short api.yourdomain.com`
6. Confirm traffic is flowing: Railway dashboard → Metrics → request rate

### 2.8 Post-cutover validation (first 30 min)

```bash
# Monitor error rate (Sentry)
# Monitor p99 latency (Railway Observability → Metrics)
# Monitor DB connection count (Supabase dashboard → Reports)

# Tail Railway logs for errors
railway logs --tail | grep -iE "error|exception|traceback"
```

If error rate exceeds pre-migration baseline by >2x, execute rollback immediately.

---

## Rollback Procedures

### Database rollback
> ⚠️ Neon is decommissioned. Database rollback means restoring from the pg_dump
> artefact into a new Supabase project or a local PostgreSQL instance.

```bash
# Create a fresh Supabase project (or local PG) and restore from the dump artefact
pg_restore \
  --dbname="postgresql://postgres:[PASSWORD]@<new-host>:5432/postgres?sslmode=require" \
  --no-owner --no-acl --jobs=4 \
  saro_neon_export_*.dump

# Point Railway at the restored DB
# Railway dashboard → saro-api → Variables → DATABASE_URL → update value

# Redeploy
railway up --detach

# Verify health
curl -sf "https://$RAILWAY_URL/health"
```

### Compute rollback (Railway → Koyeb)

1. Revert DNS CNAME from Railway back to Koyeb target
2. Verify Koyeb service is still running (do not tear down until migration is stable for 72h)

---

## Post-migration cleanup (72h after stable cutover)

- [ ] Delete Neon project (export final backup first)
- [ ] Delete Koyeb service
- [ ] Increase DNS TTL back to 3600s
- [ ] Update `DATABASE_URL` in `.env.example` to Supabase pooler format
- [ ] Tag git commit: `chore(deploy): complete Neon→Supabase + Koyeb→Railway migration`
- [ ] Update team runbook with any deviations encountered

---

*Owner: Jordan Lee (Backend) | Reviewer: Venky (Lead) | Last updated: 2026-05-07*
