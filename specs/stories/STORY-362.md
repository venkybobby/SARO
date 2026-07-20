# STORY-362: Adapter Capability Matrix (Buyer-Facing)

**Status:** ready
**Screen/Area:** Docs (Pack Epic 14)
**Depends on:** STORY-359/360 field-mapping tables

## Goal
A one-page capability matrix (fields, rule-packs, trigger modes per adapter) a
technical buyer can use during evaluation.

## Acceptance Criteria
- AC-1: `docs/adapter-capability-matrix.md` covers Bedrock, Azure OpenAI,
  Vertex; generated or hand-authored **with a CI freshness check** against the
  field-mapping tables in docs/adapter-design.md.
- AC-2: Explicitly lists non-supported fields/modes (e.g., Azure streaming
  rows, live polling) — no aspirational rows.
- AC-3: Linked from README and the Compliance Hub docs area.

## Non-Functional Requirements
- Language guardrails per docs/compliance-claims.md (no "certified", no client results).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
