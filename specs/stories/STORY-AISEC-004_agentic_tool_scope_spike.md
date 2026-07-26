# STORY-AISEC-004: SPIKE — agentic / MCP tool-invocation evidence coverage assessment

**Status:** DRAFTED (assessment authored — spike output below; no code by design)
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

---

# Assessment (spike output — 2026-07-26)

> Deliverable of this spike. No code was written. Framing (per posture): *what
> evidence can SARO surface from logs the customer already exports?* — never
> "should SARO intercept tool calls" (Non-Negotiables #3/#6 forbid it).

## Baseline — what `rp_tool_scope` already covers (AC-2 delta)

`rule_packs/observation/rp_tool_scope/1.0.0/pack.yaml` already evaluates
`NormalizedInvocationRecord` envelope **tool names** (never arguments/results,
INV-2) and fires:

| Rule | Detects | ATLAS |
|---|---|---|
| TOOL-SCOPE-VIOLATION-1 | an invoked tool outside the tenant's `allowed_tools` | AML.T0053 |
| TOOL-SCOPE-OFFERED-1 | an out-of-scope tool *offered* to the model (capability leak) | AML.T0053 |
| TOOL-POLICY-ABSENT-1 | tools used with no declared tool policy | — |

So the **core agentic tool-misuse / excessive-agency signal is already shipped.**
The delta below is what agentic/MCP threats add *beyond* this.

## Candidate signals → observability → build/defer/reject (AC-1, AC-3)

| Candidate signal (threat) | Observable from exported logs? | Recommendation | Posture impact |
|---|---|---|---|
| **MCP tool-poisoning** — hidden instructions in a tool's *description* text (AML.T0010 / OWASP MCP03) | Yes **iff** the export includes tool-description text | **BUILD (top pick)** — route exported tool descriptions through the **AISEC-001 injection detector** offline. Descriptions are untrusted text; poisoning *is* indirect prompt injection via the supply chain. Reuses shipped code, evidence-only. | Safe — deterministic, no external model (#1), read-only (#6). Needs a contract field for tool-description text. |
| **Rug pull** — a tool's description/behavior changes after approval | Yes **iff** the contract carries a per-tool description hash across records | **DEFER** — needs an envelope contract extension (tool-description hash + first-seen tracking); then a drift rule alongside `rp_tool_scope`. | Safe once the field exists; envelope-only. |
| **Tool shadowing** — a malicious tool overrides a trusted one | Partially — a shadowing tool usually surfaces as a new/out-of-scope tool name | **DEFER (mostly covered)** — largely caught by TOOL-SCOPE-OFFERED-1; a name-collision rule is a thin add. | Safe — envelope names only. |
| **Excessive agency** — abnormal volume of high-impact tool calls | Yes — envelope tool names + counts | **DEFER** — a per-tenant sensitive-tool-frequency rule; needs a tenant "sensitive tool" list (config, like `allowed_tools`). | Safe — envelope-only, tenant config not a SARO opinion. |
| **Argument-shape / injection in tool *arguments*** | **No** — arguments are message *content*, excluded from the contract (INV-2) | **REJECT-on-posture** for the observation path. Only reachable via the body-bearing core-scan path, not log-observation. | Would require body access in the observation pipeline — breaks INV-2. |
| **SSRF in MCP tools · unauthenticated MCP server exposure** | **No** — these are runtime/infra properties of the MCP server, not in AI-invocation logs | **REJECT** — out of SARO's domain entirely (infra/network scanning, not AI-output evidence). | Not an AI-audit signal; wrong product surface. |
| **HITL-approval / identity-binding / scoped-credential enforcement** | Only whether an approval *event* was logged — never enforcement itself | **REJECT/DEFER** — SARO can *evidence* that a logged approval occurred, but must never enforce or block. | Enforcement = writing/controlling (#3/#6). Evidence-of-approval-logged is a possible DEFER. |
| **Blocking / preventing a tool call** | — | **REJECT (hard)** | Non-Negotiable #3/#6 — SARO never writes to or controls client systems. |

## Recommendation

1. **Highest-value, posture-safe next step: MCP tool-poisoning evidence via the
   AISEC-001 detector.** If a tenant exports MCP tool descriptions, scan them
   offline for injection indicators. It reuses shipped code, stays deterministic
   and read-only, and maps to a real ATLAS technique (AML.T0010 / AML.T0051.001).
   Gate: needs an envelope-contract field for tool-description text — scope that
   first (its own story).
2. **Defer** rug-pull (description-hash drift) and excessive-agency-frequency
   until the contract carries the needed fields; both are then thin rules beside
   `rp_tool_scope`.
3. **Reject** argument-shape validation (breaks INV-2), SSRF/unauth-exposure
   scanning (wrong product surface), and any inline blocking/HITL enforcement
   (breaks read-only). These do not get built regardless of demand.

**Net:** the agentic tool-misuse core is already shipped in `rp_tool_scope`; the
one genuinely new, posture-safe opportunity is scanning **MCP tool-description
text** with the AISEC-001 detector — everything else is either a deferred
envelope-contract extension or a posture reject.

## Traceability
Spike — no tests. Deliverable is this assessment. AC-1..AC-4 satisfied by the
observability table (AC-1), the `rp_tool_scope` delta section (AC-2), the
build/defer/reject column with posture tags (AC-3), and DRAFTED status + no
phantom-implementation claims (AC-4).
