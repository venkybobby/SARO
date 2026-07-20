# Demo Readiness Review — 2026-07-19

**Scope:** SARO demo surface (`/demo` flow) readiness per RB-005/RB-006, plus the
state of Playwright-based demo capture. Verified by a live local walk: backend on
SQLite (test-suite shims), `scripts/seed_demo.py` corpus, Vite frontend, and a
Playwright browser pass driven by `scripts/demo_capture_playwright.py` (added with
this review).

## What was verified green (local stand-in for RB-006 §A–§E, §H)

| RB-006 item | Result |
|---|---|
| §A `GET /api/v1/demo/token` | 200, `read_only: true`, `persona_role: compliance_lead` |
| §B all 10 DEMO_TABS census endpoints | all 200 with the demo token |
| §C seeded data present | 4 vertical audits (Finance/Healthcare/Gov/Tech), non-empty lists |
| §E write guard | `POST /api/v1/ingest` → 403, `PUT /api/v1/compliance/readiness/*` → 403 |
| §H browser pass (Playwright) | all 4 tabs render; zero API responses ≥ 400 during the walk |

STORY-412's endpoint census regression test and the frontend DEMO_TABS whitelist
load from the same `demoTabs.json`, so frontend/backed census drift is pinned in CI.

> RB-006 §A/§F/§G items that require reaching `saro-backend.fly.dev` or `fly ssh`
> could not be executed from this environment and still need a T-24h live run.

## Findings (ordered by demo impact)

### F1 — TRACE risk score renders as "1286/100" (double scaling) — BLOCKER
`ScanReport.overall_risk_score` is stored on the 0–100 scale
(`scripts/seed_demo.py:80` writes `bayesian.overall * 100`; `routers/trace_view.py:168,231,282`
returns it as `risk_score` unchanged). The frontend then multiplies by 100 again:
`frontend/src/pages/TraceView.jsx:115` (`Math.round(score * 100)`, comment claims the
API returns 0–1), `TraceView.jsx:327-328`, and `frontend/src/pages/ComplianceHub.jsx:206`.
Result observed in the browser pass: TRACE badge **"1286/100"**, Recent Traces chips
1286/1617/1915/1965, same values in Compliance Hub's Recent Audits column. This
contradicts positioning non-negotiable #2 (risk score is a 0–100 integer) on the most
demo-visible surface. `TraceView.test.jsx` fixtures use 0–1 values, so the unit suite
pins the wrong contract and stays green. Decide the canonical scale (backend is 0–100
today), fix the frontend (or backend) once, and update the fixtures.

> **Correction & resolution (FND-059).** The deeper root-cause pass flipped the
> attribution: every *production* writer (`routers/scan.py`, `routers/ingest.py`,
> `routers/output_audit.py`, `routers/hf_processor.py`,
> `services/audit_submission.py`) stores the engine's **0–1 probability**
> (`bayesian_scores.overall`, rounded to 4 dp in `engine.py`), and the frontend's
> single ×100 is the intended display scaling. `scripts/seed_demo.py` was the lone
> outlier pre-multiplying by 100 — so only seeded demo tenants showed "1286/100";
> data ingested through the production paths renders correctly. Fixed by storing
> the unscaled probability in `seed_demo.py`, pinned by
> `tests/regression/test_fnd_059_seed_demo_risk_score_scale.py`. The frontend and
> its fixtures were left unchanged (they already agree with the production
> contract). Demo tenants seeded with the buggy script need a reseed
> (`cli.py demo reset` + re-ingest) for stored scores to display correctly.

### F2 — Sidebar shows a red "API offline" badge in the deployed demo — HIGH
`frontend/src/components/Sidebar.jsx:96` polls `fetch("/health")`, but
`frontend/nginx.conf` proxies only `location /api/` to the backend. On
`sarofrontend.fly.dev`, `/health` falls through to the SPA and returns index.html;
`r.json()` throws and the badge permanently reads **"API offline"** with a red dot —
in front of every demo attendee. Fix: add a `/health` proxy location to nginx.conf
(or point the sidebar at an `/api/v1`-prefixed health route). The same artifact
appears in local dev because the Vite proxy also only maps `/api`.

> **Resolution (FND-060).** Fixed: `location = /health` proxy added to
> `frontend/nginx.conf` and a `/health` entry to the Vite dev proxy, pinned by
> `tests/regression/test_fnd_060_frontend_health_proxy.py`. Takes effect on the
> next `sarofrontend` deploy.

### F3 — CI "E2E Smoke Tests" job is vacuous — HIGH
`.github/workflows/ci.yml` installs Playwright + Chromium, but every
`@pytest.mark.e2e` test (13 of them, all in `tests/test_epic9_persona.py`) has a
`pass` placeholder body. The E2E gate is green by construction and RB-006 §H exists
only as a manual checklist. `scripts/demo_capture_playwright.py` (this review) is a
first automated stand-in: it walks `/demo`, screenshots every DEMO_TABS page, and
exits non-zero on any API response ≥ 400 or failed tab. Wiring it (or real
pytest-playwright tests) into the e2e job would make the gate real.

### F4 — Committed literal demo password evades RB-006 §G's grep — MEDIUM
`scripts/seed_demo.py:39` commits `_DEMO_PW_DEFAULT = "SaroDemo2026!"` as the
fallback when `DEMO_USER_PASSWORD` is unset. RB-006 §G's check
(`git grep -iE "password\s*=\s*..."`) misses it because the variable name says "PW",
not "password". Since `SEED_DEMO_DATA=true` runs this seeder on production startup
(`main.py` lifespan), a misconfigured deploy would create `demo@saro-demo.internal`
with a publicly-known password. Suggest: generate a random password when the env var
is absent (as `seed_demo_tenant.py` already does) and widen the §G grep to `pw|pass`.

### F5 — Hollow Compliance Hub under the `seed_demo.py` corpus — LOW (internal demos)
The local seed produces: Matrix coverage 0% (0 of 5 rules covered, "as of
2026-02-10"), all four EVF framework tiles at "INTERNAL ONLY" with 0.0%, readiness
checklist 0/6, dashboard Coverage 0%. Correct behavior (EVF status is genuinely
Internal Review Only per the claims matrix) but visually underwhelming; anyone
using `SEED_DEMO_DATA` for an internal walk-through gets empty-looking compliance
panels. The live demo tenant seeded via `seed_demo_tenant.py`/STORY-407 corpus is
richer — confirm on the T-24h run that coverage/readiness panels are populated there.

### F6 — Dashboard header vs. audit data consistency — LOW (verify on live)
With the local corpus the dashboard hero shows "RISK POSTURE LOW / RISK SCORE 0"
(`/api/v1/risk/summary` returns `overall_risk_score: 0.0`) while the same tenant's
audits carry overall risk scores 12.86–19.65 and ~70 open findings. If the live
tenant shows the same "0", the headline number will invite exactly the wrong
question mid-demo. Worth an eyeball on the live T-24h pass.

## Compliance-language spot-check (RB-005 §3)
The demo surfaces observed in the walk stay inside the approved-language matrix:
EVF tiles say "INTERNAL ONLY", TRACE view gates technical mode behind the ADR-004
"How SARO Reasons" document, and the Reports page footer carries the required
"audit evidence … not regulatory certification" disclaimer. No forbidden phrases
were observed on any captured screen.

## Verdict
**Not demo-ready until F1 and F2 are fixed** — both are immediately visible to an
attendee within the first minute (a nonsensical "1286/100" risk score and a red
"API offline" badge). F3 is the structural gap that let both ship: no real browser
test ever loads these pages. After F1/F2 land, re-run
`python scripts/demo_capture_playwright.py --base-url https://sarofrontend.fly.dev`
and the remaining RB-006 live items (§A, §D, §F, §G).
