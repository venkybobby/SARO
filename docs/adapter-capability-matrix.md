# SARO Adapter Capability Matrix

> **Generated** by `scripts/generate_capability_matrix.py` from the adapters' own parsing behaviour and the STORY-361 conformance suite. Do not edit by hand — CI verifies this file matches the code.

This page states what SARO can observe from each provider's logs, including what it **cannot**. SARO produces risk scores, TRACE evidence, and remediation guidance for human review; it does not issue verdicts.

## Ingestion

| | Bedrock | Azure OpenAI | Vertex AI |
|---|---|---|---|
| Source | Bedrock model-invocation logs | Diagnostic Settings `RequestResponse` export | Cloud Logging sink (Cloud Audit Logs) |
| Storage | Customer-owned S3 | Customer-owned blob/storage | Customer-owned GCS |
| Trigger mode | Mirror-async (batch pull) | Mirror-async (batch pull) | Mirror-async (batch pull) |
| Live / inline interception | ❌ not offered | ❌ not offered | ❌ not offered |
| Access posture | Read-only, cross-account role | Read-only export read | Read-only export read |

## Field coverage (from each provider's standard log schema)

| Normalized field | Bedrock | Azure OpenAI | Vertex AI |
|---|---|---|---|
| Invocation id | ✅ | ✅ | ✅ |
| Timestamp | ✅ | ✅ | ✅ |
| Operation / method | ✅ | ✅ | ✅ |
| Model identity | ✅ | ✅ | ✅ |
| Region | ✅ | ✅ | ✅ |
| Input token count | ✅ | ❌ | ❌ |
| Output token count | ✅ | ❌ | ❌ |
| Stop reason | ✅ | ❌ | ❌ |
| Truncation detectable | ✅ | ❌ | ❌ |
| Error / failure status | ✅ | ✅ | ✅ |
| Tool / function calls | ✅ | ❌ | ❌ |

**Legend:** ✅ present in the provider's standard logs · ◐ varies by configuration or deployment shape · ❌ not emitted by the provider — SARO cannot observe it from this source.

## Rule-pack coverage

| Rule pack | Bedrock | Azure OpenAI | Vertex AI |
|---|---|---|---|
| RP-OBS-COMPLETE@1.0.0 | ✅ full | ◐ partial | ◐ partial |
| RP-TOOL-SCOPE@1.0.0 | ✅ full | ◐ conditional | ◐ conditional |

RP-OBS-COMPLETE evaluates on every adapter; **partial** means some of its checks cannot fire because the provider does not emit the underlying signal (see limitations below).

## Limitations — what SARO does NOT support today

- **Azure OpenAI — incomplete_observation** (Not supported): Azure OpenAI RequestResponse diagnostic logs do not report a stop reason, so a truncated generation is indistinguishable from a complete one. Truncation cannot be observed from this source.
- **Azure OpenAI — tool_scope_violation** (Conditional): Requires an ENRICHED export: Azure's standard RequestResponse schema carries no tool/function data, so tool-scope evaluation works only if the customer's export adds properties.tools / .toolCalls (e.g. a gateway log in the same envelope). On stock Azure diagnostic logs this scenario is unobservable.
- **Vertex AI — incomplete_observation** (Not supported): Vertex Cloud Audit Logs record that an invocation occurred, not how generation terminated. No stop reason or token accounting is emitted, so truncation is not observable from this source.
- **Vertex AI — tool_scope_violation** (Conditional): Requires an ENRICHED export: Vertex Cloud Audit Logs carry no tool/function data, so tool-scope evaluation works only if the customer's sink adds tool metadata in LogEntry.labels. Note SARO will NOT read protoPayload.request/.response to recover it — those may contain prompt/completion content (INV-2).
- **Azure OpenAI — fields not emitted by the provider:** Input token count, Output token count, Stop reason, Truncation detectable, Tool / function calls. SARO reports these as unavailable rather than inferring them.
- **Vertex AI — fields not emitted by the provider:** Input token count, Output token count, Stop reason, Truncation detectable, Tool / function calls. SARO reports these as unavailable rather than inferring them.
- **Azure OpenAI — Token counts:** Some Azure OpenAI configurations emit promptTokens/completionTokens and SARO will use them when present, but they are not part of the guaranteed RequestResponse schema — so volume-based evidence cannot be assumed for an Azure deployment without checking the export.
- **Vertex AI — Model identity:** Resolvable for publisher models (…/publishers/google/models/X). For models served behind a customer ENDPOINT the audit log names only the endpoint id, and which model sits behind it is not in the log — SARO reports model identity as missing rather than substituting the endpoint id, which would make a model-allowlist rule meaningless.

### Reading a blank result correctly

Where a signal is not emitted, the corresponding rule produces **no findings** — because there is nothing to evaluate, **not** because the deployment was found free of issues. SARO marks these as unavailable in the record so a blank result is never mistaken for a clean one.

## Adding another provider

See `docs/adapter-design.md` §5 for the bar a new adapter must pass before it appears on this page.

