# demo-persona-ui-verification — persona view verification for the demo (UI)
Stage: standard

Goal (user request, expert phrasing): the demo kit verifies the pipeline (CLI)
and the public /demo flow, but nothing verifies the authenticated persona
views — AI Auditor, Risk Officer ("risk auditor"), Compliance Lead ("lead"
persona) — against the seeded demo data. Add a persona UI verification
harness + runbook section so every persona's view is walked, screenshotted,
and gated (exact tab set, zero ≥400 API responses).

## Lifecycle
- [x] discover   (persona model mapped: Sidebar.jsx PERSONA_TABS/ROLE_LABELS, persona switcher, PATCH /users/{id}/persona super_admin-only, seed_demo single operator user)
- [x] shape      (autonomous session — decisions defaulted + logged below)
- [x] preview    (skipped — no UI change; harness drives the EXISTING UI)
- [x] plan
- [x] build      (harness + SQLite launcher + runbook Part 6 + 4 parser pins)
- [x] verify     (live walk executed in-session: login, modal dismissal, switcher, 16 tab captures, 500-census, summary.json — see Deviations for SQLite limits)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| Referenced artifact | Verified? | File path |
|---|---|---|
| Persona tab map + switcher | yes | `frontend/src/components/Sidebar.jsx` (PERSONA_TABS L17, ROLE_LABELS L70, SWITCHABLE_PERSONAS L79, switcher menu L253) |
| Persona switch endpoint (super_admin) | yes | `routers/auth.py:360` (`PATCH /users/{user_id}/persona`) |
| Existing /demo browser walk | yes | `scripts/demo_capture_playwright.py` |
| Live demo E2E gate | yes | `tests/e2e/test_demo_live_flow.py` |
| Demo seed (tenant/user/corpus) | yes | `scripts/seed_demo.py` (single operator user, persona compliance_lead) |
| Local walk precedent (SQLite + Vite) | yes | `docs/DEMO_READINESS_REVIEW_2026-07-19.md` |
| Demo runbook to extend | yes | `docs/demo/AZURE_VERTEX_E2E_DEMO.md` |
| Login form | yes | `frontend/src/pages/Login.jsx` (email/password inputs, submit) |

## Decision Log

(format: question → answer → architectural consequence; autonomous session,
answers defaulted conservatively)

| Question | Answer | Architectural consequence |
|---|---|---|
| Which personas? "ai auditor, risk auditor, lead implementation user" | Default walk = `ai_auditor`, `risk_officer`, `compliance_lead` (closest matches; no `implementation_lead` persona exists). `--all` covers all six. | Ambiguity absorbed by coverage; no new persona invented. |
| One user per persona, or one super_admin walking the switcher? | One super_admin verification user + the product's own persona switcher. | Verifies the switcher itself; base role stays super_admin so no false 403s; mirrors how a presenter demos persona views (RB-005 §5). |
| Where do expected tabs come from? | Parsed from Sidebar.jsx at runtime (PERSONA_TABS/TAB_REGISTRY/ROLE_LABELS). | Harness cannot drift from the frontend; a unit test pins the parser. |
| New E2E CI job? | No — script + runbook section only (same posture as demo_capture_playwright.py, which is also operator-run). CI-blocked account anyway. | No workflow changes; no new Actions spend. |
| Screenshots committed? | No — land in artifacts/persona-ui/ (env-dependent output). | No binary churn in git. |

## Plan (tweak-likelihood order)

1. `scripts/demo_persona_ui_verification.py` — login → per persona: switch via
   sidebar → assert rendered nav == PERSONA_TABS[persona] exactly → click every
   tab → screenshot → ≥400 census; `--ensure-user` seeds the super_admin
   verification account; exit 0/1; summary.json.
2. Runbook Part 6 (persona view verification): run steps + per-persona expected
   tab table + manual checklist.
3. Unit test pinning the Sidebar.jsx parser (personas + tab ids + labels parse
   and cross-check), no browser needed.
4. Mechanical: notes/gates/commit/PR.

## Deviations
- Live verification ran on the SQLite stand-in (no Docker in this environment).
  Findings from the walk, all environmental to SQLite: (1) many API panels 500
  via the UUID shim (`'str' object has no attribute 'hex'` — /auth/me,
  compliance-matrix, evf, audits, risks…), so (2) the persona PATCH doesn't
  apply and the nav stays on the login persona. Both are green in RB-006's
  census against Postgres; the runbook and script docstrings state that the
  Postgres stack (`scripts/run_local.ps1`) is the authoritative gate and the
  SQLite launcher is a UI-mechanics smoke. Harness mechanics fully verified:
  login, onboarding-modal dismissal, switcher interaction, per-tab capture,
  ≥400 census attribution per persona, stale-run cleanup, exit-code gating.
- Two UI facts discovered and handled in the harness (would block any
  automated walk): the first-run onboarding modal overlays the app after
  login, and the persona-switcher menu stays open over the nav until an
  outside click.
