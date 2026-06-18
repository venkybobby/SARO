STORY-TRACE-003: Grant AI Auditor read access to traces, audit detail, and audit list
Status: ready    Screen/Area: TRACE View / Security
Epic: GRC-TRACE-View · Priority: P0 · Depends on: —
Overlap: superset of STORY-CHUB-002 (audits-list role gate). If CHUB-002 is done, the `/api/v1/audits` portion is already covered — this story extends the same fix to the trace + audit-detail endpoints.

Goal
The TRACE View is the AI Auditor's primary screen, yet every endpoint it needs is gated to roles the auditor doesn't have. `/api/v1/traces/{id}` (`routers/traces.py:43`) and `/api/v1/audits/{id}` (`routers/scan.py:367`) require `super_admin`/`operator`; `/api/v1/audits` (`scan.py:329`) requires `super_admin`/`operator`/`demo_viewer`. An `ai_auditor` (and `compliance_lead`) get 403, which the UI surfaces as "audit not found." Grant read access to the personas whose job is trace inspection, without weakening tenant isolation.

Framework mapping (per ADR-004 scope locks)
- NIST AI RMF: GOVERN (role-appropriate access to oversight artifacts), MEASURE.
- EU AI Act: Article 17 (the compliance/audit owner must be able to read the QMS evidence).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the gate on `/api/v1/audit/{id}/trace` (the timeline endpoint the UI uses post-TRACE-001), When evaluated, Then `ai_auditor` and `compliance_lead` are permitted (read-only).
AC-2: Given `/api/v1/audits/{id}` (rule-pack + provenance meta), When evaluated, Then `ai_auditor` and `compliance_lead` are permitted (read-only).
AC-3: Given `/api/v1/audits` (recent list), When evaluated, Then `ai_auditor` and `compliance_lead` are permitted, preserving existing `super_admin`/`operator`/`demo_viewer` access.
AC-4: Given any of these requests by a permitted persona, When served, Then results remain tenant-scoped to that user's tenant.
AC-5: Given a role not in the permitted set, When it requests any of these, Then it still receives 403.

Edge Cases
- Read-only enforcement: granting trace/audit read must NOT grant remediation or mutation routes (e.g. POST `/api/v1/traces/{id}/remediate`).
- `demo_viewer` behavior preserved exactly.

Out of Scope
- Tenant scoping of the timeline endpoint (STORY-TRACE-002).
- Frontend error-state differentiation (STORY-TRACE-010).

Non-Functional Requirements
- Security-auditor agent review mandatory (touches `routers/` + role gating).
- STORY-015 isolation suite stays green for every added role.

Test Requirements
- Integration (`tests/integration`): `ai_auditor` and `compliance_lead` → 200 on timeline, audit detail, audit list (own tenant only); unauthorized role → 403; remediation route still denied to read-only personas.
- Regression: `demo_viewer` and `operator` access unchanged.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
