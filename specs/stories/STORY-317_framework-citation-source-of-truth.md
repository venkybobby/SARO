# STORY-317 — Framework citation source-of-truth + verification

**Epic:** GRC-4 — Risk, Controls & Framework Crosswalk
**Priority:** P0 · **Status:** READY · **Depends on:** none
**Encodes decision:** OPEN-DEC-2 → build a thin in-house crosswalk now; defer commercial library

## Context
A fabricated clause citation is the failure mode that burns auditor trust — it already bit SARO
once. Framework mappings must resolve against an authoritative reference and be flagged
VERIFIED/UNVERIFIED; the system must never assert a clause it cannot resolve.

## Framework mapping
- AIGP: accountability.
- ISO 42001 / NIST / EU AI Act: the crosswalk targets.

## Scope (in)
- A maintained crosswalk table seeded from the framework texts you hold: ISO 42001 Annex A control areas, NIST AI RMF functions/subcategories, EU AI Act high-risk obligations.
- A verification function: a citation that resolves to a table entry → `VERIFIED`; one that does not → `UNVERIFIED`.
- Consumed by STORY-309's regulatory-claim check and (later) STORY-316's crosswalk.

## Out of scope
- Buying a commercial GRC content library (deferred). Full de-duplicated crosswalk reporting (STORY-316, Phase 2).

## Acceptance criteria (binary)
- [ ] The crosswalk table is seeded and queryable for all three frameworks.
- [ ] A known clause/control resolves to `VERIFIED`.
- [ ] An unknown/invented clause resolves to `UNVERIFIED` — never emitted as confident fact.
- [ ] The verification function is callable by the audit pipeline.

## Technical notes
- Keep the table human-maintainable (versioned seed data); each entry: framework, identifier, plain-language description, source reference.
- Do **not** hand-author clause numbers you cannot source — leave the identifier blank and mark the area in plain language rather than guess.

## Test requirements
- [ ] Unit: known identifier → VERIFIED; fabricated identifier → UNVERIFIED.
- [ ] Data test: seed loads and covers the three frameworks' core areas.

## Definition of done
Crosswalk seeded; verification distinguishes known vs. unknown citations; pipeline can call it; tests green.
