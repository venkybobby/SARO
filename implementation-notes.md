# audit-trail-ui — surface the self-audit trail (audit_events) in the frontend
Stage: standard

Goal (expert phrasing): `GET /api/v1/audit/events` (routers/self_audit.py,
STORY-META-001) exposes SARO's privileged-action hash-chain trail, but no
frontend page ever calls it — it was built and tested as a backend-only,
auditor-facing API. Root cause of "record visible in DB, invisible in UI" is
not a filter/tenant/RLS bug: there is no UI consumer at all. Add one.

## Lifecycle
- [x] discover   (done inline during root-cause investigation — see chat)
- [x] shape      (1a skipped — change is already specified; 1b: single
                   AskUserQuestion resolved placement to "new page under nav";
                   remaining decisions derived directly from existing backend
                   authz, logged below rather than re-asked)
- [ ] preview    (skipped — see Deviations: page reuses Reports.jsx's
                   established list/KPI/disclaimer pattern verbatim, not a
                   novel surface; verified live via browser preview instead
                   of a throwaway mock)
- [x] plan
- [x] build
- [x] verify     (live browser verification, see Deviations for how)
- [ ] sell — n/a (internal bug-fix/UI addition, not design-partner-facing)

## Premise check
| referenced artifact | verified? | file path |
|---|---|---|
| `GET /api/v1/audit/events` | yes | routers/self_audit.py:54 |
| `audit_events` table + hash chain (STORY-META-001) | yes | live Supabase `audit_events`, 17 rows, verified via MCP |
| `_require_auditor` gate (super_admin/operator role, ai_auditor persona) | yes | routers/self_audit.py:24, auth.py:351 `require_role_or_persona` |
| Sidebar persona/tab registry pattern | yes | frontend/src/components/Sidebar.jsx (PERSONA_TABS, TAB_REGISTRY) |
| AppShell page routing | yes | frontend/src/components/AppShell.jsx (PAGE_COMPONENTS) |
| Compliance disclaimer requirement for audit evidence pages | yes | docs/COMPLIANCE_CLAIMS_MATRIX.md "Required Disclaimer" |

## Decision Log
- Q: where should the trail be visible? → User: new standalone page under nav
  (not folded into TrustCenter/AdminSettings). Consequence: new page component
  + new Sidebar/AppShell registrations.
- Q (derived, not re-asked — backend already answers it): which personas see
  the nav tab? → Mirror `_require_auditor` exactly: `super_admin`, `operator`
  (role-based) and `ai_auditor` (persona-based) get the tab. `admin`/
  `compliance_lead`/`risk_officer` do not — showing it to them would 403 on
  load, which is worse than not showing it (matches how `evf_admin` is
  already scoped in Sidebar.jsx).
- Q (derived): who sees the tenant/system scope toggle? → Only `role in
  {super_admin, operator}` per `_resolve_tenant`'s privileged check
  (self_audit router raises 403 for `scope=system` otherwise); `ai_auditor`
  persona-only users get tenant scope with no toggle.
- Q (derived): does "Export" auto-fire? → No — `export=true` writes a new
  EXPORT audit event as a side effect (self-referential by design per the
  router docstring), so it must be an explicit button, never triggered by
  page load/refetch.

## Plan
1. `frontend/src/pages/AuditTrail.jsx` (new) — fetch `/api/v1/audit/events`
   (+ optional `scope=system` toggle, actor/action_class filters), render
   event table (created_at, action_class badge, actor, target, outcome,
   seq, event_hash truncated) + chain-verification status strip + Export
   button (separate confirm-and-fetch, not auto). Reuse PageHeader/Button/
   Badge/EmptyState/Skeleton from components/ui, and the compliance
   disclaimer footer (mirrors Reports.jsx).
2. `frontend/src/components/Sidebar.jsx` — register `audit_trail` in
   TAB_REGISTRY (icon: ClipboardList variant already imported elsewhere —
   use `ScrollText` or similar new lucide import) and add to PERSONA_TABS for
   `ai_auditor`, `super_admin`, `operator`.
3. `frontend/src/components/AppShell.jsx` — lazy-import AuditTrail, register
   `audit_trail: AuditTrail` in PAGE_COMPONENTS.
4. Verify live: preview_start the frontend dev server, log in, confirm the
   tab renders for a privileged persona and the demo tenant's `AUTH_EVENT`
   row (026de909-...) appears when scoped to that tenant.

## Deviations
- PREVIEW stage: skipped a throwaway HTML mock in favor of directly building
  the page (reuses Reports.jsx's established pattern 1:1: PageHeader/Button/
  Badge/EmptyState/Skeleton, same disclaimer footer) and verifying it live in
  the browser preview — equivalent "stop and look" checkpoint, less waste.
- Verification against production data was blocked: the sandbox's dev-server
  processes (Vite proxy, would-be local uvicorn) get `ECONNREFUSED` reaching
  any external host (Fly.io, Supabase) even though `curl` from the Bash tool
  and the MCP Supabase tools reach them fine — an outbound-network
  restriction scoped to `preview_start`-launched processes, not the sandbox
  as a whole. Conservative option taken: stood up a disposable local stack
  instead (Postgres in Docker on :5544 per `docs` local-run recipe, backend
  via `uvicorn --env-file .env` — added `--env-file .env` to
  `.claude/launch.json`'s backend config since pydantic-settings reads
  `os.environ` directly and won't pick up a `.env` file on its own). Verified
  the *mechanism* end-to-end there — a real login recorded a real AUTH_EVENT
  and rendered in the new page, chain verification showed "verified intact",
  Export correctly appended a new hash-chained EXPORT event and did NOT fire
  on page load — which is the same mechanism that produced record
  026de909-9ea8-4a67-b5a8-e344cd4010fc in production; did not re-fetch that
  specific historical row (would require live prod DB access from a
  sandboxed process, which is exactly what's blocked). `.env` /
  `frontend/.env.local` are both gitignored (`.env.*` pattern); the
  `--env-file .env` launch.json flag is harmless with no `.env` present
  (uvicorn no-ops).
