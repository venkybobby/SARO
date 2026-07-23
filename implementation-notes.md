# Demo live E2E flow (Playwright) — RB-006 automation for UC-1..UC-5 demo

Stage: standard

## Lifecycle
- [x] discover   (demo surface mapped: RB-006, demo_manifest.yaml UC-1..5, DemoEntry.jsx, STORY-412 census)
- [x] shape      (interview skipped — autonomous session; decisions defaulted + logged below)
- [x] preview    (skipped — test-only work, no user-facing surface changes)
- [x] plan
- [x] build      (tests/e2e/{conftest.py,test_demo_live_flow.py} implemented; RB-006 pointer added; ruff+mypy green; armed run executed twice: 18 passed / 5 failed, all 5 = empty demo tenant)
- [x] verify     (change-debrief.html)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| RB-006 demo verification script | yes | RB-006-live-demo-verification.md |
| UC-1..UC-5 demo use cases | yes | scripts/demo_manifest.yaml:68-105 |
| `GET /api/v1/demo/token` | yes | live probe 200; auth.py; frontend/src/pages/DemoEntry.jsx:18 |
| DEMO_TABS whitelist | yes | frontend/src/config/demoTabs.json |
| Census endpoint list (10 GETs) | yes | tests/regression/test_story_412_demo_tab_endpoint_census.py:70-91 |
| Trace detail route | yes | routers/trace_view.py:24,117 → `/api/v1/audit/{audit_id}/trace` |
| ENV-MODEL-ALLOWLIST-1 rule pack | yes | rule_packs/envelope/1.0.0/envelope_allowlist.yaml |
| Sidebar tab labels | yes | frontend/src/components/Sidebar.jsx:44-63 |
| "API offline" badge (FND-060 surface) | yes | frontend/src/components/Sidebar.jsx:284 |
| `/demo` route | yes | frontend/src/App.jsx:82; live probe 200 |
| e2e marker + CI job | yes | pytest.ini markers; .github/workflows/ci.yml e2e job |
| Live demo tenant seeded data | **verified ABSENT** | live probe: `/api/v1/audits?limit=50` → `[]`, risk summary all zeros — RB-006 §C/§D currently fail live |

## Decision Log

- Q: Python pytest-playwright or Node Playwright? → Python pytest-playwright — matches repo (pytest suite; CI e2e job already installs playwright+chromium; DEMO_READINESS_REVIEW F3 explicitly suggests "real pytest-playwright tests").
- Q: Where do tests live? → `tests/e2e/test_demo_live_flow.py` + conftest — picked up by `pytest tests/ -m e2e`.
- Q: Run against live in CI by default? → No; skip unless `SARO_LIVE_E2E=1` — CI e2e job stays hermetic/green; the live run is the explicit RB-006 T-24h/T-1h pre-demo gate, not a per-PR dependency on fly.dev availability.
- Q: Base URLs? → env-overridable (`SARO_E2E_BACKEND`/`SARO_E2E_FRONTEND`), defaulting to Fly.io prod — same suite points at local dev or staging.
- Q: /app or /demo as browser entry? → /demo — /app needs interactive login credentials; the planned demo runs on the public /demo flow per RB-006 §H.
- Q: Assert UC-3/UC-4 findings? → No — demo_manifest.yaml marks them `planted_pending_rule`; asserting them would assert unbuilt rules (FM-1 discipline).
- Q: (FND-070, discovered via stop hook) Fix time-bomb by regenerating report daily or deriving date from artifact? → Derive `Generated:` from the artifact's `generated_at` — STORY-379's own principle (everything in the report comes from the artifact); makes build_markdown deterministic.

## Review round (PR #125) — both agents APPROVE; applying advisory fixes
- reviewer: strict persona_role assert; census comment accuracy; try/finally in
  FND-071 test; _artifact_date fails loudly on missing generated_at; health-badge
  wait de-raced with expect(); /artifacts/ anchored; PDF churn reverted.
- security-auditor: sentinel string in the ingest 403 probe; localStorage AND
  sessionStorage VALUES scanned for eyJ prefix; drift-detection follow-up (its
  MEDIUM #1) logged as a spawned follow-up task, not scope-crept into this PR.

## Deviations
- Live demo tenant is EMPTY (audits [], risk score 0). §C/§D/§H-data tests will fail
  against prod until the tenant is reseeded (`cli.py demo reset` + re-ingest per
  RB-006 §C). Suite is built to report this precisely rather than papering over it.
- FND-070 (out-of-scope, surfaced by the stop hook's full-suite run): STORY-379's
  report equality test was a time-bomb — `generate_validation_report.py` stamped
  `datetime.now()` while the test pins byte-equality with the committed report, so
  the suite went red the day after the report was committed. Fixed conservatively
  (date now derives from the artifact's `generated_at`; report regenerated —
  byte-identical md), pinned by tests/regression/test_fnd_070_*.py, manifest
  updated. Also restored quality/validation/confusion-latest.json to HEAD (its only
  local change was a regenerated timestamp); trend.jsonl's appended history kept.
- FND-071 (the deeper root cause behind FND-070's recurrence, found when the stop
  hook re-failed): `confusion_matrix_harness.py main()` wrote the checked-in
  artifact + appended trend.jsonl even in --check mode, and a STORY-378 test calls
  main(["--check"]) — so EVERY full pytest run mutated quality/validation/ (that's
  where the pre-session dirty files and 7 duplicate trend lines came from) and
  re-broke STORY-379 equality mid-suite. Fixed: --check is now read-only (CI
  conformance.yml only consumes the exit code); pinned by
  tests/regression/test_fnd_071_check_mode_is_read_only.py; both validation
  artifacts restored to HEAD (appended trend lines were identical duplicates —
  test churn, not history). FND-070+071 both added to quality/findings.md ledger
  (STORY-103 consistency test enforces ledger⇔manifest).
