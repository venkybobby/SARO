# STORY-BAA-01: Data-flow & residency diagram for Privacy Office sign-off

**Status:** in-progress (artifact done; **[HUMAN] Privacy Office approval OPEN**)
**Screen/Area:** Epic 15 — Trust & Compliance Enablement / BAA workstream
**Artifact:** `compliance/baa/STORY-BAA-01_data-flow-diagram.md`
**Depends on:** architecture-decision summary (`docs/ARCHITECTURE.md`)

## Goal
Give SummitCare's Privacy Office a diagram-as-code + narrative showing exactly where data goes, so
they can approve it before any PHI moves — the artifact that unblocks the BAA scope conversation.

## Acceptance Criteria
- **AC-1 [CC] ✅** Mermaid diagram: source systems → edge redaction → boundary (de-identified vs
  residual PHI) → SARO evaluation → audit events → client SIEM; PrivateLink/no-public-egress marked.
- **AC-2 [CC] ✅** Narrative labels each path de-identified (Safe Harbor) or residual PHI (BAA), and
  states where the boundary sits.
- **AC-3 [CC] ✅** Pilot (PrivateLink-hosted tenant) vs production (BYOC) drawn as two variants.
- **AC-4 [HUMAN] ⬜** Privacy Office reviews and approves. **Story stays OPEN until approval recorded.**

## Out of Scope
- The deployment build itself; the BAA signature (STORY-BAA-02); SummitCare DLP / Expert Determination.

## Non-Functional Requirements
- Anti-overclaim (ADR-004): rule-based redaction is not total de-identification — the residual-PHI
  path is real and measured, not claimed zero.

## Definition of Done
- [x] Diagram renders (Mermaid). [x] Every path labeled de-identified-or-BAA. [x] Two variants.
- [ ] Approval-status field present and **set by a human** (Privacy Office) — OPEN.

## Traceability
| AC | Evidence | Files |
|---|---|---|
| AC-1/2/3 | diagram + narrative + variants | `compliance/baa/STORY-BAA-01_data-flow-diagram.md` |
| AC-4 | approval field (human-set) | same, §5 |
