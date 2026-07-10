# STORY-412 — Demo surface trim: every visible tab must survive a click
Stage: standard

## Lifecycle
- [x] discover   (recon below — Sidebar/demo-token/AppShell/ComplianceHub/Reports/TraceView mapped)
- [x] shape      (AskUserQuestion → Decision Log)
- [x] preview    — skipped: no new visual design, reusing existing AppShell/Sidebar chrome verbatim; only a whitelist filter + wiring change, not a new surface
- [x] plan
- [x] build      (all ACs implemented; backend 1688 passed, frontend 180 passed, ruff/mypy clean)
- [x] verify     (change-debrief.html generated; independent security-auditor PASS — no
                   CRITICAL/HIGH/MEDIUM, 3 INFO — one actioned (added the readiness-toggle
                   403 regression case), two explicitly out-of-scope pre-existing items
                   flagged for a future finding, not this diff; independent reviewer
                   dispatched — will land as a follow-up commit if it surfaces anything)
- [ ] sell       — n/a unless requested

## Discover — recon findings (file:line cited)

- **`Sidebar.jsx`** (`frontend/src/components/Sidebar.jsx`): `PERSONA_TABS` (11-39) keyed by
  persona; `compliance_lead` = `["dashboard","compliance_hub","trace_view","trust_center","aims","onboarding","upload","evaluations","reports"]`.
  `persona = user?.persona_role || user?.role || "operator"` (134); `allowedTabIds =
  PERSONA_TABS[persona] || PERSONA_TABS.operator` (135). **No demo-mode branching exists
  today.** `canSwitch = ["admin","super_admin"].includes(user?.role)` (90) — already `false`
  for `role="demo_viewer"`, so AC-3 (switcher hidden) is already true by construction; needs
  only a pinning test, no code change.
- **`routers/demo.py:164-202`** (`GET /api/v1/demo/token`, public, no auth dependency):
  JWT payload = `{sub, tenant_id, role:"demo_viewer", read_only:true, exp, iat}` — **no
  `persona_role` claim today**, contradicting the story's context paragraph.
- **Critical gap vs. story's stated context:** `App.jsx:384` routes `/demo` to `DemoEntry`
  (`frontend/src/pages/DemoEntry.jsx`), which renders **bare `<Dashboard token tenantId
  isDemo />`** (line 52) — no `Sidebar`, no `AppShell`. `Dashboard`'s signature
  (`Dashboard.jsx:450`) doesn't destructure `isDemo` (no-op prop); `onNavigate` is
  `undefined` in this path, so every "quick action" button in Dashboard is a silent no-op.
  **The demo route has zero real navigation today** — resolved via AskUserQuestion: wire
  `DemoEntry` into the existing `AppShell` (below).
- **`ComplianceHub.jsx`** fires 5 GETs on load, all demo-safe already: `compliance-matrix/coverage`
  (`get_current_user` only), `evf/validation-status` (`get_current_user` only),
  `evf/qco/expiry-alerts` (`get_current_user` only), `audits?limit=10`
  (`_require_audits_list_read`, `scan.py:47-50`, explicitly includes `demo_viewer`),
  `compliance/readiness` (`require_role_or_persona`, `readiness.py`, explicitly includes
  `demo_viewer`). No panel degradation needed.
- **`Reports.jsx`** (the `reports` tab's actual component, `frontend/src/pages/Reports.jsx`)
  calls **only** `GET /api/v1/risks` (`routers/risks.py:95`, gate = `get_current_user` only —
  demo-safe). It does **not** call any `/api/v1/reports/*` endpoint — the story's technical
  note ("Reports uses `_require_reports_access`") describes a *different*, unused backend
  router (`routers/reports.py`) that the current frontend Reports page never calls. Verified,
  not assumed, per the story's own instruction.
- **`Dashboard.jsx`** on-load GETs: `/api/v1/risk/summary` (364), `/api/v1/risk/whats-changed`
  (384), `/api/v1/rules/drift-alerts` (203) — all gated `get_current_user` only
  (`routers/rule_packs.py:71-76` for drift-alerts). Plus STORY-413's two new tiles
  (`/api/v1/audits`, `/api/v1/compliance-matrix/coverage`) — both already demo-safe per above.
- **`TraceView.jsx`** on-mount GET: `/api/v1/audits?limit=10&sort=desc` (157) —
  demo-safe (`_require_audits_list_read`). Detail fetches (`/api/v1/audit/{id}/trace`,
  `/api/v1/audits/{id}`) only fire after a user selects a specific audit — out of the
  "on load" census per AC-1's own wording, but same gate family, already demo-safe by
  `_require_audits_list_read` pattern used across `scan.py`.
- **`routers/compliance_hub.py:138`** `persona_required(["compliance_lead","admin"])` —
  confirmed live bug (`"admin" in roles` checks the allow-list literal, not the caller's
  persona, in `services/persona_service.py:168-180`, so the gate is a no-op for every
  caller). Confirmed only, not touched — separate defect per the story's explicit
  out-of-scope note, and irrelevant here since `ComplianceHub.jsx` doesn't call this
  endpoint anyway (uses the compliance-matrix/evf/audits/readiness endpoints instead).
- **Test convention** (`tests/regression/test_fnd_028_trace_audit_read_access.py`):
  in-memory SQLite + `StaticPool`, seed at import time, `_user()` duck-type helper,
  `app.dependency_overrides[get_current_user] = lambda: user`. Existing
  `test_legacy_roles_and_demo_viewer_preserved` (159-167) is the direct precedent for
  demo-specific assertions. For STORY-412's AC-1 contract test I'm going one step further
  than that precedent: actually calling `GET /api/v1/demo/token` in-process (env var +
  seeded tenant, `get_db` override only — `get_current_user` NOT overridden) to mint a real
  JWT and exercise the full auth/JWT-decode path, then hitting each DEMO_TABS endpoint with
  `Authorization: Bearer <token>`, closer to the story's literal "mints a demo token (as
  `GET /api/v1/demo/token` does)" wording than a pure dependency-override shortcut.
- No `Sidebar.test.jsx` exists yet — new file.
- `tests/regression/manifest.yaml` is FND-finding-scoped (append-only ledger of bug →
  pinning test), not story-AC-scoped — STORY-412's new tests are ordinary component/
  integration tests, no manifest entry needed (confirmed by reading the file's own header
  comment and existing entries).

## Decision Log

Q1 (AskUserQuestion): DemoEntry.jsx bypasses Sidebar/AppShell entirely today — there is no
navigation to trim, RB-006's browser-pass (click every tab, open a TRACE detail) has nothing
to exercise. → **Wire demo into AppShell.** `DemoEntry.jsx` renders the existing `AppShell`
(reused verbatim — no forked chrome) instead of bare `Dashboard`, passing a synthetic `user`
object built from the decoded demo JWT payload. This is larger than the story's one-line
scope note ("introduce DEMO_TABS whitelist in Sidebar.jsx") but is the only way AC-1/AC-2
are meaningful, and matches the story's own technical note ("filter at render time in
Sidebar.jsx; do not fork PERSONA_TABS") — that note only makes sense if Sidebar is actually
rendered for demo sessions.

Q2 (AskUserQuestion): demo JWT has no `persona_role` claim; story context assumes
`persona_role="compliance_lead"`. → **Add `persona_role: "compliance_lead"` to the demo
JWT** in `routers/demo.py`. Not a `require_role()` widen (role-only checks are untouched);
uses the existing role-or-persona mechanism as designed. Turns out not strictly required for
AC-1 (every DEMO_TABS endpoint is already demo-safe by `role=demo_viewer` alone, including
Reports — see Discover), but still valuable: (a) matches the story's stated contract
verbatim, (b) `Sidebar.jsx:220` renders `ROLE_LABELS[persona] || persona` — without this
claim a demo session would display the literal string "demo_viewer" instead of "Compliance
Lead" in the user block, a cosmetic regression a prospect would see immediately, (c)
future-proofs any persona-gated panel not yet discovered. Zero downside, low-risk additive
claim.

Q3 (mine): shared fixture list for AC-1's "whitelist and test read from one shared list so
they cannot drift apart" — JS and Python can't share a `.jsx` module. → **`frontend/src/
config/demoTabs.json`** (`["dashboard","trace_view","compliance_hub","reports"]`), imported
by `Sidebar.jsx` (JSON import, Vite supports natively) and loaded by the new Python
integration test (`json.load`). The endpoint-per-tab census map lives only in the Python
test (test-only artifact, not a second source of truth for the *tab list* itself, which is
the thing AC-1 says must not drift).

Q4 (mine): `onSignOut`/`onUserUpdate` for the synthetic demo `AppShell` — no real account to
sign out of, switcher already hidden so `onUserUpdate` is normally unreachable. → `onSignOut`
does `window.location.reload()` (re-runs `DemoEntry`'s token fetch, i.e. "restart the
demo session" — the closest sane meaning of sign-out for a public read-only demo).
`onUserUpdate` merges into local synthetic-user state harmlessly (defensive; dead code path
since `canSwitch` is false, but keeps the prop contract intact rather than passing a
silently-swallowing no-op that would mask a future regression).

## Plan (ordered by tweak-likelihood)

1. **Shared fixture (tweak-likely):** `frontend/src/config/demoTabs.json` —
   `["dashboard","trace_view","compliance_hub","reports"]`.
2. **Backend claim (tweak-likely):** `routers/demo.py` — add `"persona_role":
   "compliance_lead"` to the JWT payload dict (164-202). Verify:
   `pytest tests/test_story407_demo_corpus_builder.py tests/regression/
   test_fnd_028_trace_audit_read_access.py -q` still green (neither depends on the token
   endpoint's exact payload shape, but confirms nothing decodes/asserts against it
   elsewhere).
3. **Sidebar demo override (tweak-likely, AC-2/AC-5):** `Sidebar.jsx` — import
   `DEMO_TABS` from the new JSON; `const isDemo = user?.role === "demo_viewer";`
   `const allowedTabIds = isDemo ? DEMO_TABS : (PERSONA_TABS[persona] || PERSONA_TABS.operator);`
   placed right before the existing `tabs = allowedTabIds.filter(...)` line — non-demo path
   byte-for-byte unchanged (AC-5).
4. **DemoEntry → AppShell wiring (tweak-likely, AC-1/AC-2 enabling change):**
   `DemoEntry.jsx` — decode the JWT payload already parsed locally (`parseJwtPayload`),
   build a synthetic user `{id: tenantId, tenant_id: tenantId, role: "demo_viewer",
   persona_role: payload.persona_role || "compliance_lead", read_only: true, email:
   "demo@saro.io"}`, import and render `AppShell` (import from `../App.jsx` — confirm
   `AppShell` is exported or lift it to its own module if `App.jsx` only has a default
   export; if not currently exported, export it as a named export — a mechanical,
   zero-behavior-change refactor) with `onSignOut={() => window.location.reload()}` and a
   harmless `onUserUpdate`. Needs a `toast` prop — reuse `useToast()` locally in
   `DemoEntry`.
5. **Backend contract test (AC-1):** new
   `tests/regression/test_story_412_demo_tab_endpoint_census.py` — seed a tenant, set
   `SARO_DEMO_TENANT_ID` via `monkeypatch.setenv`, override only `get_db`, call
   `GET /api/v1/demo/token` for a real JWT, load `frontend/src/config/demoTabs.json`,
   assert every mapped GET endpoint for `dashboard` / `trace_view` / `compliance_hub` /
   `reports` returns 200 with `Authorization: Bearer <token>`. Confirm the exact write
   endpoint RB-006 references (`/api/v1/ingest`) exists and is gated by
   `require_write_access` — verify, don't assume, during BUILD.
6. **Write-access regression (AC-4):** same test module (or a sibling) — POST to the
   confirmed write endpoint with the minted demo token, assert 403.
7. **Frontend component tests (AC-2/AC-3/AC-5):** new `frontend/src/components/
   Sidebar.test.jsx` — demo session renders exactly `DEMO_TABS` (AC-2), switcher absent for
   `role="demo_viewer"` (AC-3), non-demo persona tab sets unchanged for at least
   `compliance_lead`/`risk_officer`/`ai_auditor`/`operator`/`admin` (AC-5 regression
   snapshot).
8. **Full gate suite (close):** ruff/eslint, pytest (backend), vitest (frontend), quality
   ratchet — engineering-standards.md gates.

## Deviations

1. **New info during BUILD invalidates part of Q2's original rationale (not the
   decision):** `auth.py:175-189`'s `get_current_user` already synthesizes
   `persona_role="compliance_lead"` server-side for EVERY `role="demo_viewer"`
   JWT, unconditionally, regardless of what the token's own `persona_role`
   claim says. So `_require_reports_access`/role-or-persona gates never
   actually needed the JWT to carry the claim — they already worked. Kept the
   `routers/demo.py` change anyway (now for a narrower reason): it makes the
   JWT's explicit claims match what the server already grants, so a token
   inspection (or a future code path that reads the raw claim instead of
   going through `get_current_user`'s synthesis) doesn't disagree with actual
   behavior. Zero behavior change, pure consistency/observability improvement.
   Conservative option taken (kept the already-approved change) rather than
   reopening Q2.

2. **FND-051 (found during BUILD, fixed with regression test per "every bug
   fix ships a regression test"):** `test_demo_token_grants_200_on_every_tab_endpoint[compliance_hub]`
   failed red: `GET /api/v1/evf/qco/expiry-alerts` returned 422
   (`uuid_parsing` on `qco_id`). Root cause: `main.py` included
   `evf_sprint2_router` (generic `GET /qco/{qco_id}`) before
   `evf_sprint3_router` (static `GET /qco/expiry-alerts`) — both share the
   `/api/v1/evf` prefix, and FastAPI matches in registration order, so the
   generic route shadowed the static one for **every caller**, not just
   demo. Not a role-gate issue (out of this story's stated out-of-scope
   list) — a plain routing bug this story's build happened to surface.
   Fixed: swapped the two `include_router` calls in `main.py` (comment added
   explaining why order matters here). Pinned:
   `tests/regression/test_fnd_051_evf_qco_expiry_alerts_route_shadowed.py`
   (FND-051 in `tests/regression/manifest.yaml`) — asserts both the
   previously-shadowed route now resolves AND the generic `/qco/{qco_id}`
   route the swap could have shadowed in the other direction still resolves
   correctly (404 domain error, not a routing artifact).
