# STORY-306 — Provenance completeness gate

**Epic:** GRC-2 — Evidence & Provenance Layer
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-305

## Context
Absence of evidence must never be read as conformance. An output lacking required provenance
resolves to `EVIDENCE_GAP` — never `PASS`. This is the structural guard against fabricated
compliance status.

## Framework mapping
- ISO/IEC 42001: accountability.
- NIST AI RMF: GOVERN.

## Scope (in)
- A check that validates an output's provenance record is complete before any audit disposition is allowed to be `PASS`.
- On incomplete provenance, the audit result for that output is `EVIDENCE_GAP`.

## Out of scope
- The contract-level PASS⇒evidence-LINKED rule (STORY-328) — this story is the service-side counterpart.

## Acceptance criteria (binary)
- [ ] An output with complete provenance is eligible for any disposition.
- [ ] An output missing any required provenance field returns `EVIDENCE_GAP`.
- [ ] It is impossible for the audit pipeline to emit `PASS` on an output with incomplete provenance.

## Technical notes
- Required-provenance field list should reuse the capture schema from STORY-305 (single source of truth).
- This is a hard precondition in the orchestrator (STORY-308), not an advisory warning.

## Test requirements
- [ ] Unit: complete → eligible; each missing field → `EVIDENCE_GAP`.
- [ ] Negative: attempt to force `PASS` on incomplete provenance is rejected.

## Definition of done
Incomplete-provenance outputs cannot pass; `EVIDENCE_GAP` returned; negative test green.
