# STORY-312 — Hard-rule enforcement

**Epic:** GRC-3 — Output Audit Engine
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-308, STORY-328

## Context
The auditor's hard rules must be enforced in the pipeline so convenient-but-false conclusions are
structurally impossible, not merely discouraged in a prompt.

## Framework mapping
- NIST AI RMF: GOVERN.
- AIGP: accountability.

## Scope (in)
Enforce three rules in the audit pipeline:
1. **No PASS without linked evidence** (service-side, complementing the contract rule in STORY-328).
2. **Fact vs. inference separated** — each finding records evidence-derived facts distinctly from the auditor's assessment.
3. **No silent scope softening** — any reinterpretation that would downgrade a finding is surfaced as an explicit flag, not applied quietly.

## Out of scope
- Citation accuracy (STORY-317). Escalation (STORY-313, Phase 2).

## Acceptance criteria (binary)
- [ ] Pipeline rejects/blocks a `PASS` finding whose evidence is not `LINKED`.
- [ ] Each finding exposes a `facts` field and an `assessment` field that are not conflated.
- [ ] A scope reinterpretation that lowers severity sets an explicit `scope_change_flag` rather than silently applying.
- [ ] Each rule has a negative test proving the pipeline catches the violation.

## Technical notes
- Implement as pipeline guards that run before a result is finalized; a guard failure raises, it does not warn-and-continue.

## Test requirements
- [ ] Negative test per rule (unevidenced PASS, conflated fact/inference, silent softening).

## Definition of done
All three rules enforced with passing negative tests; pipeline blocks violations; tests green.
