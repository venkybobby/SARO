# SARO — Smart AI Risk Orchestrator v8.0.0

## ⚠️ CRITICAL — Repository & PR Target (read before every commit/PR)

| What | Value |
|---|---|
| **Canonical GitHub repo** | **https://github.com/venkybobby/SARO** |
| **Git remote name** | `saro` (maps to the URL above) |
| **All PRs must target** | `venkybobby/SARO` — **never** `venkybobby/saro-platform` |
| **Push command** | `git push saro <branch>:main` |

> `venkybobby/saro-platform` is a **mirror/legacy remote** — do NOT create PRs there.

## Architecture

```
SARO/
├── main.py              # FastAPI entry point (uvicorn main:app)
├── engine.py            # Core scoring engine: DIR formula, SHAP, KS-test drift
├── auth.py / database.py / models.py / schemas.py
├── routers/             # scan, traces, output_audit, reports, auth, clients,
│                        # dashboard, github_integration, demo
├── frontend/            # Streamlit UI (migrating → React/Vite on Vercel)
├── saro-data-framework/ # Offline evaluation: TruthfulQA, PII, toxicity batch jobs
├── tests/               # pytest suite (test_new_features.py, test_frontend_login.py)
├── .claude/             # Claude Code config: skills/, settings.json
└── docs/                # COMPLIANCE_CLAIMS_MATRIX.md
```

**Infrastructure (target)**
| Layer | Service |
|---|---|
| Backend API | Railway Pro — FastAPI + uvicorn |
| Frontend | Vercel Pro — React/Vite (migration in progress) |
| Database | Supabase PostgreSQL Pro |
| Cache | Railway Redis |
| CI/CD | GitHub Actions + `anthropics/claude-code-action@v1` |
| Monitoring | Railway Observability · Sentry · Prometheus/Grafana |

## SARO Positioning — Non-Negotiables

These six constraints are **immutable**. No PR may weaken them.

1. **Accepts only** `prompt` + `raw_output` — never calls external AI models.
2. **Returns only** risk score (0–100 int), TRACE timeline, remediation guidance.
3. **Never writes** to client systems.
4. **Never certifies** compliance (evidence support only — see @docs/COMPLIANCE_CLAIMS_MATRIX.md).
5. **Human-in-the-loop** always — AIGP human certification, not automated sign-off.
6. **Read-only** integration posture across all connectors.

**Frameworks (evidence/reference only):** NIST AI RMF 1.0 · EU AI Act · ISO 42001 · AIGP

## Commit Convention

[Conventional Commits](https://www.conventionalcommits.org/) — enforced in CI.

```
feat(scope): short description
fix(engine): correct KS-test threshold at p=0.05
chore(deps): bump pydantic to 2.9.0
```

Scopes: `engine` `auth` `routers` `frontend` `rules` `deploy` `ci` `docs`

## Testing Requirements

| Layer | Tool | Gate |
|---|---|---|
| Backend unit/integration | `pytest tests/ -q` | Required — all PRs |
| Frontend | `vitest run` (React/Vite) | Required after migration |
| E2E | Playwright | Required for flow changes |
| Performance | Locust | Required before Railway deploy |
| Security | `pip-audit` + OWASP patterns | Scheduled Monday 02:00 UTC |

**All PRs must pass CI before merge. No exceptions.**

## Team

| Name | Role |
|---|---|
| Venky | Lead Engineer |
| Alex Rivera | ML / scoring engine |
| Jordan Lee | Backend / infra |
| Sam Patel | QA |
| Taylor Kim | QA |

## Skills (deeper context)

See `.claude/skills/` for rule-specific guidance Claude follows automatically:

- [@.claude/skills/rule-pack-edit](.claude/skills/rule-pack-edit/SKILL.md) — rule_packs/ edits
- [@.claude/skills/risk-scoring](.claude/skills/risk-scoring/SKILL.md) — scoring & TRACE
- [@.claude/skills/api-conventions](.claude/skills/api-conventions/SKILL.md) — endpoint patterns
- [@.claude/skills/compliance-guard](.claude/skills/compliance-guard/SKILL.md) — audit trail / claims
- [@.claude/skills/test-patterns](.claude/skills/test-patterns/SKILL.md) — pytest / E2E / Locust
- [@.claude/skills/deploy-railway](.claude/skills/deploy-railway/SKILL.md) — Railway + Supabase deploy
- [@.claude/skills/drift-sentinel](.claude/skills/drift-sentinel/SKILL.md) — KS-test / circuit breaker

## References

- **GitHub repo:** https://github.com/venkybobby/SARO (remote name: `saro`) — always push/PR here
- Compliance boundaries: @docs/COMPLIANCE_CLAIMS_MATRIX.md
- API prefix: `/api/v1/`
- Port: `$PORT` (Railway injects)
- Health endpoint: `GET /health` → `{"app":"SARO","version":"<app.version>","db_ok":true}`
