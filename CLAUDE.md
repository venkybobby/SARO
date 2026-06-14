# SARO — Smart AI Risk Orchestrator v8.0.0

## ⚠️ CRITICAL — Repository & PR Target (read before every commit/PR)

| What | Value |
|---|---|
| **Canonical GitHub repo** | **https://github.com/venkybobby/SARO** |
| **Git remote name** | `origin` (maps to the URL above) |
| **All PRs must target** | `venkybobby/SARO` — **never** `venkybobby/saro-platform` |
| **Push command** | `git push origin <branch>` |

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

**Infrastructure** — canonical source of truth: [@docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Stack is frozen on Fly.io + Supabase (PT-012); Railway/Koyeb/Neon are SUPERSEDED.
| Layer | Service |
|---|---|
| Backend API | Fly.io — FastAPI + uvicorn (`saro-backend`) |
| Frontend | Fly.io — React/Vite (`sarofrontend`) |
| Database | Supabase PostgreSQL Pro |
| Cache | Redis (optional; non-evidence paths) |
| CI/CD | GitHub Actions → `flyctl deploy` (`deploy.yml`) |
| Monitoring | Sentry · Prometheus/Grafana |

## SARO Positioning — Non-Negotiables

These six constraints are **immutable**. No PR may weaken them.

1. **Accepts only** `prompt` + `raw_output` — SARO's core scoring never calls external AI models, and never generates the output it audits. *One disclosed, off-by-default exception:* the optional Gate-3 LLM-judge verification pass calls a configured provider (default Anthropic; model via `SARO_LLM_JUDGE_MODEL`) **only** when a tenant sets its API key — see the "External Model Usage" section of @docs/COMPLIANCE_CLAIMS_MATRIX.md.
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
- [@.claude/skills/saro-dev](.claude/skills/saro-dev/SKILL.md) — E2E implementation pipeline (master orchestrator)
- [@.claude/skills/auto-pr-review](.claude/skills/auto-pr-review/SKILL.md) — autonomous PR review before merge
- [@.claude/skills/tdd-enforcer](.claude/skills/tdd-enforcer/SKILL.md) — Red-Green-Refactor TDD cycle
- [@.claude/skills/security-audit](.claude/skills/security-audit/SKILL.md) — OWASP + PII + SARO surface audit
- [@.claude/skills/ci-debugger](.claude/skills/ci-debugger/SKILL.md) — autonomous CI failure diagnosis & fix

## References

- **GitHub repo:** https://github.com/venkybobby/SARO (remote name: `origin`) — always push/PR here
- Compliance boundaries: @docs/COMPLIANCE_CLAIMS_MATRIX.md
- API prefix: `/api/v1/`
- Port: `$PORT` (Railway injects)
- Health endpoint: `GET /health` → `{"app":"SARO","version":"<app.version>","db_ok":true}`

## Story Workflow — never paste prompts
- New work: create `specs/stories/STORY-###.md` from `_TEMPLATE.md`, then run `/story STORY-###`.
- New bug/review finding: run `/finding <description>` — it logs an FND, writes a pinning regression test (red→green), and updates `tests/regression/manifest.yaml`.
- Standards live in `docs/engineering-standards.md`. Core invariants: quality ratchet (`quality/baseline.json`) never goes backward; every bug fix ships a regression test; independent `reviewer`/`security-auditor` agents must approve before merge; max 3 gate cycles then escalate — never weaken a test to get green.
