# STORY-309 — Automated output checks

**Epic:** GRC-3 — Output Audit Engine
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-308
**Encodes decision:** OPEN-DEC-4 → buy commodity checks, build the regulatory-claim check

## Context
Automated checks catch common failure modes on each output without manual review. Each check
produces a finding the orchestrator scores and dispositions.

## Framework mapping
- NIST AI RMF: valid & reliable; privacy-enhanced; fair with harmful bias managed.
- ISO/IEC 42001: data quality / fairness controls.

## Scope (in)
Five checks, each emitting a finding:
1. **Groundedness / hallucination** — LLM-as-judge against `retrieved_context` (reuse the Anthropic API pattern). Unsupported factual claims flagged.
2. **Sensitive-data leakage** — PII/PHI/secrets via a proven library (Presidio-style), not hand-rolled.
3. **Harmful bias** — disparate treatment across relevant protected-attribute slices via a metric library.
4. **Prohibited / out-of-scope use** — output checked against the system's authorized `purpose` from the registry.
5. **Regulatory-claim accuracy** — **built in-house**; defers to STORY-317 for citation verification.

## Out of scope
- Explainability sufficiency check (Phase 2). Citation source-of-truth itself (STORY-317).

## Acceptance criteria (binary)
- [ ] Each of the five checks runs and returns a structured finding (pass/concern + detail).
- [ ] Groundedness flags an unsupported claim in a fixture; passes a supported one.
- [ ] Leakage check detects a planted PII string; passes a clean output.
- [ ] Prohibited-use check fails an output serving a use outside the registry `purpose`.
- [ ] Regulatory-claim check routes any compliance/legal/medical/financial claim through STORY-317 verification.

## Technical notes
- Each check is an independent module with a uniform interface so checks can be added/removed and tier-selected later (STORY-304).
- External libraries/services are themselves third-party dependencies — register them under the vendor-risk process (STORY-316) later. (Noted, not built here.)

## Test requirements
- [ ] Unit per check: one passing and one failing fixture each.
- [ ] Integration: all five run within the orchestrator on a sample output.

## Definition of done
Five checks operational with passing+failing fixtures; regulatory-claim check wired to STORY-317; tests green.
