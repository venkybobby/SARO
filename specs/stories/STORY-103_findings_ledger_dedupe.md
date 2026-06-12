# STORY-103: Deduplicate and Reconcile Findings Ledger Entries FND-009/010/011 (G-3)
Status: ready
Screen/Area: Quality Infrastructure / `quality/findings.md`

## Goal
FND-009, FND-010, FND-011 each appear twice — once "pinned," once "open" — with different root-cause text. The artifact whose purpose is proving document discipline is internally inconsistent and would be flagged in minutes during an FR-EVF-17 retrospective. Each finding ID must be unique with one canonical status and one root cause, enforced by CI.

GRC mapping: ISO/IEC 42001 Clause 10 (improvement, nonconformity records); NIST AI RMF GOVERN 1.5 (documented processes); evidentiary integrity for EVF.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given `quality/findings.md`, When parsed, Then every FND-XXX identifier appears exactly once.
- AC-2: Given the formerly duplicated FND-009/010/011, When each surviving row is read, Then it carries a single reconciled root cause, a single status, and a reconciliation note referencing this story (audit trail of the merge, not silent deletion).
- AC-3: Given CI runs, When a PR introduces a duplicate finding ID or an ID with conflicting statuses, Then the quality gate fails with the offending IDs named.
- AC-4: Given the `/finding` slash command, When it appends a new finding, Then it validates ID uniqueness before writing.

## Edge Cases
- The two versions of a finding describe genuinely different defects → split into the lower-numbered original plus a new FND-XXX, cross-referenced.
- Historical git references to the deleted duplicate rows → reconciliation note preserves both prior texts in a collapsed appendix for evidentiary continuity.

## Out of Scope
- Re-litigating closed findings' technical content.
- Ledger schema redesign.

## Non-Functional Requirements
- Validator must run in <2s in CI; standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
