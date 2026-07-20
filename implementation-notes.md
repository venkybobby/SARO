# TASK — Demo readiness review + Playwright demo capture verification
Stage: trivial

Read-mostly verification task: audit RB-005/RB-006 demo runbooks and the demo
surface (demo token, DEMO_TABS census, seeds), assess the state of Playwright
E2E coverage, and perform a live local demo capture (backend on SQLite +
Vite frontend + Playwright screenshots). No product source changes intended;
all scripts live in the session scratchpad. Gates stand down per the trivial
classification (no interface/data-model change, no user-facing change).

## Lifecycle
- [x] discover   (repo demo surface mapped: routers/demo.py, DemoEntry.jsx, demoTabs.json, RB-005/RB-006, STORY-412 census)
- [ ] shape      (skipped — verification task, no design decisions)
- [ ] preview    (skipped — no UI change)
- [ ] plan       (skipped — trivial)
- [x] build      (local stack booted on SQLite; Playwright walk captured all DEMO_TABS + TRACE detail; capture script added at scripts/demo_capture_playwright.py)
- [x] verify     (findings written to docs/DEMO_READINESS_REVIEW_2026-07-19.md — F1 double-scaled risk score, F2 nginx /health gap, F3 vacuous e2e gate, F4 committed fallback password, F5/F6 seed-data gaps)
- [ ] sell       (n/a)

## Decision Log
- Q: Where to run the demo capture? → A: Locally (SQLite + shims mirroring
  tests/conftest.py, seed via scripts/seed_demo.py) — RB-006's live checks
  require fly ssh access this session does not have.
- Q: Modify product source? → A: No. Capture scripts stay in scratchpad;
  findings are reported, not auto-fixed.

## Deviations
None yet.
