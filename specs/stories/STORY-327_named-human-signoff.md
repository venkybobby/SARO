# STORY-327 — Named-human residual-risk sign-off

**Epic:** GRC-6 — Lifecycle Gates, Sign-off & Output Contract
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-326, STORY-331

## Context
Accountability is non-delegable. Accepting residual risk (e.g., a `GO_WITH_CONDITIONS`) requires a
named human in a defined role — the system records who, in what role, and when.

## Framework mapping
- ISO/IEC 42001: leadership.
- NIST AI RMF: GOVERN.
- AIGP: accountability.

## Scope (in)
- A sign-off record on a gate decision: `{role, accepted_by, accepted_at}`.
- The role binds to the org RACI defined in config (STORY-331).
- A `GO_WITH_CONDITIONS` cannot be finalized without a completed sign-off.

## Out of scope
- Notification/approval UX. Multi-approver workflows (later if needed).

## Acceptance criteria (binary)
- [ ] A residual-risk acceptance without a named `accepted_by` is rejected.
- [ ] The `role` must match an allowed sign-off role from config for that tier.
- [ ] `accepted_at` is recorded and immutable once set.
- [ ] `GO_WITH_CONDITIONS` is not finalized until sign-off is present.

## Technical notes
- Map sign-off role → tier in config (e.g., HIGH tier requires governance-committee role). For MVP a config constant is acceptable with a TODO to move to STORY-331's store.

## Test requirements
- [ ] Unit: missing approver rejected; wrong-role rejected; valid sign-off finalizes the decision.

## Definition of done
Residual acceptance requires a valid named human in an allowed role; recorded immutably; tests green.
