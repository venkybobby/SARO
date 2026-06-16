# STORY-302 — Registry completeness enforcement

**Epic:** GRC-1 — AI Asset Registry & Risk Tiering
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-301

## Context
Unknown metadata must never be read as a safe default. A system with missing required governance
fields is a governance gap, and a gap must be able to block a deployment gate.

## Framework mapping
- ISO/IEC 42001: leadership / accountability.
- NIST AI RMF: GOVERN.

## Scope (in)
- A completeness check over registry entries that raises a `GOVERNANCE_GAP` flag per missing required field.
- Gaps are queryable per system and in aggregate.
- Expose a `has_open_gaps` signal consumed by the gate engine (STORY-326).

## Out of scope
- The gate decision itself (STORY-326). Auto-filling missing data.

## Acceptance criteria (binary)
- [ ] An entry missing any required governance field produces one `GOVERNANCE_GAP` per missing field.
- [ ] Gaps are listable per system and across the portfolio.
- [ ] `has_open_gaps == true` is exposed for a system with ≥1 open gap.
- [ ] Resolving the missing field clears the corresponding gap.

## Technical notes
- Implement as a pure function over a registry entry plus a config-driven required-field list (config lives in STORY-331; for MVP a constant is acceptable with a TODO to move to config).

## Test requirements
- [ ] Unit: complete entry → no gaps; each missing field → exactly one gap.
- [ ] Integration: gap clears after the field is supplied.

## Definition of done
Incomplete entries surface gaps; `has_open_gaps` exposed for the gate; tests green.
