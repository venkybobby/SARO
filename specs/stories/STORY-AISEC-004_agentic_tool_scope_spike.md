# STORY-AISEC-004: SPIKE — agentic / MCP tool-invocation evidence coverage assessment

**Status:** draft
**Screen/Area:** rule_packs (rp_tool_scope) / roadmap assessment (no implementation)

## Type
**Spike / assessment (SPECIFIED-only).** Output is a decision document, not code.
Deliberately fenced this way because the honest scope depends on findings — we do
not pre-commit to building a connector that could conflict with the read-only
posture.

## Source & attribution
Threat model from the Apache-2.0 `mukul975/Anthropic-Cybersecurity-Skills` skills
`securing-agentic-ai-tool-invocation` (ATLAS `AML.T0053` plugin compromise) and
`auditing-mcp-servers-for-tool-poisoning` (ATLAS `AML.T0010` supply-chain,
OWASP `MCP03:2025`).

## Premise verification (FM-2 — verified before authoring)
| Referenced artifact | Verified? | File path |
|---|---|---|
| Existing tool-scope rule-pack | yes | `rule_packs/observation/rp_tool_scope/` (fires TOOL-SCOPE-VIOLATION findings) |
| Tool-scope demo evidence | yes | `scripts/demo_azure_vertex_e2e.py` (surfaces `TOOL-SCOPE-VIOLATION-1`, out-of-scope invocations) |
| Read-only / no-write posture | yes | CLAUDE.md Non-Negotiables #3 and #6 |
| Agentic threat definitions | yes | cloned skills above |

## Goal
Assess — without building — whether and how SARO could extend its existing
tool-scope evidence (`rp_tool_scope`) to cover **agentic AI tool-invocation and
MCP tool-poisoning** signals *from customer-owned logs*, and produce a
go/no-go recommendation that respects the read-only, evidence-only posture.
The question is deliberately framed as "what evidence can we surface from logs the
customer already exports?" — never "should SARO intercept tool calls?" (it must not).

## Acceptance Criteria (Given/When/Then)
- AC-1: Given the agentic/MCP threat model, When assessed, Then the spike
  documents which signals (tool allowlist violations, argument-shape anomalies,
  post-approval tool-description drift / "rug pull") are *observable from exported
  logs* vs. which require inline interception (out of posture).
- AC-2: Given SARO's existing `rp_tool_scope` pack, When compared, Then the doc
  states the delta between what it already detects and the agentic threat set.
- AC-3: Given the posture constraints, When concluding, Then the recommendation is
  an explicit build / defer / reject per candidate signal, each tagged with its
  posture impact (Non-Negotiables #1/#3/#6).
- AC-4: Given the output, When filed, Then it uses SPECIFIED/DRAFTED vocabulary and
  cites no phantom implementation (FM-1/FM-3).

## Edge Cases
- A signal that is observable but only via a *write-back* or live hook → classified
  reject-on-posture, with the reason recorded (not silently dropped).
- Overlap with STORY-AISEC-002 ATLAS axis (AML.T0053) — cross-reference, don't
  duplicate the crosswalk.

## Out of Scope
- Any implementation, endpoint, or rule-pack change (this is a spike).
- Anything requiring SARO to sit inline in a tool-call path or write to client
  systems — barred by posture and not up for reconsideration here.

## Non-Functional Requirements
- Decision doc only; no code, no gates triggered beyond doc review.

## Benefits
- **Prevents wasted build:** a small assessment now stops the team from
  half-building an MCP/agentic connector that later collides with the read-only
  posture — the exact "unverified premise / phantom work" failure class the repo
  guards against.
- **Roadmap clarity:** produces a defensible build/defer/reject list tied to
  posture, so agentic-AI demand (a fast-growing buyer concern) gets a crisp answer
  instead of scope creep.
- **Leverages what exists:** frames the opportunity as extending the proven
  `rp_tool_scope` evidence pack, maximizing reuse over net-new surface.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
