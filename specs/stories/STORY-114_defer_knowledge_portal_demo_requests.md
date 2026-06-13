# STORY-114: Defer the demo-request capability (Knowledge Portal / admin Demo Requests)

**Status:** ready (⚠ premise clarified — Knowledge Portal has no demo-request UI today)
**Screen/Area:** frontend/src KnowledgePortal.jsx, DemoRequests.jsx; routers/demo.py

## Goal
"Defer" the demo-request feature so it is not user-reachable in this release, without deleting the backend or losing data. Investigation found the Knowledge Portal currently has **no** demo-request UI; demo requests live in (a) a public signup endpoint `POST /api/v1/demo/signup`, (b) an admin "Demo Requests" management page, and (c) a public `/demo` read-only entry. This story disables/hides the demo-request surface behind a flag and presents a deferred ("coming soon") state where a CTA would appear.

## Decision Required (resolve at Definition-of-Ready)
Clarify scope of "defer". **Default interpretation:** hide the admin "Demo Requests" nav tab and gate the public `POST /api/v1/demo/signup` behind a feature flag (default OFF) so no new demo requests can be submitted, and if/where a "Request a Demo" CTA would surface in the Knowledge Portal, render a deferred placeholder instead of wiring it. Confirm whether the public `/demo` read-only entry should also be gated.

## Context (file:line)
- `KnowledgePortal.jsx` (route `knowledge_portal`, Sidebar.jsx:68; personas ai_auditor, admin, operator) — static articles only; no demo CTA today.
- `DemoRequests.jsx` (route `demo_requests`, Sidebar.jsx:63; admin) — manage inbound requests; APIs `/api/v1/demo/requests`, `/api/v1/demo/requests/{id}`.
- `routers/demo.py:28` `POST /api/v1/demo/signup` (public), `:84` GET requests (super_admin), `:110` PATCH (super_admin), `:142` GET `/api/v1/demo/token` (public, `/demo`).
- `DemoEntry.jsx` (route `/demo`, App.jsx:368) — public read-only demo session.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given a feature flag `DEMO_REQUESTS_ENABLED` (default OFF), When the app loads, Then the admin "Demo Requests" tab is hidden and any Knowledge Portal demo CTA renders a deferred/"coming soon" placeholder instead of an active form.
- **AC-2:** Given the flag OFF, When `POST /api/v1/demo/signup` is called, Then it returns a clear "demo requests are temporarily unavailable" response (e.g. 503/feature-disabled) rather than accepting/storing a request — no new `DemoRequest` rows created, no Slack notification fired.
- **AC-3:** Given the flag ON, When the app/endpoints are exercised, Then today's behavior is fully restored (admin tab visible, signup accepted) — defer is reversible by flag, not by code removal.
- **AC-4:** Given existing demo data and the management endpoints, When the feature is deferred, Then stored requests are preserved and the backend model/migrations are untouched (defer ≠ delete).

## Edge Cases
- The public `/demo` read-only entry (`/api/v1/demo/token`) — confirm whether it is in scope for deferral; default: leave it unless the user says otherwise.
- STORY-111 flags `demo_requests` as a possibly-orphaned nav entry — coordinate so the two stories agree on its disposition (hidden-by-flag here vs removed there).

## Out of Scope
- Deleting demo-request code, model, or migrations.
- Building a new Knowledge Portal demo CTA beyond the deferred placeholder.

## Non-Functional Requirements
- security-auditor review (touches a public router). The disabled signup must fail closed and not leak whether the feature exists. Follow `.claude/skills/api-conventions`.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_admin_demo_requests_nav_removed` (admin tab gone); KP had no demo CTA (premise) | components/Sidebar.jsx |
| AC-2 | `test_signup_fails_closed_when_disabled` (503, no DB write / no Slack) | routers/demo.py |
| AC-3 | `test_flag_enabled_values`; LIVE-006 tests re-enable the flag and pass | routers/demo.py |
| AC-4 | management endpoints + DemoRequest model untouched (security-auditor confirmed) | routers/demo.py |

**Status:** done. Premise corrected (Knowledge Portal had no demo CTA; the standalone DemoRequests page was already removed by STORY-016). Added `_demo_requests_enabled()` (env `DEMO_REQUESTS_ENABLED`, default OFF) gating the public `POST /api/v1/demo/signup` to fail closed (503, no DB write/Slack) — reversible by flag, data/model preserved. Removed the orphaned `demo_requests` admin nav entry (also fixed an FND-007 fall-through). Public `/demo` read-only entry left in scope-default (untouched). Independent `security-auditor`: APPROVE (fail-closed, no info leak, only signup gated). Branch `story/STORY-114_...` (stacked on 112).
