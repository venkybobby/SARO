# Observation Adapter Design

**Owner:** Jordan Lee (Backend/Infra) · **Contract:** `adapters/contract.py`
· **Contract version:** 1.0.0 · Stories: STORY-358 (contract), 359 (Azure),
360 (Vertex), 361 (conformance), 362 (capability matrix).

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

### 3.2 Azure OpenAI — see STORY-359 (pending)
### 3.3 Vertex AI — see STORY-360 (pending)

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
6. **Pass the conformance suite** (STORY-361) — it instantiates the shared
   scenario set against your adapter. Passing it is what makes "supports
   <provider>" a tested claim rather than a marketing one.
7. **Prove tenant isolation**: two tenants' sources cannot cross-read (INV-3).
8. **Update** §3, the capability matrix, and `AUDITED`/`DATA_PLANE`
   classification if you add routes (STORY-366).

### Non-negotiables for any adapter

- Zero external model calls (INV-1) — adapters parse logs, they do not invoke models.
- Body-free normalized output (INV-2).
- Read-only against customer storage (INV-6); customer-owned buckets only.
- Deterministic parsing: same input bytes ⇒ same record, so attestations reproduce.
