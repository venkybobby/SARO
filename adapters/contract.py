"""Observation adapter contract (STORY-358).

**The one schema the rule-pack engine consumes.** Every observation adapter
(Bedrock #1, Azure OpenAI #2, Vertex #3, …) parses its provider's log format
into a :class:`NormalizedInvocationRecord`. Rules are written against these
field names, never against a provider's wire format — so adding an adapter
does not touch the engine, and a rule cannot accidentally depend on a
Bedrock-only key.

INV-2 (zero-PHI retention) is expressed in the type system, not in a comment:
this record has **no field that can hold message content**. Prompts, completions,
tool arguments, and tool results have no home here. What it carries is the
*envelope*: identifiers, timestamps, counts, tool NAMES, and provenance. A
function that receives a ``NormalizedInvocationRecord`` cannot read a body even
by mistake, because the body never entered the object.

Relationship to ``adapters/bedrock/records.Envelope``: ``Envelope`` remains the
Bedrock adapter's internal parse product (frozen dataclass, provider-shaped).
:func:`from_bedrock_envelope` lifts it into this contract. Existing attestation
hashes are computed on the audit path and are unaffected by this addition — the
contract is additive, so no hash-format bump (STORY-358 AC-3).

Field availability
------------------
Providers differ. A field a provider does not emit must be recorded as
explicitly unavailable, never silently ``None``: an absent token count and a
provider that never reports token counts are different facts, and an evidence
system must not conflate them. Adapters declare the difference via
``field_availability`` — see :meth:`NormalizedInvocationRecord.mark_unavailable`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# Bump only for a breaking change to the field set. Adapters record the version
# they emitted, so a stored record stays interpretable later.
CONTRACT_VERSION = "1.0.0"


class FieldAvailability(str, Enum):
    """Why a normalized field has no value.

    ``PRESENT``      — the provider emitted it and it is populated.
    ``UNAVAILABLE``  — this provider never emits it (structural gap).
    ``MISSING``      — the provider normally emits it but this record lacked it
                       (data-quality gap — worth flagging in a rule).
    """

    PRESENT = "present"
    UNAVAILABLE = "field_unavailable"
    MISSING = "field_missing"


class SourceProvenance(BaseModel):
    """Where this record came from — pointer + integrity hash, never content."""

    model_config = ConfigDict(frozen=True)

    adapter_id: str = Field(description="Adapter family, e.g. 'bedrock-invocation-log'")
    source_uri: Optional[str] = Field(
        default=None,
        description="Pointer to the source log object (s3://…, blob URL, gs://…). "
        "A POINTER only — SARO does not copy the object's content here.",
    )
    cursor: str = Field(
        description="Monotonic stream position within the source (resumable watermark)."
    )
    record_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 of the raw source record, for tamper-evidence. The "
        "hash is one-way: it proves integrity without retaining the record.",
    )


class ToolInvocation(BaseModel):
    """A tool/function the model was offered or chose to call.

    NAME AND OUTCOME ONLY. Tool arguments and results are message content and
    are deliberately absent — RP-TOOL-SCOPE evaluates *which* tool was called
    against the tenant's allowed set, which never requires the arguments.

    The optional ``description`` is the tool's *advertised* metadata (what the
    tool claims to do, loaded into the model's context) — not per-invocation
    message content, so it does not breach INV-2. It exists so RP-TOOL-POISONING
    (STORY-AISEC-006) can scan it for hidden injection directives (MCP tool
    poisoning, ATLAS AML.T0010). Optional and default-None: adapters populate it
    only when the source log carries it.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    offered: bool = Field(
        default=False, description="Present in the request's tool configuration."
    )
    invoked: bool = Field(
        default=False, description="The model emitted a call to this tool."
    )
    description: str | None = Field(
        default=None,
        description="The tool's advertised description text (metadata), if the "
        "source log carries it. Scanned for tool-poisoning by RP-TOOL-POISONING.",
    )


class NormalizedInvocationRecord(BaseModel):
    """One model invocation, normalized across providers. Body-free by design."""

    model_config = ConfigDict(frozen=True)

    # ── Contract + source identity ──────────────────────────────────────────
    contract_version: str = Field(default=CONTRACT_VERSION)
    provenance: SourceProvenance

    # ── Tenancy (operator-supplied binding, never read from the log) ────────
    tenant_id: uuid.UUID

    # ── Invocation identity ─────────────────────────────────────────────────
    request_id: str
    model_id: str
    operation: str = Field(
        description="Provider operation, normalized where equivalent "
        "(e.g. Bedrock 'Converse', Azure 'ChatCompletions_Create')."
    )
    region: Optional[str] = None
    timestamp: datetime = Field(description="Invocation time, timezone-aware UTC.")

    # ── Request/response metadata (counts and flags — never content) ────────
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None
    stop_reason: Optional[str] = None
    truncated: bool = Field(
        default=False,
        description="Output was cut short (e.g. max_tokens) — the observation is "
        "incomplete, which RP-OBS-COMPLETE cares about.",
    )
    error_code: Optional[str] = Field(
        default=None, description="Provider error/status code, if the call failed."
    )

    # ── Agentic surface ─────────────────────────────────────────────────────
    tools: tuple[ToolInvocation, ...] = Field(default=())

    # ── Field availability ──────────────────────────────────────────────────
    field_availability: dict[str, FieldAvailability] = Field(
        default_factory=dict,
        description="Per-field explanation for absent values. Fields not listed "
        "are PRESENT. Adapters MUST record structural gaps here (AC-3).",
    )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def availability(self, field_name: str) -> FieldAvailability:
        """Availability of *field_name* — PRESENT unless an adapter said otherwise."""
        return self.field_availability.get(field_name, FieldAvailability.PRESENT)

    @property
    def invoked_tools(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.tools if t.invoked)

    @property
    def offered_tools(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.tools if t.offered)

    @staticmethod
    def mark_unavailable(*field_names: str) -> dict[str, FieldAvailability]:
        """Build a ``field_availability`` map marking fields structurally absent."""
        return {name: FieldAvailability.UNAVAILABLE for name in field_names}

    @staticmethod
    def mark_missing(*field_names: str) -> dict[str, FieldAvailability]:
        """Build a map marking fields the provider should have emitted but didn't."""
        return {name: FieldAvailability.MISSING for name in field_names}


# ── Bedrock lift (adapter #1 conforms to the contract; it does not fork it) ──


def from_bedrock_envelope(
    envelope: Any,
    *,
    tenant_id: uuid.UUID,
    adapter_id: str,
    source_uri: Optional[str] = None,
    record_hash: Optional[str] = None,
    tools: tuple[ToolInvocation, ...] = (),
    stop_reason: Optional[str] = None,
    truncated: bool = False,
) -> NormalizedInvocationRecord:
    """Lift a Bedrock ``Envelope`` into the normalized contract.

    Kept here rather than in the Bedrock package so the contract owns its own
    conversions and every adapter's lift sits side by side for comparison.

    Token counts absent from a Bedrock envelope are ``MISSING`` (Bedrock does
    emit them; this record simply lacked them), not ``UNAVAILABLE``.
    """
    availability: dict[str, FieldAvailability] = {}
    if envelope.input_token_count is None:
        availability["input_token_count"] = FieldAvailability.MISSING
    if envelope.output_token_count is None:
        availability["output_token_count"] = FieldAvailability.MISSING
    if not envelope.region:
        availability["region"] = FieldAvailability.MISSING

    return NormalizedInvocationRecord(
        provenance=SourceProvenance(
            adapter_id=adapter_id,
            source_uri=source_uri,
            cursor=envelope.cursor,
            record_hash=record_hash,
        ),
        tenant_id=tenant_id,
        request_id=envelope.request_id,
        model_id=envelope.model_id,
        operation=envelope.operation,
        region=envelope.region or None,
        timestamp=envelope.timestamp,
        input_token_count=envelope.input_token_count,
        output_token_count=envelope.output_token_count,
        stop_reason=stop_reason,
        truncated=truncated,
        tools=tools,
        field_availability=availability,
    )
