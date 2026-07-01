# STORY-SOC-01: SOC 2 Type II scope definition + observation-window kickoff

**Status:** in-progress (artifact done; **[HUMAN] clock-start OPEN**)
**Screen/Area:** Epic 15 — Trust & Compliance Enablement / SOC 2 Type II workstream
**Artifact:** `compliance/soc2/STORY-SOC-01_scope-and-kickoff.md`
**Depends on:** none — start immediately (observation clock is the long pole)

## Goal
Define scope/boundary/TSC and the auditor-engagement checklist so the observation clock can start.

## Acceptance Criteria
- **AC-1 [CC] ✅** TSC selection with rationale — Security baseline; recommend Confidentiality +
  Availability in scope, defer Processing Integrity + Privacy, with the tradeoff for each.
- **AC-2 [CC] ✅** System description / boundary: in-scope (runtime, audit pipeline, tenant isolation,
  access model, CI gates) vs explicitly out (customer systems, audited vendors, SIEM, superseded infra).
- **AC-3 [CC] ✅** Auditor-engagement checklist: readiness vs Type II, 3/6/12-month window tradeoffs,
  evidence expectations.
- **AC-4 [HUMAN] ⬜** Select/engage the audit firm; set the observation-window start date. **Clock start.**

## Out of Scope
- Performing the audit; firm procurement; building controls (SOC-02 discovers, gaps are follow-ons).

## Non-Functional Requirements
- Posture: SARO holds no SOC 2 report — readiness only. Uses PT-012 Fly.io + Supabase stack (roadmap
  doc is partly stale on Railway).

## Definition of Done
- [x] TSC set with rationale. [x] Boundary documented.
- [ ] Observation-start date field present and **set by a human** — OPEN.

## Traceability
| AC | Evidence | Files |
|---|---|---|
| AC-1/2/3 | TSC + boundary + engagement checklist | `compliance/soc2/STORY-SOC-01_scope-and-kickoff.md` |
| AC-4 | clock-start block (human-set) | same, §5 |
