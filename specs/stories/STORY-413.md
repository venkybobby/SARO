# STORY-413: Dashboard placeholder KPIs — real, hidden, or honestly impossible

**Status:** ready
**Screen/Area:** Dashboard.jsx — opening frame of the demo and the operator app
**Epic:** GRC-10 — Demo Readiness
**Priority:** P0 · **Depends on:** none · **Pairs with:** STORY-412

## Context
`Dashboard.jsx` ships hardcoded KPI tiles (`Controls Overdue: 5`, `Readiness: 68%`,
`Drift Alerts: 2`, `Rule Pack Version: v3.1`, `Coverage Gap: 18%`, `Failed Scans: 1`,
`Queue Depth: 3`, `Due This Week: 8`) marked `placeholder: true`, captioned
"sample — not yet wired to live data." The Dashboard is the demo's opening frame and the AI
Auditor is the deal-killer persona: fabricated compliance numbers with a fine-print
disclaimer is the exact failure mode ADR-004 exists to prevent. The Marcus Hale pressure
test already returned an AI Auditor REJECT on weaker overclaiming than this.

## Framework mapping
- ADR-004: anti-overclaiming on finding/metric language.
- NIST AI RMF MEASURE: metrics presented as measurements must be measurements.

## Goal
Every number on the Dashboard is a measurement or an honest absence. An AI Auditor
screenshotting the opening frame finds nothing to reject.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given any session (demo or operator), when the Dashboard renders, then no tile with
  `placeholder: true` renders in any mode, and the "sample — not yet wired to live data"
  caption string no longer exists in the codebase.
- AC-2: Given the Audits and Coverage endpoints, when the Dashboard loads for either operator
  or demo sessions, then those two tiles render live values from their endpoints, showing a
  loading skeleton (not a fabricated number) before data arrives.
- AC-3: Given an endpoint failure, when the Dashboard renders that tile, then it shows an
  explicit "unavailable" state — never a stale or default number.
- AC-4: Given a future PR adds a new hardcoded `placeholder: true` tile, when CI runs, then a
  grep-style CI check (or test) fails — the pattern is fenced, not just cleaned once.
- AC-5: Given 2, 3, or 4 visible tiles, when the KPI row renders, then layout is verified at
  each count with no orphan gaps.

## Scope (in)
1. **Demo + production behavior:** tiles with `placeholder: true` are not rendered unless
   live data arrives and flips the flag (existing flip logic at `Dashboard.jsx:402-407`
   stays). No placeholder tile is ever visible to any user — the "sample" caption path is
   deleted, not restyled.
2. **Wire the two tiles the demo script points at**, sourced from endpoints that already
   exist and admit the demo principal:
   - **Audits (7d)** — from `GET /api/v1/audits` count (already flips today; verify).
   - **Coverage %** — from `GET /api/v1/compliance-matrix/coverage` (real INV-2 envelope
     coverage; the number the SummitCare story hinges on).
3. **Layout resilience:** the KPI row renders correctly with 2–4 tiles (no orphan gaps when
   placeholders are suppressed).

## Out of Scope
- Building backend endpoints for Controls Overdue, Drift Alerts, Queue Depth, Readiness %,
  Failed Scans, Due This Week. If the data does not exist, the tile does not exist. Wiring
  these is a post-pilot backlog item, not a demo item.
- Any change to non-KPI Dashboard panels (LiveFeed, EngineScores, RegCoverage untouched
  unless they contain the same pattern — audit them in AC-4 but fix in a follow-up if found).

## Edge Cases
- Endpoint failure must render "unavailable," not a stale/default number (AC-3).
- KPI row must not show orphan gaps at 2, 3, or 4 visible tiles (AC-5).

## Non-Functional Requirements
- The flip mechanism already exists; the change is inverting the default from "show fake
  until real" to "show nothing until real." Small diff, high trust payoff.
- AC-4 keeps the failure mode from regenerating — this exact pattern was flagged in the June
  screen reviews and returned.

## Test Requirements
- Component tests: placeholder suppression (AC-1), live-flip render (AC-2), failure state
  (AC-3), extend `Dashboard.test.jsx`.
- CI guard for AC-4 alongside existing lint steps in `quality-gates.yml`.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
