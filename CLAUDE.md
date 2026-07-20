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

## Failure modes (named, so they can be checked for)

These are failures that have actually happened in this project. Each is named so
a review can ask "is this one present?" instead of relying on vigilance.

| ID | Failure mode | What it looks like | Control |
|---|---|---|---|
| **FM-1** | **Claimed-implemented without commit evidence** | A story/epic/artifact is described as shipped in chat, a summary, or a planning doc, but no commit implements it. Downstream work is then authored on top of the phantom. | Story index rows must cite a resolvable commit SHA to claim `IMPLEMENTED`/`MERGED` — enforced by `scripts/check_story_index.py` in CI. |
| **FM-2** | **Unverified premise in dependent work** | A spec/plan references prior story IDs, corpora, rule-packs, or docs that were never verified to exist. | Premise-verification table required before authoring dependent work (see below). Unverifiable references are marked `PREMISE-UNVERIFIED`, never assumed. |
| **FM-3** | **Drafted read as delivered** | "Produced the backlog" / "published the pack" — a document was written, and the vocabulary let it be remembered as working software. | Closed status vocabulary: `DRAFTED`/`SPECIFIED` for documents, `IMPLEMENTED`/`MERGED` for code. The words "done" and "complete" are rejected by the index gate. |
| **FM-4** | **Status updated later, not in the implementing PR** | The index drifts because status changes are deferred to a follow-up that never happens. | Definition of Done requires the index row to change in the same PR as the implementation. |
| **FM-5** | **Guessing on ambiguity** | Proceeding on an assumption rather than asking. | Historical #1 failure mode — see `docs/engineering-standards.md` hard rule 4. |

### The ledger rule

**The repo is the only status ledger that counts.** Chat history, session
summaries, memory files, and planning documents are *hypotheses* about the
repo's state. They are never evidence. When they disagree with the repo, the
repo is right and the other ledger gets corrected.

### Premise check (before authoring any dependent work)

Any story pack, spec, plan, or epic that references prior artifacts MUST open
with a verification pass:

1. List every referenced artifact (story ID, corpus, rule-pack, document, endpoint).
2. Grep the repo for each one; cite the **file path** that proves it exists.
3. Mark anything you cannot verify as `PREMISE-UNVERIFIED` — do not assume, and
   do not soften it to "presumably exists".
4. If a load-bearing premise is false, surface it before writing dependent
   work, not after.

Worked example: `specs/stories/STORY-PACK-14-19-INDEX.md` §Premise verification.

### Session start

Open every session by reading the relevant story index and recent `git log`.
Treat prior-session claims as hypotheses until the repo confirms them. Do not
carry conversational context forward as established fact.

## Story Workflow — never paste prompts
- New work: create `specs/stories/STORY-###.md` from `_TEMPLATE.md`, then run `/story STORY-###`.
- New bug/review finding: run `/finding <description>` — it logs an FND, writes a pinning regression test (red→green), and updates `tests/regression/manifest.yaml`.
- Standards live in `docs/engineering-standards.md`. Core invariants: quality ratchet (`quality/baseline.json`) never goes backward; every bug fix ships a regression test; independent `reviewer`/`security-auditor` agents must approve before merge; max 3 gate cycles then escalate — never weaken a test to get green.

## Lifecycle
- ALL implementation work runs under the saro-lifecycle skill
  (DISCOVER → SHAPE → PREVIEW → PLAN → BUILD → VERIFY → SELL). Load it at the
  start of any story, finding, feature, fix, or refactor — even when the user
  doesn't mention it. /story and /build are the entry points; individual
  stage prompts are never needed.
- implementation-notes.md (lifecycle template) is created at task start and
  kept truthful; hooks gate on it. Deviations from plan: conservative option,
  log under ## Deviations, keep going.
- Plans lead with tweak-likely decisions (data model, type interfaces,
  user-facing); mechanical refactoring is buried at the bottom.
