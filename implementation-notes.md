# STORY-AISEC-004 — SPIKE: agentic/MCP tool-invocation evidence coverage
Stage: trivial

Spike/assessment — the deliverable is a DECISION DOCUMENT, not code (the story
is SPECIFIED-only by design). Code gates (pytest/ratchet) do not apply; the
output is the build/defer/reject assessment appended to the story file.

## Lifecycle
- [x] discover   (rp_tool_scope current coverage + agentic/MCP threat set mapped)
- [ ] shape      (n/a — no code; assessment is the artifact)
- [ ] preview    (n/a)
- [ ] plan       (n/a)
- [x] build      (assessment authored)
- [ ] verify     (n/a — doc)
- [ ] sell       (n/a)

## DISCOVER findings
- `rule_packs/observation/rp_tool_scope/1.0.0/pack.yaml` ALREADY detects, from
  envelope tool NAMES only (INV-2, no arguments/results): TOOL-SCOPE-VIOLATION-1
  (invoked tool outside allowed_tools), TOOL-SCOPE-OFFERED-1 (out-of-scope tool
  offered), TOOL-POLICY-ABSENT-1 (tools used, no declared policy).
- Agentic/MCP threat set (cloned skills securing-agentic-ai-tool-invocation
  [ATLAS AML.T0053], auditing-mcp-servers-for-tool-poisoning [AML.T0010,
  OWASP MCP03]): tool poisoning, tool shadowing, rug pulls, toxic flows,
  argument anomalies, SSRF, unauth MCP exposure, excessive agency.
- Posture non-negotiables that bound the answer: #1 no external model in core
  scoring, #3 never writes to client systems, #6 read-only connectors.

## Decision Log
- Deliverable form? → decision doc appended to the story file (spike output), not code
- Framing? → "what evidence from logs the customer already exports", never "should SARO intercept tool calls" (it must not)

## Deviations
- Branch stacked on story/STORY-AISEC-003 (pack chain; predecessors unmerged due
  to CI billing block). Doc-only, so no code conflict risk.
