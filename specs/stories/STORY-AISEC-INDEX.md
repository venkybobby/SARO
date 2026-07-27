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
| STORY-AISEC-002 | MITRE ATLAS evidence axis on findings + TRACE | IMPLEMENTED | 4e58b0d — `rule_packs/atlas/` verified registry + `engine.py` ATLAS axis (evidence-only, detector-anchored); `tests/test_aisec_002_atlas_axis.py` 8/8; full suite 2321 passed, ratchet 89.13%; reviewer APPROVE + security-auditor PASS |
| STORY-AISEC-003 | Adversarial prompt-injection eval corpora for saro-data-framework | IMPLEMENTED | 2669ca0 — `rule_packs/injection/eval.py` + 347-sample corpus + `scripts/run_injection_eval.py`; `tests/test_aisec_003_injection_eval.py` 10/10; targeted recall 0.80 / held-out 0.0 (honest split); full suite 2331 passed, ratchet 89.16%; reviewer APPROVE + security-auditor PASS |
| STORY-AISEC-004 | SPIKE — agentic / MCP tool-invocation evidence coverage assessment | DRAFTED | assessment authored (spike output, no code by design) — `specs/stories/STORY-AISEC-004_agentic_tool_scope_spike.md` §Assessment |
| STORY-AISEC-005 | Homoglyph / confusable normalization for the injection detector | IMPLEMENTED | 718e04f — `_CONFUSABLES` fold in `rule_packs/injection/detector.py` normalize(); homoglyph recall 0.0→0.9444, FPR stays 0.0; `tests/test_aisec_005_homoglyph_normalization.py` 8/8; full suite 2362 passed, ratchet 89.04%; reviewer APPROVE + security-auditor PASS |
| STORY-AISEC-006 | MCP tool-description poisoning evidence (scan tool descriptions) | IMPLEMENTED | fc08197 — `ToolInvocation.description` + `rp_tool_poisoning` pack + `_check_tool_description_injection` (evidence-only, ATLAS AML.T0010); `tests/test_aisec_006_tool_description_poisoning.py` 9/9; full suite 2371 passed, ratchet 89.06%; reviewer APPROVE + security-auditor PASS |
| STORY-AISEC-007 | Semantic prompt-injection on the optional Gate-3 judge (held-out gap) | IMPLEMENTED | 5204926 — `engine._scan_injection_semantic` on the disclosed off-by-default judge (SARO-102); catches held-out injection when enabled, PII-redacted/bounded/evidence-only, zero calls by default; `tests/test_aisec_007_semantic_injection_judge.py` 7/7; full suite 2378 passed, ratchet 89.09%; reviewer APPROVE + security-auditor PASS |
| STORY-AISEC-008 | Adapters populate `ToolInvocation.description` from provider logs (Azure + Vertex; Bedrock N/A) | IMPLEMENTED | 01cd4ec — Azure + Vertex `_extract_tools` capture the offered tool description (clamped 8 KB); activates AISEC-006's `rp_tool_poisoning` on real exports; Bedrock out of scope (scan-path, no observation record); `tests/test_aisec_008_adapter_tool_description.py` 9/9; full suite 2387 passed, ratchet 89.11%; reviewer APPROVE + security-auditor PASS |

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
