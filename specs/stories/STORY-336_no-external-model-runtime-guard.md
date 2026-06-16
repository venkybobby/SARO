# STORY-336 — No-external-model-at-runtime invariant guard

**Epic:** GRC-9 — Architectural Invariants & Claims Integrity
**Priority:** P0 · **Status:** READY · **Depends on:** none

## Context
SARO's locked claim — "never calls external AI models at runtime" — must be enforced in code, not
trusted to reviewers. This is the durable fix for the class of error that DEC-4 represented: a guard
that fails CI the moment a product-path module reaches a third-party hosted model.

## Invariant (precise)
No code path in the **product/runtime path** may transmit client data to, or invoke, a **third-party
hosted model API**. Self-hosted models inside SARO infra are permitted. The **offline QA lab** module
(STORY-338) is explicitly exempt and must be isolated from the product path.

## Framework mapping
- NIST AI RMF: GOVERN (accountability for declared behavior).
- AIGP: accountability / claim integrity.

## Scope (in)
- A definitive allowlist/denylist of model-provider SDKs and API endpoints treated as "external."
- A static guard (import/dependency lint + call-site check) that fails if any product-path module
  references an external model SDK or endpoint.
- An explicit exemption for the offline QA lab package, asserted to be unreachable from product code.

## Out of scope
- Replacing legitimate self-hosted model usage. Network-layer egress policy (can be a fast-follow).

## Acceptance criteria (binary)
- [ ] A deliberately added external-model call in a product-path module fails the guard.
- [ ] A self-hosted model call passes the guard.
- [ ] The offline QA lab package is exempt and proven unreachable from the product path.
- [ ] The guard runs in CI and blocks merge on violation.

## Technical notes
- Implement as an architectural/import test plus a small registry of forbidden external model
  packages/endpoints. Wire into the existing quality-gates workflow.
- Pair with a runtime egress check as a later hardening step if desired.

## Test requirements
- [ ] Positive: clean product path passes.
- [ ] Negative: injected external-model import/call fails CI.

## Definition of done
Guard enforces the invariant in CI, exempts the offline lab, blocks violations; tests green.
