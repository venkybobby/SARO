# STORY-326 — Lifecycle gate engine

**Epic:** GRC-6 — Lifecycle Gates, Sign-off & Output Contract
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-310, STORY-328, STORY-302 (STORY-304 relaxed for MVP)
**Encodes decision:** OPEN-DEC-1 → 1 High FAIL → GO_WITH_CONDITIONS; ≥2 High FAILs → NO_GO

## Context
Nothing reaches production without passing the right gate. The gate aggregates findings into a
single recommendation and enforces the non-negotiable blocking rules.

## Framework mapping
- ISO/IEC 42001: AI system lifecycle / operation.
- NIST AI RMF: GOVERN.

## Scope (in)
- Aggregate a system's findings into `gate_recommendation` ∈ {GO, GO_WITH_CONDITIONS, NO_GO}.
- Blocking rules:
  - Any **Critical FAIL** → `NO_GO` (also enforced by contract STORY-328).
  - **≥2 High FAILs** → `NO_GO`; exactly **1 High FAIL** → `GO_WITH_CONDITIONS`.
  - Any **open governance gap** (STORY-302) → cannot be `GO`.

## Out of scope
- Sign-off capture (STORY-327). Tier-scaled stringency beyond the raw tier (STORY-304, Phase 2).

## Dependency relaxation (MVP)
Use the raw `internal_tier` from STORY-303 directly. The full tier-routing layer (STORY-304) is
Phase 2 and does not block this story.

## Acceptance criteria (binary)
- [ ] A single Critical FAIL yields `NO_GO` regardless of other PASSes.
- [ ] Two High FAILs yield `NO_GO`; one High FAIL yields `GO_WITH_CONDITIONS`.
- [ ] A system with an open governance gap cannot be `GO`.
- [ ] The High-FAIL threshold (N=2) is read from config (STORY-331), not hard-coded.

## Technical notes
- The result must agree with the contract's Critical-FAIL⇒NO_GO rule; if they disagree, treat it as a defect (single source of truth = contract).

## Test requirements
- [ ] Unit: Critical-FAIL, 1-High, 2-High, open-gap scenarios → expected recommendation.

## Definition of done
Gate produces correct recommendations for all blocking scenarios; threshold is config-driven; tests green.
