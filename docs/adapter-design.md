# Observation Adapter Design

**Owner:** Jordan Lee (Backend/Infra) · **Contract:** `adapters/contract.py`
· **Contract version:** 1.0.0 · Stories: STORY-358 (contract), 359 (Azure),
360 (Vertex), 361 (conformance), 362 (capability matrix).

> **Buyer-facing summary:** [`docs/adapter-capability-matrix.md`](adapter-capability-matrix.md)
> — generated from the adapters' behaviour and the conformance suite. This file
> is the engineering detail behind it.

---

## 1. What an adapter is

An observation adapter turns one provider's invocation logs into
`NormalizedInvocationRecord`s. That is its entire job. It does **not** score,
does not call the provider's API at evaluation time, and does not write to the
customer's systems (INV-6 read-only posture).

```
customer-owned log export ──► adapter.parse ──► NormalizedInvocationRecord ──► rule-pack engine ──► attestation
        (S3 / blob / GCS)         (per provider)        (one schema)              (provider-agnostic)
```

The value of the seam: rules are written once against normalized field names.
Adding adapter #4 changes no rule and no engine code.

## 2. The contract

`NormalizedInvocationRecord` (Pydantic, frozen). Full field docs live in the
module docstring; the shape:

| Group | Fields |
|---|---|
| Contract identity | `contract_version` |
| Provenance | `provenance.adapter_id`, `.source_uri` (pointer), `.cursor` (resumable watermark), `.record_hash` (SHA-256 of the raw record) |
| Tenancy | `tenant_id` — **operator-supplied binding, never read from the log** |
| Invocation | `request_id`, `model_id`, `operation`, `region`, `timestamp` |
| Metadata | `input_token_count`, `output_token_count`, `stop_reason`, `truncated`, `error_code` |
| Agentic | `tools[]` → `ToolInvocation{name, offered, invoked}` |
| Availability | `field_availability{field → PRESENT \| field_unavailable \| field_missing}` |

### INV-2 is structural, not procedural

The record has **no field capable of holding message content** — no prompt, no
completion, no tool arguments, no tool results. Tool *names* are metadata and
are carried; tool *arguments* are content and are not. This is enforced by
`tests/test_story358_adapter_contract.py::test_contract_has_no_content_bearing_field`,
which fails if anyone adds a content-bearing field. A function that takes a
`NormalizedInvocationRecord` cannot read a body by mistake, because the body was
never put in the object.

### Availability: absent ≠ unavailable

Three distinct facts, never collapsed into `None`:

- `PRESENT` — provider emitted it, value populated.
- `field_unavailable` — **this provider never emits it.** Structural. Not a
  data-quality problem; a coverage limitation to state honestly in the
  capability matrix (STORY-362).
- `field_missing` — provider normally emits it, this record didn't. A
  data-quality signal RP-OBS-COMPLETE can act on.

An adapter that returns silent `None` for a field its provider does not support
is lying by omission, and the capability matrix built from these tables would
inherit the lie.

## 3. Field-mapping tables

### 3.1 Bedrock (`bedrock-invocation-log`, adapter #1)

Source: Bedrock model-invocation logging (S3 delivery). Lift:
`adapters/contract.from_bedrock_envelope`.

| Bedrock field | Normalized field | Notes |
|---|---|---|
| `requestId` | `request_id` | |
| `modelId` | `model_id` | feeds the envelope model-allowlist rule (STORY-411) |
| `operation` | `operation` | `Converse` / `ConverseStream` / `InvokeModel*` |
| `region` | `region` | `field_missing` when blank |
| `timestamp` | `timestamp` | parsed to tz-aware UTC |
| `input.inputTokenCount` | `input_token_count` | `field_missing` if absent |
| `output.outputTokenCount` | `output_token_count` | `field_missing` if absent |
| `output…stopReason` / `stop_reason` | `stop_reason`, `truncated` | `max_tokens` ⇒ `truncated=True` |
| `toolConfig.tools[].toolSpec.name` / `tools[].name` | `tools[].name` + `offered=True` | names only |
| `content[].toolUse` / `type=="tool_use"` | `tools[].invoked=True` | names only |
| (caller-supplied position) | `provenance.cursor` | e.g. `s3:key:L42` |
| (operator config) | `tenant_id` | **not** from the log |

Bodies (`inputBodyJson` / `inputBodyS3Path`) are read **only** on the audit
branch, guarded by a deny-by-default bucket allowlist (FND-1) and size caps
(FND-2). They never reach the normalized record.

### 3.2 Azure OpenAI (`azure-openai-diagnostic-log`, adapter #2)

Source: Azure Diagnostic Settings, category `RequestResponse`, exported to
customer-owned storage. Parser: `adapters/azure_openai/parse.py`.

| Azure field | Normalized field | Rule-pack fields consumed | Notes |
|---|---|---|---|
| `correlationId` | `request_id` | OBS-REQUIRED-FIELDS-1 | falls back to `properties.requestId`; absence ⇒ record rejected |
| `operationName` | `operation` | OBS-REQUIRED-FIELDS-1 | e.g. `ChatCompletions_Create` |
| `time` | `timestamp` | OBS-REQUIRED-FIELDS-1 | 7 fractional digits, truncated to 6 for parsing |
| `properties.modelName` (+`modelVersion`) | `model_id` | OBS-REQUIRED-FIELDS-1, envelope allowlist | `name:version`; falls back to `modelDeploymentName`, else `MISSING` |
| `location` | `region` | — | `MISSING` when absent |
| `properties.promptTokens` | `input_token_count` | OBS-TOKEN-COUNTS-1 | see availability note below |
| `properties.completionTokens` | `output_token_count` | OBS-TOKEN-COUNTS-1 | see availability note below |
| `resultType` / `resultSignature` | `error_code` | OBS-ERROR-INVOCATION-1 | non-success type, or non-2xx signature |
| `properties.tools` / `toolDefinitions` / `functions` * | `tools[].offered` | TOOL-SCOPE-OFFERED-1, TOOL-POLICY-ABSENT-1 | *not in the standard schema — see below |
| `properties.toolCalls` / `functionCalls` * | `tools[].invoked` | TOOL-SCOPE-VIOLATION-1 | *not in the standard schema — see below |
| (object key + line number) | `provenance.cursor` | — | e.g. `2026/07/01/log.ndjson:L42` |
| (operator config) | `tenant_id` | — | **never** from the log — see below |
| — | `stop_reason`, `truncated` | OBS-TRUNCATED-OUTPUT-1 | **`UNAVAILABLE`** — Azure does not report why generation stopped |

**Availability semantics for token counts.** No usage fields at all ⇒
`UNAVAILABLE` (this deployment's schema does not report usage). One usage field
present and the other absent ⇒ `MISSING` (Azure reported usage here and this
record is incomplete). Conflating the two would make a provider limitation look
like a customer data-quality problem, or vice versa.

**\* Tool data is not part of the Azure `RequestResponse` schema.** The keys
above are parsed when a customer's export carries them (an enriched export or a
gateway log shipped in the same envelope). By default they are absent, and the
adapter marks `tools` as `UNAVAILABLE`.

> **Consequence that must never be misreported:** on standard Azure records,
> RP-TOOL-SCOPE produces **zero findings because there is no data to evaluate** —
> which is *not* the same as a clean tool-scope result. This is pinned by
> `tests/test_story359_azure_adapter.py::test_standard_azure_records_yield_no_tool_findings_because_data_is_absent`
> and must appear as a "not supported" row in the capability matrix (STORY-362),
> never as coverage.

**Why this source is INV-2-safe by nature:** Azure `RequestResponse` diagnostic
logs do not contain prompt or completion content. There is no body to fetch and
no allowlist to enforce (contrast Bedrock's S3-externalized bodies).

**Tenant isolation (INV-3), two independent controls** — `adapters/azure_openai/source.py`:
1. A reader is bound to one tenant's `container` + `prefix`, rejects traversal,
   and matches prefixes on **segment boundaries** (`tenant-1` must not read
   `tenant-10`).
2. Tenancy is set from operator config only. Azure records carry
   subscription GUIDs, `properties.objectId`, and sometimes an Entra tenant id;
   none may influence SARO's tenancy.

**Corpus:** `tests/fixtures/azure/corpus.ndjson` — 54 deterministic records
(`scripts/azure_corpus_builder.py`, `--check` verifies byte-identity in CI).
### 3.3 Vertex AI (`vertex-ai-audit-log`, adapter #3)

Source: Cloud Logging sink (Cloud Audit Logs for `aiplatform.googleapis.com`)
exported to a customer-owned GCS bucket. Parser: `adapters/vertex_ai/parse.py`.

| Vertex / Cloud Logging field | Normalized field | Rule-pack fields consumed | Notes |
|---|---|---|---|
| `insertId` | `request_id` | OBS-REQUIRED-FIELDS-1 | falls back to `operation.id`; absence ⇒ record rejected |
| `protoPayload.methodName` | `operation` | OBS-REQUIRED-FIELDS-1 | shortened to `PredictionService.GenerateContent` |
| `timestamp` | `timestamp` | OBS-REQUIRED-FIELDS-1 | 9 fractional digits (ns), truncated to µs |
| `protoPayload.resourceName` | `model_id` | OBS-REQUIRED-FIELDS-1, envelope allowlist | `…/publishers/google/models/X` → `X`; **endpoints → `MISSING`** (see below) |
| `resource.labels.location` | `region` | — | `MISSING` when absent |
| `protoPayload.status.code` | `error_code` | OBS-ERROR-INVOCATION-1 | `google.rpc.Code` name (`PERMISSION_DENIED`); `0` = success |
| `labels.tools` / `toolCalls` * | `tools[]` | TOOL-SCOPE-* | *not in the audit schema — enriched exports only |
| (object key + line number) | `provenance.cursor` | — | e.g. `2026/07/01/log.ndjson:L42` |
| (operator config) | `tenant_id` | — | **never** from the log |
| — | `input_token_count`, `output_token_count` | OBS-TOKEN-COUNTS-1 | **`UNAVAILABLE`** — audit logs never report usage |
| — | `stop_reason`, `truncated` | OBS-TRUNCATED-OUTPUT-1 | **`UNAVAILABLE`** |
| **`protoPayload.request` / `.response`** | **— never read —** | — | **may contain prompt/completion. See below.** |

**Endpoint deployments lose model identity.** A publisher-model call names the
model; a call to a customer endpoint names only `endpoints/{id}`, and which
model sits behind it is not in the log. The adapter returns `MISSING` rather
than passing the endpoint id off as a model id — doing that would leave a
model-allowlist rule silently evaluating an identifier that is not a model,
while appearing to work.

> **INV-2 hazard unique to this adapter.** Vertex **Data Access** audit logs can
> include `protoPayload.request` and `protoPayload.response`; for generative
> calls those hold the actual prompt and completion — real PHI. Azure's
> diagnostic logs contain no payload, so INV-2 held there by luck of the schema.
> Here the content may genuinely be present in the source, so the parser is
> **body-blind by construction**: no code path indexes those keys. Proven under
> the hostile case by
> `tests/test_story360_vertex_adapter.py::test_phi_payload_present_in_source_never_reaches_the_record`
> and `::test_phi_never_reaches_rule_findings_either`, with PHI-bearing entries
> planted in the corpus so the guard cannot be vacuous.

**Tool data** is absent from the audit schema, so RP-TOOL-SCOPE produces zero
findings on standard Vertex entries — a coverage gap, **not** a clean tool-scope
result. Same constraint and same treatment as Azure (§3.2).

**Corpus:** `tests/fixtures/vertex/corpus.ndjson` — 56 deterministic records
(`scripts/vertex_corpus_builder.py`, `--check` verifies byte-identity in CI).

## 4. How to add adapter #N

1. **Read the provider's log schema** and write the field-mapping table into
   §3 *first* — including the rows you cannot fill. Those become
   `mark_unavailable(...)` entries and honest "not supported" rows in the
   capability matrix (STORY-362).
2. **Create `adapters/<provider>/`** with a pure `parse.py` (no I/O, no SDK
   import) and a `source.py` for reading the customer-owned export. Mirror the
   Bedrock split: parsing is unit-testable without cloud credentials.
3. **Emit `NormalizedInvocationRecord`** — never a provider-shaped dict passed
   downstream. Record structural gaps via `mark_unavailable`, per-record gaps
   via `mark_missing`.
4. **Bind tenancy from operator config**, never from log content. A log field
   claiming a tenant id is attacker-controllable input (INV-3).
5. **Commit a deterministic synthetic corpus** (≥50 records) covering the shared
   scenarios: happy path, missing fields, malformed record, tool-scope
   violation, incomplete observation.
6. **Join the conformance suite** (STORY-361) — see §5 below. Passing it is what
   makes "supports \<provider\>" a tested claim rather than a marketing one.
7. **Prove tenant isolation**: two tenants' sources cannot cross-read (INV-3).
8. **Update** §3, the capability matrix, and `AUDITED`/`DATA_PLANE`
   classification if you add routes (STORY-366).

### Non-negotiables for any adapter

- Zero external model calls (INV-1) — adapters parse logs, they do not invoke models.
- Body-free normalized output (INV-2).
- Read-only against customer storage (INV-6); customer-owned buckets only.
- Deterministic parsing: same input bytes ⇒ same record, so attestations reproduce.

---

## 5. The conformance bar — what adapter #4 must pass (STORY-361)

An adapter is not "supported" anywhere in SARO's documentation until it is in
`tests/conformance/providers.py::REGISTERED_ADAPTERS` and passing.

### Register it

Implement a provider class with `adapter_id`, `display_name`, and
`build(scenario) -> Outcome`, then add an instance to `REGISTERED_ADAPTERS`.
Build every scenario **through your real parser** — a hand-constructed
`NormalizedInvocationRecord` tests the contract, which is already covered, and
proves nothing about your parsing.

### Answer all six scenarios

| Scenario | What it asserts |
|---|---|
| `happy_path` | Well-formed record normalizes; identity + provenance populated |
| `missing_fields` | Absent fields are classified — **no silent nulls** |
| `malformed_record` | Uninterpretable input **raises**; never a half-populated record |
| `tool_scope_violation` | An out-of-scope tool call is caught by RP-TOOL-SCOPE |
| `incomplete_observation` | A truncated/partial observation is detectable |
| `tenancy_spoofing` | A record claiming another tenant **cannot** override the operator binding (INV-3) |

### The three honest answers

A provider must return an outcome for every scenario — silence is not an option
the API offers. Each outcome is one of:

- `Outcome.supported(record)` — works on the provider's **standard** logs.
- `Outcome.conditional(record, reason=…)` — works only under a stated
  precondition (e.g. an enriched export). Renders as `◐`, never `✅`, because a
  tick would tell a buyer it works on the logs they already have.
- `Outcome.not_supported(reason=…)` — the provider's logs cannot express it.
  Renders as `⚠️ n/a` and is listed as a coverage gap.

`reason` is mandatory (≥20 chars) for the latter two and is asserted, so a gap
cannot be waved through with an empty string. Current gaps and conditionals are
**pinned** by `test_known_gaps_are_exactly_the_expected_ones` and
`test_known_conditionals_are_exactly_the_expected_ones`: introducing a new one
is a deliberate, reviewed change rather than a quiet regression.

### Also required

- A deterministic synthetic corpus (≥50 records) with a `--check` mode wired
  into CI, since attestations and the STORY-378 harness need byte-identical inputs.
- Universal invariants hold on every record: contract stays body-free, provenance
  carries `adapter_id` + `cursor`, timestamps are timezone-aware.
- Records are reproducible: the same input twice yields an identical record.

### Artifacts

`.github/workflows/conformance.yml` runs the suite on any change to
`adapters/**` or `rule_packs/observation/**`, publishes
`quality/conformance/adapter-conformance.{json,md}`, and prints the matrix into
the job summary. That matrix is the honest source for the buyer-facing
capability matrix (STORY-362) — generated, never hand-authored.
