# STORY-308 — Audit orchestrator service

**Epic:** GRC-3 — Output Audit Engine
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-305, STORY-328 (STORY-304 relaxed for MVP)

## Context
The orchestrator runs the output-audit protocol over an output and emits a contract-shaped
result. It is the spine that the checks, scoring, and gate hang off.

## Framework mapping
- NIST AI RMF: MEASURE, MANAGE.
- ISO/IEC 42001: operation.

## Scope (in)
- A service that, given an output id, runs the protocol: provenance check (STORY-306) → automated checks (STORY-309) → risk scoring & disposition (STORY-310) → assembles a result conforming to the JSON contract (STORY-328).
- Emits one result object per audited output.

## Out of scope
- Tier-driven check selection (STORY-304, Phase 2). Drift monitoring (STORY-311). Agent-action audit (Epic GRC-5).

## Dependency relaxation (MVP)
STORY-304 (tier routing) is **not** required for MVP. Run the **full** Phase-1 check set on every
output regardless of tier; the tier-routing layer slots in at Phase 2 without changing this interface.

## Acceptance criteria (binary)
- [ ] Given a valid output id, the orchestrator returns a result that validates against `ai_grc_audit_result.schema.json`.
- [ ] Provenance check runs first; incomplete provenance short-circuits to `EVIDENCE_GAP`.
- [ ] Each finding carries a disposition, risk score, and framework mapping.
- [ ] The orchestrator never emits `PASS` where evidence is not `LINKED`.

## Technical notes
- Keep orchestration declarative: a pipeline of independently testable steps; no step silently swallows a failure of a prior step.
- Output is the contract object (STORY-328 / Pydantic model in STORY-329).

## Test requirements
- [ ] Integration: sample output → schema-valid result.
- [ ] Integration: incomplete-provenance output → `EVIDENCE_GAP`, no `PASS`.

## Definition of done
Orchestrator produces a schema-valid result on sample outputs; provenance short-circuit works; tests green.
