# STORY-328 — Audit-result JSON contract + validation

**Epic:** GRC-6 — Lifecycle Gates, Sign-off & Output Contract
**Priority:** P0 · **Status:** READY · **Depends on:** none (schema delivered)

## Context
The audit output is the boundary artifact everything else relies on. Validating it against the
JSON Schema contract enforces structural and policy rules at the edge, in code.

## Framework mapping
- NIST AI RMF: GOVERN (traceability).

## Scope (in)
- Integrate `ai_grc_audit_result.schema.json` as the validation contract for all audit outputs.
- A validation entry point that rejects non-conforming results.
- Confirm the three schema-enforced rules hold: PASS⇒evidence LINKED; CONDITIONAL/FAIL⇒remediation; Critical-FAIL⇒NO_GO.

## Out of scope
- The Pydantic model (STORY-329, Phase 2). The CI harness (STORY-330, Phase 2).

## Acceptance criteria (binary)
- [ ] A valid result instance passes validation.
- [ ] A `PASS` finding with `MISSING` evidence is rejected.
- [ ] A `FAIL`/`CONDITIONAL` finding with no remediation is rejected.
- [ ] A result containing a Critical FAIL but `gate_recommendation != NO_GO` is rejected.

## Technical notes
- Use a Draft 2020-12-capable validator (e.g., `jsonschema`).
- The schema is the single source of truth for enums; downstream code should not redefine them.

## Test requirements
- [ ] One valid fixture passes; one fixture per rule violation is rejected (these were proven during design — port them as regression tests).

## Definition of done
All audit outputs validate against the contract; each policy rule rejects its violation; tests green.
