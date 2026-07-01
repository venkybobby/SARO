# STORY-BAA-02: BAA execution package & tracking

**Status:** in-progress (artifact done; **[HUMAN] BAA execution HARD GATE OPEN**)
**Screen/Area:** Epic 15 — Trust & Compliance Enablement / BAA workstream
**Artifact:** `compliance/baa/STORY-BAA-02_execution-package.md`
**Depends on:** STORY-BAA-01 (approved diagram informs scope)

## Goal
Package what's needed to get the BAA signed with the right AI-processing exhibits, and track it to
signature — as items for counsel to confirm, never as binding language.

## Acceptance Criteria
- **AC-1 [CC] ✅** Checklist of AI-processing BAA components (sub-processors, breach notice, permitted
  uses, de-identification, return/destruction, audit rights), framed as items for counsel.
- **AC-2 [CC] ✅** Note where narrowed scope is possible if edge redaction is proven.
- **AC-3 [CC] ✅** Status tracker: component → owner → status → blocking-yes/no.
- **AC-4 [HUMAN] ⬜** SummitCare counsel + SARO execute the BAA. **HARD GATE: no PHI flows until signed.**

## Out of Scope
- Drafting binding legal language (counsel owns it); the signature itself.

## Non-Functional Requirements
- Narrowing to "mostly de-identified" is a negotiation, not a fact (residual path non-zero).
- `docs/sub-processors.md` is stale (Railway/Streamlit) — flagged for reconciliation before it
  becomes a BAA exhibit.

## Definition of Done
- [x] Checklist complete. [x] Tracker shows every item's owner/status.
- [ ] Execution AC gated and visibly incomplete until signed — **HARD GATE OPEN**.

## Traceability
| AC | Evidence | Files |
|---|---|---|
| AC-1/2/3 | checklist + narrowed-scope note + tracker | `compliance/baa/STORY-BAA-02_execution-package.md` |
| AC-4 | execution block (human-set) | same, §5 |
