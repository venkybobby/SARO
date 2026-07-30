# SARO Roles & Permissions — Ground Truth

This document exists to answer one question precisely: **what do
"Implementation Lead", "AI Auditor", and "Risk Auditor ISO 42001" actually do
in SARO?** Every claim below is grounded in a file:line citation or a live
Supabase query. Where no code defines a behavior, that is stated explicitly —
nothing here is a guess at what a role "should" do.

## The short answer

| Role name (as you described it) | Exists in code? | What actually exists instead |
|---|---|---|
| **AI Auditor** | ✅ Yes — `ai_auditor` persona, fully enforced | Real, working persona (see below) |
| **Implementation Lead** | ❌ No — zero hits anywhere in the repo, in any casing/spacing | Nothing. No table row, no enum value, no enforcement, no frontend label. |
| **Risk Auditor ISO 42001** | ❌ No — zero hits as a role/persona | The closest real thing is the `risk_officer` persona (a test-file comment once glosses it as "risk auditor"). "ISO 42001" itself only ever appears as a *compliance framework name*, never as a role. |

If these three roles exist as literal string values somewhere in your live
Supabase `users` table (`role` or `persona_role` columns), they currently have
**zero enforcement** anywhere in the codebase: no endpoint checks for them, no
frontend tab or button maps to them, and the JWT/auth layer doesn't recognize
them as anything special. A user assigned one of these two nonexistent
personas would fall through to whatever default the frontend/backend apply
for an unrecognized value (see "What happens to an unknown persona" below).

---

## The two axes: `role` vs. `persona_role`

SARO has **two separate, independently-tracked identity fields** on `users`,
and conflating them is the most likely source of confusion:

### 1. `users.role` — coarse system tier, DB-enforced

```sql
CHECK (role IN ('super_admin', 'operator'))   -- migrations/044_users_role_check.sql
```

Only two legitimate values, enforced at the database level (added 2026-07-29,
the commit immediately preceding this audit — `FND-093`). A third value,
`"demo_viewer"`, exists only as a **synthetic, non-persisted** value minted
into demo JWTs (`auth.py:194-208`, `routers/demo.py:212`) — it never appears
as an actual row in the `users` table (confirmed: DB CHECK constraint would
reject it).

**Live data** (queried directly): all 3 real users in the production DB have
`role = 'super_admin'`.

### 2. `users.persona_role` — fine-grained UI/permission persona, NOT DB-enforced

```python
persona_role: Mapped[Optional[str]]  # "compliance_lead" | "risk_officer" | "ai_auditor" | "admin" | None
```
(`models.py:84-85`)

**Critical gap:** unlike `role`, this column has **no CheckConstraint**.
Nothing at the database layer stops an arbitrary string (e.g.
`"implementation_lead"`) from being written here. The only thing that
prevents garbage values is a single allowlist inside one API endpoint
(`_VALID_PERSONAS`, `routers/auth.py:333,370`) — and that allowlist only
applies if the persona is set *through that specific endpoint*
(`PATCH /api/v1/auth/users/{user_id}/persona`). A value written any other way
(direct SQL, a migration seed, an admin script) is never validated.

The four real personas, and what defines them, live in the `persona_permissions`
table (seeded from `services/persona_service.py`, migration `004_add_persona_permissions.sql`):

| `persona_role` | `allowed_tabs` | `allowed_actions` | `denied_actions` | `trace_mode` |
|---|---|---|---|---|
| `compliance_lead` | dashboard, compliance_hub, trace_view, evidence_export, claims_matrix, how_saro_reasons, dpa_governance, ir_plan, onboarding, upload | evidence_export, verify_chain, onboarding, trace_executive, claims_matrix, dpa | rule_pack_admin, gdpr_erasure, admin_settings, rule_packs, coverage_gap, remediation | executive |
| `risk_officer` | dashboard, risk_summary, vendor_risk, ir_plan, trace_view | risk_summary, vendor_risk, board_pdf_export, ir_plan, trace_executive | rule_pack_admin, gdpr_erasure, admin_settings, remediation, claims_matrix | executive |
| `ai_auditor` | dashboard, trace_view, evidence_export, rule_packs, coverage_gap, remediation, drift_alerts, upload | trace_technical, rule_packs, coverage_gap, remediation, drift_alerts, audit_crud | gdpr_erasure, risk_summary_board, claims_matrix, admin_settings | technical |
| `admin` | (all tabs) | `["*"]` (everything) | (none) | technical |

(Live data, queried directly from `persona_permissions`, 4 rows, matches the
`services/persona_service.py` seed exactly.)

**Live data on real users:** of the 3 users in production, one has
`persona_role='risk_officer'`, one has `persona_role='super_admin'` (**not a
valid persona** — no row for it in `persona_permissions`, meaning that user's
persona-based tab/action lookups will find nothing), and one has no persona
set at all.

---

## Where each persona is actually enforced (backend)

`auth.py` defines the mechanisms; `routers/*.py` uses them:

| Dependency | What it checks | Definition |
|---|---|---|
| `require_role(*roles)` | `.role` only | `auth.py:287-311` |
| `persona_required(*personas)` | `.persona_role` only | `auth.py:314-339` |
| `require_role_or_persona(roles, personas)` | either | `auth.py:351-383` |
| `require_write_persona` | allowlist: write-capable = `{compliance_lead, risk_officer, admin}` or system roles `{super_admin, operator}`; `ai_auditor` explicitly denied write | `auth.py:264-266,386-416` |

Across all 47 router files, every `require_role(...)` call uses only
`super_admin`/`operator`/`admin`/`demo_viewer` in various combinations — never
anything resembling "implementation_lead" or "risk_auditor". Every
persona-based check uses only `compliance_lead`/`risk_officer`/`ai_auditor`/`admin`.

### AI Auditor (`ai_auditor`) — the one real match

What an `ai_auditor` persona can actually do, per code:
- **Read** TRACE/audit evidence (`TRACE_READ_PERSONAS`, `auth.py:348`)
- **Read** rule packs, coverage gaps, drift alerts, and act on
  dispositions/remediation (`routers/dispositions.py:25`, `routers/rule_pack_versions.py:29`, etc.)
- **Cannot write** insights actions (`_READ_ONLY_PERSONAS = {"ai_auditor"}`,
  `auth.py:266`) — the AI Insights page disables Apply/Snooze/Dismiss buttons
  for this persona (`frontend/src/pages/AIInsights.jsx:217`)
- **Cannot** access the Compliance Hub, claims matrix, or admin settings
  (explicit denials in `persona_permissions.denied_actions`)

### risk_officer — closest real analog to "Risk Auditor"

Read access to risk summary, vendor risk, board PDF export, IR plan, and
executive-mode TRACE. Explicitly denied rule-pack admin, GDPR erasure, admin
settings, remediation, and claims matrix.

---

## A confirmed access-control bug: Compliance Hub denies everyone

`routers/compliance_hub.py:138`:
```python
dependencies=[Depends(persona_required(["compliance_lead", "admin"]))]
```

`persona_required` is defined as `def persona_required(*personas: str)`
(`auth.py:314`). Passing a single **list** here makes `personas` a 1-tuple
*containing that list* — not the two unpacked strings the author intended.
The check `if persona_role not in personas` (`auth.py:328`) then compares a
string against a tuple whose only element is a list, which is never true. The
practical effect: **`GET /api/v1/compliance/hub` currently rejects every
persona**, including `compliance_lead` and `admin`, the two it's supposed to
allow. This is a straightforward one-line fix (`persona_required("compliance_lead", "admin")`)
but is called out here because it's exactly the kind of "role doesn't work
right in the UI" symptom you described.

---

## Frontend: two competing role vocabularies

The real, backend-connected role system, surfaced correctly in
`frontend/src/components/Sidebar.jsx`:
- `ROLE_LABELS` (`Sidebar.jsx:73-80`): `compliance_lead`→"Compliance Lead",
  `risk_officer`→"Risk Officer", `ai_auditor`→"AI Auditor", `admin`→"Admin",
  `super_admin`→"Super Admin", `operator`→"Operator"
- `PERSONA_TABS` (`Sidebar.jsx:18-45`): which nav tabs each persona sees
- `AdminSettings.jsx:4-19` (`PERSONAS` dropdown + `PERMISSIONS_REF` table):
  descriptive reference of persona permissions shown to admins when assigning
  personas — this is UI copy, not enforcement, but it's at least wired to the
  real persona vocabulary.

**But `frontend/src/pages/Settings.jsx:17-35` defines an entirely separate,
hardcoded role vocabulary** — `Admin`, `Risk Manager`, `Viewer`, `Auditor` —
with its own `PERMISSIONS`/`ROLE_PERMS` mock tables. This file has **no fetch
or axios call anywhere in it** — it's disconnected from the backend entirely,
showing static mock data regardless of the logged-in user's actual role or
persona.

**This is almost certainly why the roles look "not defined properly in UI":**
depending on which settings page a user lands on, they'll see one of two
completely different, non-interoperable role systems. `Settings.jsx`'s
"Auditor" role is not the same thing as the backend's `ai_auditor` persona,
and neither "Risk Manager" nor "Viewer" exist anywhere in the backend at all.

---

## What happens to an unknown persona value

If a user's `persona_role` is set to something not in
`persona_permissions` (e.g. a hypothetical `"implementation_lead"`):
- `GET /api/v1/auth/me` (`routers/auth.py:255-271`) looks up
  `allowed_tabs`/`allowed_actions` by `persona_role` — an unmatched value
  yields no row, so those fields come back empty/absent.
- `Sidebar.jsx:144-145` falls back to `PERSONA_TABS.operator` when the
  persona key isn't found in `PERSONA_TABS`.
- No endpoint using `persona_required`/`require_write_persona` would ever
  admit the unknown value (fail-closed).

In other words: an undefined persona doesn't error loudly, it just silently
gets treated as having almost no permissions — which likely presents to the
user as "my role doesn't do anything," matching your original symptom.

---

## Recommendation (not implemented — docs only, per your request)

If "Implementation Lead" and "Risk Auditor ISO 42001" are roles you actually
want in the product, they need, at minimum:
1. A row in `persona_permissions` (or a decision that `role`, not
   `persona_role`, should carry them — but that column is DB-constrained to
   `super_admin`/`operator` only, so that would require a migration).
2. Additions to `_VALID_PERSONAS` in `routers/auth.py`.
3. Entries in `Sidebar.jsx`'s `ROLE_LABELS`/`PERSONA_TABS`.
4. A decision about `Settings.jsx` — its mock role vocabulary should probably
   be deleted or reconciled with the real one, since it currently misleads
   whoever views that page into thinking "Risk Manager"/"Viewer"/"Auditor"
   are real, distinct backend roles.

This is scoped intentionally as documentation only — no code changes were
made as part of this task, per your instruction to keep role work docs-only
for now.
