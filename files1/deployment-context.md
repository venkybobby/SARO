# Skill: SARO Deployment Context

## Infrastructure

| Component | Technology | Notes |
|-----------|-----------|-------|
| Primary deployment | Koyeb | Container-based, auto-scaling |
| Database | Neon PostgreSQL | Serverless Postgres, async driver required |
| Cache / Sessions | Redis | Async client — patched March 2026 (see auth.py) |
| Dev OS | Windows + PowerShell/CMD + Miniconda | Path separators: backslash. Conda envs for Python isolation. |

## Deployment Checklist (pre-Koyeb push)

1. Version string is `8.0.0` across all 8 version-bearing files
2. JWT secret sourced from environment variable — not hardcoded
3. `DELETE /auth/logout` endpoint present and Redis-invalidating
4. PWA router registered at app startup
5. No `time.sleep()` in async code paths
6. Neon connection string from env — not hardcoded
7. Health check endpoint returns `{"version": "8.0.0", "status": "healthy"}`

## Environment Variables (required at runtime)

```
JWT_SECRET=<from secrets manager>
DATABASE_URL=<neon postgresql connection string>
REDIS_URL=<redis connection string>
ANTHROPIC_API_KEY=<claude api key>
KOYEB_APP_NAME=saro-platform
```

## Python Package Install Convention

Always use `--break-system-packages` when installing outside a venv:
```
pip install <package> --break-system-packages
```

## GitHub

- Repo: `github.com/venkybobby/saro-platform`
- ⚠️ A GitHub token was flagged as leaked in March 2026 — confirm revocation before any new token operations
