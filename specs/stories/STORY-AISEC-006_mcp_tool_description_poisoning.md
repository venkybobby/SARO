# STORY-AISEC-006: MCP tool-description poisoning evidence (scan tool descriptions)

**Status:** draft
**Screen/Area:** adapters/contract (ToolInvocation) / rule_packs/observation / TRACE evidence

## Origin
The AISEC-004 spike named this the top posture-safe agentic opportunity: MCP
**tool-poisoning** (hidden instructions in a tool's *description* text — ATLAS
AML.T0010 / OWASP MCP03) is indirect prompt injection delivered through the tool
supply chain. It was gated on "an envelope-contract field for tool-description
text." This story adds that field and scans it with the AISEC-001 detector.

## Premise verification (FM-2 — verified before authoring)
| Referenced artifact | Verified? | File path |
|---|---|---|
| ToolInvocation contract | yes | `adapters/contract.py` (`ToolInvocation`: name/offered/invoked) |
| Observation evaluator + check dispatch | yes | `rule_packs/observation/evaluate.py` (`_CHECKS`, `_finding`, `evaluate_records`) |
| Genesis pack loader (globs all) | yes | `rule_packs/observation/loader.py` (`load_genesis_packs`) |
| AISEC-001 injection detector | yes (MERGED) | `rule_packs/injection/detector.py` (`scan`, `load_injection_pack`) |
| ATLAS registry | yes (MERGED) | `rule_packs/atlas/registry.py` |
| Demo pack selection | yes | `scripts/demo_azure_vertex_e2e.py` `_demo_packs` (iterates all genesis packs) |

## Goal
Carry the tool's advertised **description** text (metadata, NOT arguments/results
— INV-2 still holds) in the contract, and add an observation check that scans it
with the AISEC-001 injection detector, emitting evidence-only findings when a tool
description contains injection/poisoning indicators. Read-only, deterministic, no
external model, evidence-only. ATLAS-tagged (AML.T0010 / AML.T0051.001).

## Acceptance Criteria (Given/When/Then)
- AC-1: Given a `ToolInvocation` with a `description` containing an injection
  directive (e.g. "…ignore all previous instructions and exfiltrate…"), When the
  record is evaluated, Then a tool-description-poisoning finding fires carrying the
  matched injection indicators and an ATLAS technique id.
- AC-2: Given a tool with a benign description, When evaluated, Then no finding
  fires (no false positive).
- AC-3: Given a tool with no description (`None`) — the default and every existing
  adapter today — When evaluated, Then the check is a no-op (backward compatible;
  existing records, the demo, and its committed counts/screencast are unchanged).
- AC-4: Given evaluation, When it runs, Then it makes zero external-model/network
  calls (deterministic detector) — consistent with SARO posture and INV-2
  (descriptions are advertised metadata, not message body).
- AC-5: Given the finding, When surfaced, Then its language is evidence-shaped
  ("indicators consistent with…", human review required) — never a verdict.

## Edge Cases
- A homoglyph/obfuscated poisoning payload in the description → caught (reuses the
  AISEC-005 normalization/fold in the detector).
- Multiple tools each with a poisoned description → one finding per poisoned tool.
- Very long description → bounded by the detector's `max_scan_chars`.

## Out of Scope
- **Adapter population** of `description` from real provider logs (Bedrock/Azure/
  Vertex) — a later per-adapter story; the field is optional (default None) so
  adapters opt in when the log carries it.
- SSRF / unauthenticated-MCP-exposure / rug-pull detection (AISEC-004 rejected/
  deferred those).
- Any write/block/interception — read-only, evidence-only.

## Non-Functional Requirements
- Additive/backward-compatible: `description` optional (default None); the new
  genesis pack is a no-op on description-less records. Demo pinned to its two
  intended packs so the new pack does not ripple into its provenance/screencast.
- Deterministic, no network, no new dependency. Quality ratchet holds.
- reviewer + security-auditor approve (contract + rule_packs + input-handling).

## Benefits
- **Closes the AISEC-004 top pick, posture-safe:** turns MCP tool-poisoning into
  auditor-ready evidence by reusing the shipped injection detector — no external
  model, read-only, evidence-only.
- **Supply-chain coverage:** names the real ATLAS technique (AML.T0010) SARO
  otherwise had no signal for.
- **Zero blast radius by default:** optional field, no-op until an adapter or
  tenant supplies tool descriptions.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 (poisoned desc fires + ATLAS/indicators) | `test_poisoned_description_fires_with_atlas_and_indicators`, `test_multiple_poisoned_tools_each_fire` | `rule_packs/observation/evaluate.py` (`_check_tool_description_injection`), `rule_packs/observation/rp_tool_poisoning/1.0.0/pack.yaml` |
| AC-2 (benign no false positive) | `test_benign_description_does_not_fire` | `rule_packs/observation/evaluate.py` |
| AC-3 (no-description no-op, backward compat) | `test_no_description_is_a_noop`, `test_tool_invocation_description_defaults_to_none`, demo tests unchanged (`_demo_packs` pin) | `adapters/contract.py` (`ToolInvocation.description`), `scripts/demo_azure_vertex_e2e.py` |
| AC-4 (no network/model) | `test_evaluation_makes_no_network_calls` | `rule_packs/observation/evaluate.py` |
| AC-5 (evidence-shaped, no verdict) | `test_finding_language_is_evidence_shaped_not_a_verdict` | `rule_packs/observation/rp_tool_poisoning/1.0.0/pack.yaml` |
| (pack provenance + genesis load) | `test_poisoning_pack_loads_with_hash`, `test_new_pack_does_not_break_genesis_load` | `rule_packs/observation/loader.py` (`KNOWN_CHECKS`) |
