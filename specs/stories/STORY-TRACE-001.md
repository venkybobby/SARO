STORY-TRACE-001: Repoint TRACE View to the timeline endpoint and render truthful per-step status
Status: ready    Screen/Area: TRACE View
Epic: GRC-TRACE-View · Priority: P0 · Depends on: STORY-TRACE-002

Goal
`frontend/src/pages/TraceView.jsx` fetches `/api/v1/traces/{id}`, which returns `list[AuditTraceOut]` (an array of per-gate rows — `routers/traces.py:40`), then renders it as a single object reading `trace.status`, `trace.risk_score`, `trace.steps[key]`, `trace.steps_completed`, `trace.hash_chain_valid`. All of those are `undefined` on an array, so: the status badge is always PENDING, the risk chip never renders, the six-step strip shows all-green ("done") via the `steps_completed || 6` fallback even for a failing audit, and no detail panels render. Repoint the screen to the correct timeline endpoint `GET /api/v1/audit/{id}/trace` (`routers/trace_view.py:48`, returns `build_trace_timeline` output) and normalize its shape to the render contract so steps, statuses, and panels reflect reality.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 13 (transparency — the pipeline outcome shown must be the true outcome).
- NIST AI RMF: MEASURE (per-gate results surfaced accurately).
- ISO/IEC 42001: document-lifecycle linking (trace tied to its audit).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given `TraceView.jsx`, When a trace loads, Then it calls `GET /api/v1/audit/{id}/trace` (not `/api/v1/traces/{id}`) and binds against `build_trace_timeline`'s shape.
AC-2: Given the timeline returns `steps` as an array of `{key, status, detail, rules_fired}` (`services/trace_service.py:110`), When the strip and panels render, Then each UI step resolves its data via `steps.find(s => s.key === stepKey)` (not object indexing).
AC-3: Given a step has no data or status "pending", When the strip renders, Then it shows "pending" — the `steps_completed || 6` all-green fallback is removed and no step is shown as "done" without a real pass/warn/fail.
AC-4: Given a step's status is fail or warn, When the strip renders, Then that step shows the fail/warn style (a failing audit must never display as fully passed).
AC-5: Given the timeline includes `audit_status` and the risk score is sourced (from the timeline or the audit report), When the header renders, Then the status badge and risk chip show real values, not PENDING/blank.
AC-6: Given summary vs technical mode, When toggled, Then summary uses each step's `detail`/`summary` and technical shows the step object (including `rules_fired`).

Edge Cases
- Audit with zero trace rows → strip renders all-pending with an explicit "no trace records" note, not all-green.
- A gate that maps to multiple UI steps (per `_INT_GATE_TO_STEP`) must not double-count or drop steps.
- `executive_mode` strips `rules_fired`/`detail`; technical mode must still function when those are absent.

Out of Scope
- Tenant scoping of the endpoint (STORY-TRACE-002 — hard dependency, do first).
- Role/access changes (STORY-TRACE-003).
- Integrity banner correctness (STORY-TRACE-004).

Non-Functional Requirements
- No code path renders a step as "done"/passed without a backing real status.
- Single normalization helper converts the timeline response → render model, unit-tested in isolation.

Test Requirements
- Frontend unit (`frontend/src/pages/TraceView.test.jsx`): array `steps` → correct per-step binding; pending step → pending (not done); fail step → fail style; empty steps → all-pending + note; header binds `audit_status`/risk.
- Contract test: a fixture of `build_trace_timeline` output renders without `undefined` reads.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
AC-6	—	—
