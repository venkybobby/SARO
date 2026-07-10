# STORY-413 — Dashboard placeholder KPIs: real, hidden, or honestly impossible
Stage: standard

## Lifecycle
- [x] discover   (recon below)
- [x] shape      (Decision Log — no user interview needed; design follows directly from
                   the story's explicit ACs/out-of-scope, logged as "mine" decisions)
- [x] preview    — skipped: no new visual design, same KpiCard chrome, fewer/renamed tiles
- [x] plan
- [x] build      (all ACs implemented; backend 1693 passed, frontend 196 passed, ruff/eslint clean, CI guard verified locally)
- [x] verify     (change-debrief.html generated; independent reviewer dispatched — this
                   story touches no auth/routers/middleware/rule_packs, so security-auditor
                   isn't required per the CLAUDE.md trigger, only reviewer)
- [ ] sell       — n/a unless requested

## Discover — recon findings (file:line cited)

- **`PERSONA_KPIS`** (`frontend/src/pages/Dashboard.jsx:303-331`): 4 personas × 4 tiles.
  8 tile-instances carry `placeholder: true` (Controls Overdue ×2, Readiness %, Drift
  Alerts, Rule Pack Version, Coverage Gap %, Failed Scans, Queue Depth, Due This Week) —
  exactly the 8 named in the story. The other 6 (`EVF Frameworks`, `Scans This Week`,
  `Critical Risks`, `Remediation %`, `Scans Today` ×2, `Avg Score`) carry no
  `placeholder` flag.
- **`deriveKpis`** (394-409) already overwrites `Critical Risks`/`Remediation %`
  (risk_officer/admin/super_admin) and `Scans This Week`/`Scans Today`
  (compliance_lead / else-branch) with real values from `/api/v1/risk/summary` — these
  6 are genuinely real today, not placeholders needing this story's work.
- **`Avg Score`** (`operator`, index 3, line 326) has no `placeholder` flag but is
  **never** touched by `deriveKpis` (only index 0 is overwritten for the
  ai_auditor/operator branch) — a hardcoded `41` with no backing data and no flag,
  i.e. the exact failure mode this story targets, just missing its `placeholder: true`
  marker. **Not in the story's named list of 8 and not in its out-of-scope list either**
  — nobody flagged it before. Out of this story's explicit scope (which enumerates
  specific tiles to remove/keep) — logged as a new finding below rather than silently
  fixed or silently left broken.
- **Caption** `"sample — not yet wired to live data"` — one occurrence,
  `KpiCard` render loop, `sub={kpi.placeholder ? "..." : undefined}` (~line 557).
- **`GET /api/v1/audits`** (`routers/scan.py:380-419`) has only `limit`/`offset` query
  params — **no date-range filter**. `audit_count` from `/api/v1/risk/summary`
  (`services/risk_service.py:149`, `len(audit_records)`) is an **unwindowed total**, not
  a 7-day count — using it under an "(7d)" label would itself be an ADR-004 overclaim
  (labeling a total as a window). So "Audits (7d)" needs its own fetch to the
  `/api/v1/audits` list endpoint with a client-side 7-day filter, exactly as the story's
  technical note says — not a relabel of the existing (already-real) audit-count tiles.
- **`GET /api/v1/compliance-matrix/coverage`** (`routers/compliance_matrix.py:119-207`,
  `get_current_user` only) returns `overall_coverage_pct` — confirmed demo-safe by
  STORY-412's build. Not called anywhere in `Dashboard.jsx` today.
- **`KpiCard`** (95-157): `value` renders as-is (`value ?? "—"`), `loading` shows a
  `Skeleton`, `sub` is a secondary caption. No dedicated "unavailable" state exists —
  reusable directly by passing `value="Unavailable"` when a fetch errors.
- **`Dashboard.test.jsx`** conventions confirmed (source-inspection `readFileSync` +
  regex for "must not regress" pins, `vi.stubGlobal("fetch", ...)` router, minimal
  `user={{persona_role: ...}}` doubles) — matches STORY-412's Explore-agent findings from
  earlier in this session.
- **`quality-gates.yml`**'s `regression-and-ratchet` job (Python-only, no Node/npm setup)
  runs standalone `python scripts/check_*.py` steps (e.g. `check_citations.py`) — the
  AC-4 guard must be a pure-Python regex/text scan of `Dashboard.jsx`, matching that
  precedent exactly.

## Decision Log

Q1 (mine): the story says "wire the two tiles the demo script actually points at" but
doesn't say for which personas. → **Add `Audits (7d)` and `Coverage %` to every
persona's KPI row**, not just `compliance_lead`. AC-2 requires them for "both operator
and demo sessions" (a floor, not a ceiling); the Definition of Done says "every number
on the Dashboard" (not "every number on the demo persona's Dashboard"); and
`compliance-matrix/coverage` is tenant-wide, persona-agnostic data with no reason to
withhold it from any persona. Conservative in the sense that it can't make any persona's
Dashboard less honest.

Q2 (mine): "Avg Score" (operator) is a hardcoded fake with no `placeholder` flag —
found during Discover, not named in the story. → **Leave untouched, log as a new
finding** rather than silently fix (its correct semantics — average of what, over what
window — is a product question, not a mechanical one) or silently leave broken without a
paper trail. Filed as FND-052 (see Deviations). Matches this story's own explicit
Out-of-Scope discipline: only the 8 named tiles are this story's business.

Q3 (mine): AC-5 ("KPI row layout verified at 2, 3, and 4 visible tiles") — after removing
placeholders and adding 2 real tiles, real personas land at 3 (`ai_auditor`: 1 remaining
real tile + 2 new) or 4 (`compliance_lead`/`risk_officer`/`admin`/`super_admin`/
`operator`: 2 remaining + 2 new) tiles; no persona naturally produces exactly 2, and
failure/loading states change a tile's *content*, not the tile *count*. → **Extract the
KPI grid into a small `KpiRow` component** (mechanical, behavior-preserving) so AC-5 can
be pinned directly against synthetic 2/3/4-length arrays, rather than relying on
persona-count coincidence.

Q4 (mine): 7-day audit count needs a real endpoint call + client-side date filter, no
server-side date-range param exists. → `limit=200` (the endpoint's practical ceiling —
`Query(..., le=200)`, `scan.py:392`) client-side-filtered by `created_at >= now - 7d`.
Documented as a known cap in a code comment (a tenant with >200 audits in 7 days would
undercount) rather than silently assumed accurate — matches demo/pilot data volumes;
building a proper server-side windowed-count endpoint is out of scope per the story's own
"post-pilot backlog" framing for the other 6 tiles.

## Plan (ordered by tweak-likelihood)

1. **Data model (tweak-likely):** `PERSONA_KPIS` — strip all 8 `placeholder: true`
   entries from all 4 persona arrays. Remove the `sub={kpi.placeholder ? "sample...
   " : undefined}` caption branch entirely (AC-1).
2. **New tiles (tweak-likely):** two new hooks, `useAuditsLast7d(token)` (fetch
   `/api/v1/audits?limit=200`, client-side filter `created_at >= now-7d`, count) and
   `useCoveragePct(token)` (fetch `/api/v1/compliance-matrix/coverage`,
   `overall_coverage_pct`) — each returns `{ value, loading, error }`. Appended as two
   extra `KpiCard`s after the persona's own tiles, for every persona.
3. **`KpiRow` extraction (mechanical, enables AC-5):** pull the
   `<div style={grid}>{kpis.map(...)}</div>` block into `function KpiRow({ kpis,
   loading })`, behavior-identical, just testable in isolation.
4. **CI guard (AC-4):** `scripts/check_no_placeholder_kpi_tiles.py` — regex-scans
   `frontend/src/pages/Dashboard.jsx` for `placeholder:\s*true`, exits 1 if found (mirrors
   `scripts/check_citations.py`'s structure exactly). New step in
   `.github/workflows/quality-gates.yml`'s `regression-and-ratchet` job.
5. **Tests:** extend `Dashboard.test.jsx` (AC-1 source-inspection: no `placeholder: true`,
   no "sample —" string; AC-2 loading-then-live for the two new tiles; AC-3 error →
   "Unavailable"); new `KpiRow.test.jsx` (AC-5: 2/3/4-length arrays render correctly, no
   crash, no stray gap). CI-guard script gets its own tiny test (or a direct
   `subprocess`/exit-code check) mirroring `check_citations.py`'s own test coverage
   pattern if one exists — confirm during BUILD.
6. **FND-052 (mechanical logging, not a fix):** file `Avg Score`'s missing-flag fake
   number as a new finding in `quality/findings.md` / `tests/regression/manifest.yaml`
   with `status: open` (no pinning test — this story isn't fixing it, just recording it
   so it doesn't get lost, matching the manifest's own "open = no test yet" convention).

## Deviations
None yet.
