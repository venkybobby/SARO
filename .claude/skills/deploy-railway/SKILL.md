---
name: deploy-railway
description: Triggered when modifying Dockerfile, railway.toml, docker-compose, CI/CD deploy steps, or any Railway/Supabase configuration. Enforces SARO service topology, env var naming, and health check requirements.
---

# Deploy Railway Skill

## Trigger Conditions
Activate for changes to `Dockerfile.*`, `railway.toml`, `.github/workflows/deploy*.yml`, `docker-compose*.yml`, or any file referencing `RAILWAY_`, `SUPABASE_`, or `DATABASE_URL`.

## Service Topology

```
Railway Project: saro-platform
├── api          (FastAPI)       — main Dockerfile.api
├── redis        (Redis 7)       — Railway managed
└── worker       (optional)      — async job processing

Supabase Project: saro-db
└── PostgreSQL 15 — connection via DATABASE_URL (pooler endpoint)

Vercel Project: saro-frontend
└── React/Vite — env: VITE_API_URL=https://api.saro-platform.up.railway.app
```

## Environment Variable Naming

All env vars must follow this convention (set in Railway dashboard, not committed):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:6543/db?sslmode=require

# Auth
JWT_SECRET_KEY=<256-bit random>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15

# SARO Engine
MIN_BATCH_SAMPLES=50
INCIDENT_TOP_K=10
BAYESIAN_PRIOR_ALPHA=1.0
CONFIDENCE_THRESHOLD=0.85

# Redis
REDIS_URL=redis://default:pass@redis.railway.internal:6379

# Sentry
SENTRY_DSN=https://...@sentry.io/...

# App
APP_VERSION=8.0.0
ENV=production
```

**Never commit secrets. Never hardcode `DATABASE_URL` or `JWT_SECRET_KEY`.**

## Dockerfile Requirements (api)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Health check must be present
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

EXPOSE ${PORT:-8000}
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

## Health Check

`GET /health` must return HTTP 200 with body `{"status":"ok","version":"8.0.0"}` within 10 seconds. Railway routes traffic only after health check passes.

## Private Networking

Services within the same Railway project communicate via private hostnames:

```bash
# From api service, reach Redis:
REDIS_URL=redis://default:$REDIS_PASSWORD@redis.railway.internal:6379

# Never use public URLs for internal service communication
```

## Deploy Checklist

Before triggering a Railway deploy:

- [ ] `python -m pytest tests/ -q` passes locally
- [ ] `pip-audit` shows no high/critical CVEs
- [ ] `APP_VERSION` env var matches `8.0.0`
- [ ] Health endpoint responds to `curl /health`
- [ ] `DATABASE_URL` points to Supabase pooler (port 6543), not direct (5432)
- [ ] Redis TTL set for all cached objects (no indefinite cache entries)

## railway.toml

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile.api"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```
