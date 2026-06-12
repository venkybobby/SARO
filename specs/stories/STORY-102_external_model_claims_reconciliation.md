# STORY-102: Reconcile "No External Model Calls" Claim with Hybrid Gate-3 Reality (G-2)
Status: ready
Screen/Area: Documentation / Claims Matrix — `docs/how-saro-reasons.md`, `docs/backlog.md`, Claims Matrix

## Goal
`docs/backlog.md` Epic 10 asserts "read-only, no external model calls, human-in-the-loop" while engine.py calls the Anthropic API whenever `ANTHROPIC_API_KEY` is set (engine.py:1349–1350). `docs/how-saro-reasons.md` — the canonical scoring-methodology document — contains zero mention of the LLM judge. The DPA discloses the flow; the methodology doc and backlog deny it. This re-introduces the exact red-team finding from April 2026 and violates the Claims Matrix governance rule. All claim-bearing artifacts must state hybrid mode honestly and identically.

GRC mapping: EU AI Act Art. 13 (transparency to deployers) & Art. 52; ISO/IEC 42001 A.8 (information for interested parties); NIST AI RMF GOVERN 4.1, MAP 1.1; AIGP duty of accurate disclosure. Contradictory transparency artifacts are the single fastest way to fail the AI Auditor (deal-killer) persona.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given an auditor reads `docs/how-saro-reasons.md`, When they reach the scoring pipeline section, Then a "Hybrid Verification (Gate 3)" section exists stating: when it activates (tenant opt-in + key-gated), what is sent (redacted samples ≤500 chars per STORY-101), what is never sent, the sub-processor identity, and the fallback behavior when disabled.
- AC-2: Given `docs/backlog.md` Epic 10, When the posture statement is read, Then it is amended to "read-only ingestion, human-in-the-loop; external model calls occur only in tenant-opt-in Hybrid Gate-3 mode as documented in how-saro-reasons.md."
- AC-3: Given the Claims Matrix, When the "no external AI calls" claim row is reviewed, Then it is either re-scoped with the hybrid-mode qualification or retired, with SME-validation status reset accordingly (per SARO_GRC_SME_Validation_Requirements_v1.0 — no claim issued before SME validation).
- AC-4: Given the compliance-guard skill/CI gate, When any doc asserts "no external model calls" without the hybrid qualifier, Then the gate fails the build (grep-based rule for llm|hybrid|judge consistency across claim-bearing docs).
- AC-5: Given a fresh-context reviewer subagent, When asked "does SARO call external models?", Then every canonical doc yields the same answer.

## Edge Cases
- Tenants on contracts signed under the old "no external calls" language → flag for legal review list; do not silently reinterpret.
- Marketing/landing copy (veriaegis-landing) repeating the old claim → inventory and correct or strip (coordinates with STORY-106).
- TRACE view UI text implying purely deterministic reasoning → audit strings for the same contradiction.

## Out of Scope
- Code changes to engine.py (STORY-101).
- Authoring the full "How SARO Reasons" transparency rewrite owned by Alex Rivera for enterprise demos — this story patches the contradiction; the deep rewrite remains his deliverable.

## Non-Functional Requirements
- Doc changes versioned with changelog entry; Claims Matrix change logged in findings ledger.
- Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
