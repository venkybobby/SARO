# STORY-337 — Claims-consistency guard (locked Compliance Claims Matrix)

**Epic:** GRC-9 — Architectural Invariants & Claims Integrity
**Priority:** P1 (highest-leverage preventative) · **Status:** READY · **Depends on:** STORY-336

## Context
DEC-4 contradicted a locked claim and a single-axis gap analysis could not catch it. This story is the
durable fix: make the Compliance Claims Matrix machine-checkable so any new story, PR, or doc that
introduces a capability contradicting a locked claim is flagged automatically — "prompts suggest, hooks
enforce, CI guarantees" applied to claims integrity.

## Framework mapping
- AIGP: accountability / truthful representation.
- NIST AI RMF: GOVERN.

## Scope (in)
- A structured registry of locked claims as checkable assertions, seeded from the Compliance Claims
  Matrix, including at least:
  - SARO never calls external AI models at runtime (enforced concretely by STORY-336).
  - SARO never certifies compliance.
  - SARO always requires human-in-the-loop review.
  - SARO never writes to client systems.
  - AIGP = principles evaluation only (never "framework" or "certification").
  - EU AI Act coverage = evidence support for Articles 9/13/17 only.
  - ISO 42001 support = lightweight document lifecycle linking only.
- A CI step + required PR checklist: each new story/PR is checked against the registry; a contradiction
  blocks merge or requires an explicit, logged claim-change decision.
- Targeted automated checks where a claim is mechanically verifiable (e.g., the external-model claim
  delegates to STORY-336; framing-language checks flag forbidden terms like "certification"/"framework"
  applied to AIGP).

## Out of scope
- Full NLP contradiction detection (out of reach; not attempted). Auto-resolving contradictions.

## Acceptance criteria (binary)
- [ ] The claims registry exists and is versioned.
- [ ] A PR introducing an external-model runtime call is blocked (via STORY-336).
- [ ] A doc/story describing AIGP as a "certification" or "framework" is flagged by the framing check.
- [ ] Changing a locked claim requires an explicit, logged decision — it cannot happen silently.

## Technical notes
- Keep it pragmatic: a registry + required checklist + a few mechanical checks beats an unachievable
  general contradiction detector. The mechanical checks grow over time.

## Test requirements
- [ ] Negative: an AIGP-as-"certification" string is flagged; an external-model call is blocked.
- [ ] Positive: a compliant story passes the guard.

## Definition of done
Locked claims are a versioned, CI-checked registry; mechanical violations are blocked; claim changes are logged; tests green.
