# FND — F1/F2 from docs/DEMO_READINESS_REVIEW_2026-07-19.md
Stage: standard

Two demo-blocker fixes from the merged readiness review (PR #123), requested by
the user ("please fix both"):

- **F1** — TRACE risk score renders "1286/100": frontend multiplies the already
  0–100 `overall_risk_score` by 100 (`TraceView.jsx`, `ComplianceHub.jsx`);
  `TraceView.test.jsx` fixtures pin the wrong 0–1 contract.
- **F2** — deployed sidebar permanently shows "API offline": `Sidebar.jsx`
  polls `/health` but `frontend/nginx.conf` proxies only `/api/`, so the SPA's
  index.html comes back and `r.json()` throws.

## Lifecycle
- [x] discover   (covered by the merged readiness review — file:line evidence for both bugs)
- [x] shape      (scope fixed by the review's F1/F2 recommendations; user approved "fix both")
- [ ] preview    (skipped — bug fixes restoring intended rendering, no new design)
- [x] plan       (below)
- [x] build      (seed_demo.py scale fix, nginx + vite /health proxy, main.py db_ok field; FND-059/FND-060 pinned red→green)
- [x] verify     (live local re-run: /health via proxy returns db_ok=true, reseeded scores 0.1286–0.1965, Playwright walk shows "13/100" TRACE badge and green "API online · DB ok" sidebar, zero red rows)
- [ ] sell       (n/a)

## Decision Log
- Q: Which layer owns the canonical risk-score scale? → A: **Backend, 0–100**
  (engine writes `bayesian.overall * 100` to `ScanReport.overall_risk_score`;
  API returns it unchanged; positioning non-negotiable #2 says 0–100 int).
  Consequence: frontend stops rescaling; test fixtures move to 0–100 values.
- Q: Fix F2 in the frontend (point Sidebar at an /api path) or at the proxy? →
  A: **Proxy** — add a `/health` location to nginx.conf (prod) and a `/health`
  entry to the Vite dev proxy, keeping `GET /health` as the single canonical
  health endpoint per docs/ARCHITECTURE.md. No backend route changes.

## Plan (tweak-likely first)
1. User-facing: `TraceView.jsx` (RiskChip + recent-chip scaling),
   `ComplianceHub.jsx` score scaling — remove the `* 100`.
2. Guard against regression: update `TraceView.test.jsx` fixtures to 0–100
   API values; add/adjust ComplianceHub test for the score chip.
3. Mechanical: `frontend/nginx.conf` `/health` proxy location;
   `frontend/vite.config.js` dev-proxy entry. Trusted config edit.

## Deviations
- **F1 fix direction flipped from the plan.** The plan (and the merged review
  doc) said to remove the frontend's ×100. Root-causing showed every production
  writer stores the engine's 0–1 probability and the frontend's single ×100 is
  the intended display scaling — `scripts/seed_demo.py` was the lone outlier
  pre-multiplying by 100. Conservative fix: align the seed script with the
  production writers; frontend and its fixtures untouched. Review doc corrected
  with an addendum. (Aggressive option — migrate storage to 0–100 API-wide per
  positioning non-negotiable #2 — is an API contract change touching 5+ writers
  and many consumers; left for a story if wanted.)
- **F2 needed a third leg.** Beyond the nginx and Vite proxies, /health's JSON
  never contained the `db_ok` boolean that Sidebar.jsx reads (and that
  CLAUDE.md/ARCHITECTURE.md document). Added `db_ok` to the payload additively
  (`database` string kept for existing consumers).
