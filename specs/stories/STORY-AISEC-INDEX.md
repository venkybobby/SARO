# STORY-AISEC Index — AI-security leverage from the cybersecurity-skills library

> Source: product-owner review (2026-07-24) of the Apache-2.0 community library
> `mukul975/Anthropic-Cybersecurity-Skills` (817 skills; 14-skill `ai-security`
> subdomain). These four stories capture only the slice that fits SARO's
> immutable posture — deterministic, evidence-only, no external model in core
> scoring. Model-based detectors (Llama Guard, Prompt Guard 2, NeMo) are
> explicitly excluded from core scoring per Non-Negotiable #1.
>
> Status vocabulary is the closed set enforced by `scripts/check_story_index.py`:
> SPECIFIED (document exists, no code) → IMPLEMENTED (cites a reachable commit
> SHA) → MERGED. All four are drafts (no code yet), so status is SPECIFIED.

| Story | Title | Status | Evidence |
|---|---|---|---|
| STORY-AISEC-001 | Deterministic prompt-injection normalization + detection rule-pack | IMPLEMENTED | 0d905d3 — `rule_packs/injection/` + `engine._scan_injection` (evidence-only); `tests/test_aisec_001_injection_detector.py` 14/14; full suite 2309 passed, ratchet 89.10%; reviewer + security-auditor addressed |
| STORY-AISEC-002 | MITRE ATLAS evidence axis on findings + TRACE | SPECIFIED | spec only — `specs/stories/STORY-AISEC-002_mitre_atlas_evidence_axis.md` |
| STORY-AISEC-003 | Adversarial prompt-injection eval corpora for saro-data-framework | SPECIFIED | spec only — `specs/stories/STORY-AISEC-003_adversarial_eval_corpora.md` |
| STORY-AISEC-004 | SPIKE — agentic / MCP tool-invocation evidence coverage assessment | SPECIFIED | spec only — `specs/stories/STORY-AISEC-004_agentic_tool_scope_spike.md` |

## Recommended sequence & dependencies
1. **AISEC-001** first — the deterministic detector; highest value, lowest posture
   risk, no dependencies. Everything else leans on it.
2. **AISEC-002** next — additive ATLAS evidence axis; AISEC-001 findings become
   its first consumer (AML.T0051.001 / AML.T0054).
3. **AISEC-003** — benchmarks AISEC-001; depends on the detector existing.
4. **AISEC-004** — independent spike; can run in parallel, output is a doc.

## Cross-cutting guardrails (baked into every story)
- **Non-Negotiable #1** — core scoring stays external-model-free; guard/judge
  models allowed ONLY on the disclosed off-by-default Gate-3 path (SARO-102).
- **Claims matrix** — ATLAS/NIST references stay Tier-3 evidence-only; no
  conformance/verdict language (compliance-guard).
- **FM-2** — every reference verified to a file path above; upstream ATLAS/RMF
  frontmatter is re-verified, never trusted (it mis-files AI-RMF codes under a
  `nist_csf:` key).
- **Attribution** — upstream is Apache-2.0; preserve NOTICE/attribution where code
  semantics are ported (lifecycle Port sub-protocol: reimplement, don't transliterate).
