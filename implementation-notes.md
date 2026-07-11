# FND-052 — remove operator's fake "Avg Score" KPI tile
Stage: standard

## Lifecycle
- [x] discover   — already done when FND-052 was filed during STORY-413's build (see
                   quality/findings.md); re-confirmed current Dashboard.jsx state below
- [x] shape      — user explicitly resolved the open product question ("don't want to
                   show fake scores in demo") — decision log below
- [x] preview    — skipped: removing a tile, not adding a new surface
- [x] plan       — see below
- [x] build      (tile removed; new regression test verified via fault injection —
                   re-added the tile, confirmed the test failed red, removed it again,
                   confirmed green; backend 1694 passed, frontend 202 passed, ruff clean)
- [x] verify     (findings ledger + manifest consistency tests green; FND-052 now
                   status: pinned in both files, cross-checked)
- [ ] sell       — n/a

## Discover — re-confirmed current state (file:line)

- `frontend/src/pages/Dashboard.jsx:348-351`: `PERSONA_KPIS.operator` = `[{label:"Scans
  Today", value:7,...}, {label:"Avg Score", value:41, severity:"low", icon:ShieldAlert}]`.
- `deriveKpis` (469-488): the `else` branch (ai_auditor/operator) only ever writes
  `base[0]` ("Scans Today") from `data.audit_count` — `base[1]` ("Avg Score") is never
  touched by live data. Confirmed unaffected by removing it (no index shift risk for
  this branch, since nothing downstream references `base[1]` for these two personas).
- `admin`/`super_admin` alias `risk_officer`'s array (354-355), not operator's — removal
  only affects the `operator` persona.
- The CI guard (`scripts/check_no_placeholder_kpi_tiles.py`) doesn't catch this tile
  today because it was never flagged `placeholder: true` — that's the original defect
  FND-052 documents. No guard change needed once the tile itself is gone (nothing left
  to catch).

## Decision Log

Q1 (user, resolving FND-052's open product question — "what does Avg Score mean, wire it
or remove it?"): "Don't want to show fake scores in demo." → **Remove the tile outright**,
same treatment as the 8 tiles STORY-413 already removed — no invented semantics (average
of what, over what window, was never specified and still isn't), no backend endpoint
exists to back it, so per STORY-413's own established rule ("if the data doesn't exist,
the tile doesn't exist") it comes out. `operator` ends up with 1 persona-specific tile
(Scans Today) + the 2 universal live tiles (Audits (7d), Coverage %) = 3 visible tiles,
same count `ai_auditor` already has — no new layout case, `KpiRow`'s existing 3-tile
coverage (`KpiRow.test.jsx`) already proves this renders correctly.

## Plan
1. `frontend/src/pages/Dashboard.jsx` — delete the "Avg Score" tile object from
   `PERSONA_KPIS.operator`.
2. `frontend/src/pages/Dashboard.test.jsx` — add a regression assertion: operator
   persona never renders "Avg Score" (mirrors STORY-413's AC-1 pattern for the other 8).
3. `quality/findings.md` + `tests/regression/manifest.yaml` — flip FND-052 from
   `open`/`verify-pinned` (no test) to `status: pinned`, pointing at the new test.
4. Full gate suite; independent reviewer dispatch (small diff, no auth/routers/rule_packs
   touched — security-auditor not required per CLAUDE.md's trigger).
5. New PR (prior branch was merged; per CLAUDE.md, follow-up work restarts the branch
   from latest main and gets its own PR).

## Deviations
None yet.
