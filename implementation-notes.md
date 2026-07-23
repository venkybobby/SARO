# STORY-TAB-004 — Evaluations RBAC / nav visibility alignment

Stage: standard

## Lifecycle
- [x] discover   (skipped — gates + consumers audited this session; premise table in specs/stories/STORY-TAB-004.md)
- [x] shape      (interview skipped — autonomous session; decisions defaulted + logged below)
- [x] preview    (skipped — no visual change; a nav entry disappears for one persona, button visibility keyed to role)
- [x] plan
- [ ] build
- [ ] verify
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| List gate `require_role("super_admin","operator")` | yes | routers/evaluations.py:230-234 |
| Trigger gate `require_role("super_admin")` | yes | routers/evaluations.py:156-160 |
| `require_role` checks `current_user.role` (roles axis, not persona) | yes | auth.py:287-306 |
| Sidebar shows `evaluations` to compliance_lead + admin + super_admin personas | yes | frontend/src/components/Sidebar.jsx:12-38 |
| Trigger button keyed off persona (`ai_auditor`/`admin`/`super_admin`) | yes | frontend/src/pages/Evaluations.jsx:28-29 |
| HTTP role-matrix test pattern (dependency overrides, in-memory SQLite) | yes | tests/regression/test_fnd_028_trace_audit_read_access.py:74-92 |
| Trigger 422s on unknown dataset BEFORE creating a run/background task | yes | routers/evaluations.py:175-181 |

## Decision Log

(format: question → defaulted answer → architectural consequence)

| Question | Answer (defaulted) | Architectural consequence |
|---|---|---|
| Widen backend or narrow frontend? | Both, minimally (least privilege): backend list gate gains `admin` (read-only run metadata for the operations owner whose persona nav already surfaces the tab); trigger stays `super_admin`-only; `evaluations` removed from the `compliance_lead` persona list. | One-word authz change on a read endpoint; no new write capability. security-auditor review required (routers/ touched). |
| Frontend gating axis | `user.role`, never `persona_role` — a persona-switched super_admin keeps the backend-granted capability; an admin-persona viewer doesn't gain it. | Matches `require_role` semantics; pinned in vitest. |
| AC-5 regression guard without running a real eval in tests | super_admin POST /trigger with an unknown dataset → 422 proves the auth gate admits super_admin while the validation (which precedes run creation) stops any background work; admin POST → 403 proves the gate didn't widen. | No network/background side effects in the suite. |
| 403 UX on the list | Distinct message ("your role does not have access to evaluation runs") when the list GET 403s; generic banner otherwise. | No bare "⚠ 403". |

## Deviations
None yet.
