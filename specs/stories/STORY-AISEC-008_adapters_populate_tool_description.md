# STORY-AISEC-008: Adapters populate ToolInvocation.description from provider logs

**Status:** IMPLEMENTED (01cd4ec)
**Screen/Area:** adapters/{azure_openai,vertex_ai}/parse.py / rule_packs/observation (Bedrock N/A — scan-path)

## Origin
STORY-AISEC-006 shipped the `ToolInvocation.description` field + the
`rp_tool_poisoning` pack that scans it, but left it **optional/default-None** and
noted: *"adapter population from real provider logs is a later per-adapter story;
the field is a no-op until populated."* This is that story — it makes MCP
tool-description poisoning detection actually fire on real exported logs.

## Premise verification (FM-2 — verified before authoring)
| Referenced artifact | Verified? | File path / provider fact |
|---|---|---|
| Contract field (target) | yes (MERGED) | `adapters/contract.py` `ToolInvocation.description: str \| None` |
| Poisoning pack + check (consumer) | yes (MERGED) | `rule_packs/observation/rp_tool_poisoning/1.0.0/pack.yaml`, `evaluate._check_tool_description_injection` |
| **Bedrock observation-record path** | **PREMISE-CORRECTED** | `adapters/bedrock/parse.py` builds an **`AuditSubmission`** (scan path), NOT a `NormalizedInvocationRecord` — tool names go into `metadata.toolConfig/toolUse`. `from_bedrock_envelope` (→ observation record w/ `ToolInvocation`) is only called from `tests/conformance/providers.py` (test scaffolding). **Bedrock has no PRODUCTION observation `ToolInvocation` to populate** → out of scope here. |
| Azure tool extraction (builds the record) | yes | `adapters/azure_openai/parse.py` `_extract_tools` builds `ToolInvocation(...)`; `parse` returns a `NormalizedInvocationRecord` (`tools=tools`). Description at `item.function.description`. |
| Vertex tool extraction (builds the record) | yes | `adapters/vertex_ai/parse.py` `_extract_tools` builds `ToolInvocation(...)`; `parse` returns a `NormalizedInvocationRecord` (`tools=tools`). Description at `item.functionDeclaration.description`. |
| Description lives in OFFERED config | yes | Bedrock `toolSpec.description`; Anthropic `tools[].description`; Azure `function.description`; Vertex `functionDeclaration.description` — all request-side (offered), not in the invoked `toolUse`/`tool_use` blocks |
| Adapter conformance harness | yes | `tests/conformance/` (CI "Cross-adapter conformance suite") |

## Goal
Have each provider adapter capture the **offered** tool's advertised
`description` text and pass it to `ToolInvocation(description=...)`, so the
`rp_tool_poisoning` scan (AISEC-006) fires on real logs. Descriptions come from
the request-side tool declarations; invoked-only tools (no offered declaration)
carry `description=None`. Bounded, backward-compatible, adapter-agnostic downstream
(the evaluator/contract are unchanged).

> **Scope corrected during DISCOVER:** only Azure and Vertex have a production
> observation-record path (their `parse` returns a `NormalizedInvocationRecord`
> with `ToolInvocation`s). Bedrock's production `parse` goes to the scan path
> (`AuditSubmission`); it has no production observation `ToolInvocation`, so it is
> **out of scope** here (a Bedrock observation-record path would be its own story).

## Acceptance Criteria (Given/When/Then)
- AC-1: **(Bedrock — N/A this story)** Bedrock has no production observation
  record; deferred until a Bedrock observation path exists.
- AC-2: Given an Azure OpenAI export with `function.description`, When parsed,
  Then the `ToolInvocation.description` is populated.
- AC-3: Given a Vertex AI export with `functionDeclaration.description`, When
  parsed, Then the `ToolInvocation.description` is populated.
- AC-4: Given a tool that was **invoked but not offered** (a `toolUse`/`tool_use`
  block with no request-side declaration), When parsed, Then its `description`
  is `None` (no description available in the log — never fabricated).
- AC-5: Given an export with **no** tool descriptions (or names-only tool data),
  When parsed, Then behavior is unchanged from today (`description=None`) —
  backward compatible; existing conformance/snapshot fixtures unaffected.
- AC-6: End-to-end — Given a poisoned tool description in a real-shaped export
  fixture, When the record is parsed and evaluated, Then `rp_tool_poisoning`
  fires `TOOL-DESC-POISONING-1` with the injection indicators (adapter → record →
  evidence, proven per provider).
- AC-7: Given an adversarially long description, When captured, Then it is bounded
  to a documented max length (proposal: 8 KB) so a record cannot be inflated
  without limit (addresses the AISEC-006/007 security INFO on the unbounded field).

## Edge Cases
- Description present on the offered spec but the tool is also invoked → attach
  the offered description to the single merged `ToolInvocation` (tools are keyed
  by name; offered+invoked collapse to one entry today).
- Mixed: some offered tools have descriptions, some don't → per-tool None where absent.
- Non-string / structured description (unlikely per schema) → coerce to str or drop
  (never crash the parse).
- Homoglyph/obfuscated poisoning in the description → already handled by the
  detector's AISEC-005 fold (no adapter work needed).

## Out of Scope
- **Rug-pull / description-drift over time** (AISEC-004 deferred) — needs a
  per-tool description hash + first-seen tracking, a separate story.
- Carrying tool **arguments or results** — INV-2: those remain absent.
- Demo/screencast integration (the demo is pinned to its 2 packs in AISEC-006);
  showing poisoning in the demo would be a separate, opt-in change.
- Any change to the contract, evaluator, or `rp_tool_poisoning` pack (all done).

## Non-Functional Requirements
- Backward-compatible: description is additive; absent → None; existing
  conformance + snapshot fixtures must not change unless a fixture gains a
  description on purpose (regenerate deliberately).
- Deterministic parse; bounded description length (AC-7). No new dependency.
- INV-2 note: descriptions are advertised metadata (per AISEC-006's disclosed
  determination), not message body — the adapter reads only the request-side tool
  *declaration*, never arguments/results.
- reviewer + security-auditor approve (adapters + input-handling).

## Benefits
- **Activates a shipped-but-dormant control:** AISEC-006's poisoning scan only
  fires once descriptions are populated — this makes MCP tool-poisoning evidence
  real on live Bedrock/Azure/Vertex exports (ATLAS AML.T0010).
- **Localized, low-risk:** three small `_extract_tools` changes + fixtures; the
  contract, evaluator, and pack are untouched.

## Suggested implementation sketch (non-binding)
- Add a `_tool_specs(container) -> list[tuple[name, description|None]]` beside each
  `_tool_names`, reading the provider's description field; thread descriptions into
  `_extract_tools` so the merged `ToolInvocation` per name gets the offered
  description. Cap at 8 KB in the contract or at capture.
- Fixtures: one poisoned + one benign tool-description export per provider under
  the adapter test/fixture dirs; assert population (AC-1..3), None cases
  (AC-4/AC-5), and end-to-end poisoning firing (AC-6).

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 (Bedrock) | N/A — out of scope (no production observation path) | — |
| AC-2 (Azure populates) | `test_azure_populates_description_and_poisoning_fires`, `test_azure_benign_description_populated_but_no_finding` | `adapters/azure_openai/parse.py` (`_tool_descriptions`, `_extract_tools`) |
| AC-3 (Vertex populates) | `test_vertex_populates_description_and_poisoning_fires`, `test_vertex_benign_description_populated_but_no_finding` | `adapters/vertex_ai/parse.py` (`_tool_descriptions`, `_extract_tools`) |
| AC-4 (invoked-only → None) | `test_azure_invoked_only_tool_has_no_description`, `test_vertex_invoked_only_tool_has_no_description` | both adapters |
| AC-5 (no tools unchanged) | `test_azure_no_tools_unchanged`, adapter suites 70/70 | both adapters |
| AC-6 (end-to-end poisoning fires) | the `..._poisoning_fires` tests (parse → evaluate `TOOL-DESC-POISONING-1`) | adapters + `rule_packs/observation` |
| AC-7 (bounded 8 KB) | `test_clamp_bounds_and_coerces`, `test_azure_oversized_description_is_clamped` | `adapters/contract.py` (`clamp_tool_description`, `MAX_TOOL_DESCRIPTION_CHARS`) |
