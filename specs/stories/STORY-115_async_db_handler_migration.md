# STORY-115: Async DB handlers for the risk-dashboard router (and the async-session decision)

**Status:** draft
**Screen/Area:** Backend / routers / database layer
**Tracks:** FND-024 (NEW-5 from the Dashboard screen review). Sibling to FND-017..023 (PR — board-dashboard review findings).

## Goal
SARO's API convention (`.claude/skills/api-conventions`) is **async-only route handlers**, but the
risk-dashboard routes (`routers/risk_dashboard.py`: `get_risk_summary`, `get_vendor_risk`,
`get_whats_changed`, `export_board_pdf`, `get_board_summary`, `export_board_summary_pdf`,
`get_vendor_risk_alias`) are synchronous `def` handlers running **blocking** SQLAlchemy queries.
Under load each blocking query occupies an event-loop worker thread; the convention exists to keep
the loop free. This story brings the router into convention **without regressing behavior**, and
makes the explicit decision on whether to adopt an async DB session (the only change that yields a
real, not cosmetic, benefit).

## Why this is not a trivial `def`→`async def` rename
1. **Internal sync callers.** `export_board_pdf` / `export_board_summary_pdf` call
   `get_board_summary(...)` and the aggregation helpers **directly and synchronously**;
   `get_vendor_risk_alias` calls `get_vendor_risk(...)`. Making the callees `async` forces every
   caller to `await`.
2. **Direct-call tests.** `tests/test_specs.py` invokes `get_board_summary(db=..., current_user=...)`
   directly (not via HTTP) and asserts on the returned dict. `async def` returns a coroutine and
   breaks those assertions.
3. **`async def` over blocking I/O is cosmetic.** Wrapping blocking `db.query(...).all()` in an
   `async def` still blocks the loop. A genuine fix needs an async session
   (`AsyncSession` + `async_sessionmaker`, `await db.execute(select(...))`), which is a
   `database.py`-wide change touching every router and the test `get_db` overrides — not local to
   this router.

## Decision required before this story is `ready`
Pick ONE and record it in the story before running `/story`:
- **Option A — Full async session migration (repo-wide).** Introduce an async engine/session,
  migrate all routers + the conftest `get_db` overrides. Real benefit, large blast radius, separate
  rollout. This story then becomes the *first slice* (risk-dashboard) of that program.
- **Option B — Offload blocking calls (`run_in_threadpool`).** Keep the sync session; make handlers
  `async def` and wrap DB work in `fastapi.concurrency.run_in_threadpool`. Satisfies the convention
  and frees the loop without an async-DB rewrite. Internal sync callers stay sync (call the helper,
  not the route). Lower risk; recommended interim.
- **Option C — Document an explicit exemption.** Record in `api-conventions` that read-only,
  low-traffic board endpoints are exempt. Cheapest; no convention drift only if written down.

## Acceptance Criteria (Given/When/Then — required before /story will run)
> Concrete ACs depend on the decision above. Drafted for **Option B** (recommended interim):
- AC-1: Given the risk-dashboard routes, When inspected, Then every `@router` handler in
  `routers/risk_dashboard.py` is declared `async def` (api-conventions compliant).
- AC-2: Given an async handler, When it performs DB access, Then the blocking query runs via
  `run_in_threadpool` (or an async session, per the chosen option) — not inline on the loop.
- AC-3: Given the existing endpoint tests (`test_p2_stories_009_010_014_016.py`,
  `test_specs.py`), When the suite runs, Then all pass unchanged in behavior (same status codes,
  same payload shape); direct-call tests are updated to the new call convention if needed.
- AC-4: Given `export_board_pdf` / `export_board_summary_pdf` / `get_vendor_risk_alias`, When they
  reuse aggregation logic, Then they call shared **non-route** helpers (not the async route fns), so
  there is no `await`-from-sync hazard.

## Edge Cases
- ReportLab-absent path (JSON fallback) must still work under the new handler form.
- The RBAC guard (`_require_board_access`) must still execute before any DB/threadpool work.
- `get_board_summary`'s "No data" early return must be preserved.

## Out of Scope
- Any behavior/response-shape change to the endpoints (this is a conformance refactor).
- Migrating routers other than `risk_dashboard.py` (unless Option A is chosen, which makes it a
  separate program-level epic).

## Non-Functional Requirements
- No regression in the full suite (backend 1204+ / frontend 102).
- No new external calls; SARO read-only, evidence-only posture unchanged.
- security-auditor + reviewer gates before merge (touches `routers/`).

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
