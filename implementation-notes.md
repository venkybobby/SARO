# FND-078 / FND-079 / FND-063 / FND-067 — security-hardening findings batch

Stage: standard

## Lifecycle
- [x] discover   (skipped — all four findings carry root-cause rows in quality/findings.md from their originating audits)
- [x] shape      (owner instruction "Fix them all"; decisions defaulted + logged below)
- [x] preview    (skipped — no user-facing design change; one UI copy generalization)
- [x] plan       (per-finding task list; red-first pin per finding)
- [x] build      (four fixes red-first; gates green — regression 215, integration 370, unit 834, vitest 276, full mypy clean, ratchet holds)
- [x] verify     (reviewer APPROVE x4 + security-auditor PASS; review round applied — previous-value forensics on the contact audit event, overlong-email boundary pin. CI verification pending the GitHub Actions billing restore — merge held.)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| EvaluationRunOut carries api_url + error_message; Detail extends it | yes | routers/evaluations.py:54-77 |
| require_role 403 echoes role tuple; or_persona variant is generic | yes | auth.py:303-304 vs auth.py:377 |
| /remediation/oauth/jira/start gated by bare get_current_user | yes | routers/remediation.py:408-412 |
| No security-contact field exists; docs/ops has no breach template | yes | grep models.py/clients.py; ls docs/ops |
| Next migration slot | yes | migrations/041_pilot_feedback.sql → 042 |
| No test pins the "Required:" wording | yes | grep tests/ |
| CI billing outage (jobs die at 0 steps) — merge must wait | yes | gh api runs/jobs; memory project_github_actions_billing_block |

## Decision Log

(format: question → defaulted answer → architectural consequence)

| Question | Answer | Architectural consequence |
|---|---|---|
| FND-078: drop or sanitize? | Drop `api_url` + `error_message` from EvaluationRunOut (list + trigger responses); keep on EvaluationRunDetailOut (super_admin/operator only). ORM columns unchanged. | List consumers (incl. the AdminSettings embed + TrustCenter card) see no internal infra detail; failure text remains reachable via the gated detail route. |
| FND-079 wording | Generic "Not authorised for this action." — mirrors require_role_or_persona; `_log_authz_denial` keeps the full role detail server-side. Evaluations.jsx 403 copy loses the role enumeration (pinned phrase kept). | Uniform disclosure posture across both authz helpers. |
| FND-063 scope | Role-gate /start: require_role("admin","super_admin") + require_write_access. Single-slot pending nonce kept (documented residual — concurrent admin flows clobber; low risk, admin-only now). | Rebinding the tenant Jira connection becomes an admin capability; demo/read-only tokens blocked outright. |
| FND-067 scope | docs/ops/breach-notification-template.md (initial/update/closure sections, [HUMAN — COUNSEL REVIEW] markers per FND-064 precedent) + nullable `tenants.security_contact_email` (migration 042) surfaced read/write on the client profile endpoints. | 72h-clock artifacts exist before an incident; contact captured at onboarding; counsel sign-off explicitly flagged, not implied. |
| Landing | One branch/PR (findings batch, not stories); merge HELD until GitHub Actions billing is restored (jobs currently die at startup — merging unverified would break the no-red-merge rule). | PR opens now; owner unblocks billing; then merge. |

## Deviations
- Reviewer/security round applied in-PR: audit event records {previous, new}
  (forensic redirect question); >320-char email boundary pin added; FND-061
  fixture re-roled to the FND-063-admitted role (assertions unchanged).
- Merge deliberately HELD: GitHub Actions billing outage means CI cannot run;
  merging unverified-by-CI would break the no-red-merge rule.
