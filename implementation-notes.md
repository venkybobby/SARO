# STORY-AISEC-008 — Adapters populate ToolInvocation.description
Stage: standard

## Lifecycle
- [x] discover   (three adapter parsers + provider description-field locations mapped)
- [x] shape      (decisions below; no product ambiguity — activates a shipped control)
- [x] preview    (skipped — backend adapters, no UI)
- [x] plan
- [x] build
- [x] verify     (full suite 2387 passed; reviewer APPROVE + security-auditor PASS)
- [ ] sell       (n/a)

## DISCOVER findings
- Each adapter builds `ToolInvocation(name, offered, invoked)` from names only:
  - Bedrock: `bedrock/parse.py` `_offered_tools` reads `toolConfig.tools[].toolSpec.name`
    (Converse) + `tools[].name` (Anthropic). Description at `toolSpec.description`
    / `tools[].description`.
  - Azure: `azure_openai/parse.py` `_extract_tools`/`_tool_names` → `item.name` /
    `item.function.name`. Description at `function.description`.
  - Vertex: `vertex_ai/parse.py` `_extract_tools`/`_tool_names` → `item.name` /
    `item.functionDeclaration.name`. Description at `functionDeclaration.description`.
- Description is request-side (OFFERED) only; invoked `toolUse`/`tool_use` blocks
  carry name+input, no description → invoked-only tools get description=None.
- Downstream (contract field, `rp_tool_poisoning`, evaluator) all MERGED (AISEC-006).

## Decision Log
- Description source? → **offered/request-side tool config only** (that's where it
  lives); invoked-only → None (never fabricated).
- Length bound (AC-7 / auditor INFO)? → **truncate at capture to 8192 chars**
  (`MAX_TOOL_DESCRIPTION_CHARS` in adapters/contract.py). Truncate, NOT reject —
  a >8KB description must not break the parse.
- Merge offered+invoked? → tools key by name today (offered+invoked collapse to one
  ToolInvocation); attach the offered description to that single entry.
- Shared helper vs per-adapter? → per-adapter `_tool_specs`-style extraction
  (provider shapes differ), using the one shared cap constant.

## SCOPE CORRECTION (DISCOVER, FM-2)
Bedrock's production `parse` returns an `AuditSubmission` (scan path), NOT a
`NormalizedInvocationRecord` — its observation/`ToolInvocation` path is TEST-ONLY
(conformance harness via `from_bedrock_envelope`). So **Bedrock is out of scope**;
only **Azure + Vertex** produce production observation records with ToolInvocation.
Spec premise + ACs corrected accordingly.

## Plan (tweak-likelihood order)
1. **Contract constant** `MAX_TOOL_DESCRIPTION_CHARS = 8192` + a `clamp_tool_description`
   helper in adapters/contract.py. Verify: unit test the cap.
2. **Azure** `_extract_tools` → capture `function.description` (clamped), attach to
   ToolInvocation. Verify: AC-2 + AC-6 (poisoned/benign fixtures).
3. **Vertex** `_extract_tools` → capture `functionDeclaration.description` (clamped).
   Verify: AC-3 + AC-6.
4. Tests `tests/test_aisec_008_adapter_tool_description.py` (AC-2..7 for Azure+Vertex;
   AC-4 invoked-only=None; AC-5 backward-compat; AC-7 cap). Gates 1-7; reviewer +
   security-auditor; index → IMPLEMENTED; conformance suite unchanged.

## Compliance guardrails
- INV-2: read only the request-side tool DECLARATION (metadata), never args/results.
- Backward compatible: absent description → None; existing conformance/snapshot
  fixtures unchanged unless deliberately given a description.
- Bounded (8KB), deterministic, no new dependency.

## Review round 1 (reviewer + security-auditor agents)
- **security-auditor: PASS.** Untrusted description string-matched only (defensive
  isinstance guards; no eval/exec); bounded (8192 clamp + upstream MAX_RECORD_CHARS);
  body-blind intact (Azure `properties`, Vertex `labels` — never protoPayload); no
  new raw-content egress; bandit clean.
- **reviewer: REQUEST-CHANGES → addressed:**
  1. [BLOCKER/FM-4] code uncommitted + index SPECIFIED → committing code+test now,
     index flipped to IMPLEMENTED citing the SHA (same PR).
  2. [MINOR] drive-by ruff reformat in the two parse files → accepted (repo formatter).
  3. [MINOR] empty-string top-level description shadowed the nested one → fixed:
     `desc = item.get("description") or fn.get("description")` (falsy falls through).
  - Scope correction (Bedrock out) confirmed accurate + honestly surfaced.

## Deviations
- Spec authored + committed first (b9b65a4) on this branch, then built here — one
  story PR (spec + code + index flip).
- Bedrock OUT of scope (DISCOVER/FM-2): its production parse is scan-path
  (AuditSubmission), no observation ToolInvocation. Azure + Vertex only.
