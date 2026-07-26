# STORY-AISEC-008: Adapters populate ToolInvocation.description from provider logs

**Status:** draft
**Screen/Area:** adapters/{bedrock,azure_openai,vertex_ai}/parse.py / rule_packs/observation

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
| Bedrock tool extraction (names-only today) | yes | `adapters/bedrock/parse.py` `_offered_tools` reads `toolConfig.tools[].toolSpec.name` (Converse) + `tools[].name` (Anthropic InvokeModel) |
| Azure tool extraction | yes | `adapters/azure_openai/parse.py` `_extract_tools`/`_tool_names` reads `item.name` / `item.function.name` |
| Vertex tool extraction | yes | `adapters/vertex_ai/parse.py` `_extract_tools`/`_tool_names` reads `item.name` / `item.functionDeclaration.name` |
| Description lives in OFFERED config | yes | Bedrock `toolSpec.description`; Anthropic `tools[].description`; Azure `function.description`; Vertex `functionDeclaration.description` — all request-side (offered), not in the invoked `toolUse`/`tool_use` blocks |
| Adapter conformance harness | yes | `tests/conformance/` (CI "Cross-adapter conformance suite") |

## Goal
Have each provider adapter capture the **offered** tool's advertised
`description` text and pass it to `ToolInvocation(description=...)`, so the
`rp_tool_poisoning` scan (AISEC-006) fires on real logs. Descriptions come from
the request-side tool declarations; invoked-only tools (no offered declaration)
carry `description=None`. Bounded, backward-compatible, adapter-agnostic downstream
(the evaluator/contract are unchanged).

## Acceptance Criteria (Given/When/Then)
- AC-1: Given a Bedrock Converse export whose `toolConfig.tools[].toolSpec`
  carries a `description`, When parsed, Then the corresponding `ToolInvocation`
  has that description; same for Anthropic-on-Bedrock `tools[].description`.
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

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
