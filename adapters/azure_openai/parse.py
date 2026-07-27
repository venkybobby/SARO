"""Azure OpenAI diagnostic-log parsing (STORY-359).

Pure functions, no I/O, no Azure SDK import — the same split the Bedrock adapter
uses, so parsing is unit-testable without cloud credentials and the conformance
suite (STORY-361) can drive it directly.

Every absent field is classified, never silently dropped:

* ``UNAVAILABLE`` — the standard Azure ``RequestResponse`` schema has no such
  field (tool calls, stop reason). A coverage limitation, disclosed as such.
* ``MISSING``     — Azure emits it on some configurations and this record
  lacked it (token counts, model name, region). A data-quality signal.

The distinction is what keeps "RP-TOOL-SCOPE produced no findings on Azure"
from being misread as "this Azure deployment is in scope compliance".
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from adapters.azure_openai.records import (
    MAX_RECORD_CHARS,
    SUPPORTED_CATEGORY,
    AzureAdapterConfig,
    AzureCategorySkipped,
    AzureRecordError,
    AzureRecordTooLarge,
)
from adapters.contract import (
    FieldAvailability,
    NormalizedInvocationRecord,
    SourceProvenance,
    ToolInvocation,
    clamp_tool_description,
)

logger = logging.getLogger(__name__)

# Azure result signatures that indicate a successful invocation.
_SUCCESS_RESULT_TYPES = frozenset({"success", "succeeded"})

# Optional tool-data keys. NOT part of the documented Azure RequestResponse
# schema — present only when a customer enriches the export (e.g. an API-gateway
# log shipped in the same envelope). Parsed when present so those customers get
# RP-TOOL-SCOPE coverage; absent by default, which is the honest common case.
_TOOL_OFFERED_KEYS = ("tools", "toolDefinitions", "functions")
_TOOL_INVOKED_KEYS = ("toolCalls", "functionCalls")


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Azure emits ISO-8601 with 7 fractional digits and a 'Z' suffix."""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # Python accepts at most 6 fractional digits; Azure emits 7.
    if "." in text:
        head, _, tail = text.partition(".")
        digits = "".join(c for c in tail if c.isdigit())
        offset = tail[len(digits) :]
        text = f"{head}.{digits[:6]}{offset}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _record_hash(raw: dict[str, Any]) -> str:
    """SHA-256 over the canonical record — tamper-evidence without retention."""
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=True, default=str).encode()
    ).hexdigest()


def _tool_names(container: Any) -> list[str]:
    """Extract tool NAMES from a list of strings or of dicts. Names only."""
    names: list[str] = []
    if not isinstance(container, list):
        return names
    for item in container:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = item.get("name") or (item.get("function") or {}).get("name")
            if isinstance(name, str) and name:
                names.append(name)
    return names


def _tool_descriptions(container: Any) -> dict[str, str]:
    """Map offered tool NAME → advertised description (STORY-AISEC-008).

    Reads the request-side tool declaration only (metadata, INV-2 safe): the
    description sits at ``item.description`` or ``item.function.description``.
    """
    out: dict[str, str] = {}
    if not isinstance(container, list):
        return out
    for item in container:
        if not isinstance(item, dict):
            continue
        fn_raw = item.get("function")
        fn = fn_raw if isinstance(fn_raw, dict) else {}
        name = item.get("name") or fn.get("name")
        # Falsy top-level (None or "") falls through to the nested function form.
        desc = item.get("description") or fn.get("description")
        if isinstance(name, str) and name and desc is not None:
            out[name] = desc
    return out


def _extract_tools(props: dict[str, Any]) -> Optional[tuple[ToolInvocation, ...]]:
    """Return tool invocations, or None when the export carries no tool data.

    ``None`` and ``()`` mean different things and must not be conflated:
    ``None`` = the schema had no tool information at all (UNAVAILABLE);
    ``()``   = tool data was present and showed no tools (a real observation).
    """
    offered: list[str] = []
    invoked: list[str] = []
    descriptions: dict[str, str] = {}
    saw_tool_data = False

    for key in _TOOL_OFFERED_KEYS:
        if key in props:
            saw_tool_data = True
            offered.extend(_tool_names(props[key]))
            descriptions.update(_tool_descriptions(props[key]))
    for key in _TOOL_INVOKED_KEYS:
        if key in props:
            saw_tool_data = True
            invoked.extend(_tool_names(props[key]))

    if not saw_tool_data:
        return None

    invoked_set = set(invoked)
    offered_set = set(offered)
    all_names = sorted(offered_set | invoked_set)
    return tuple(
        ToolInvocation(
            name=name,
            offered=name in offered_set,
            invoked=name in invoked_set,
            description=clamp_tool_description(descriptions.get(name)),
        )
        for name in all_names
    )


def _model_id(props: dict[str, Any]) -> Optional[str]:
    """Model identity for allowlist rules.

    Prefers ``modelName`` (the actual model) over ``modelDeploymentName`` (a
    customer-chosen alias). A deployment alias like "prod-chat" says nothing
    about which model served the traffic, so using it for a model allowlist
    would make the allowlist meaningless — but it is a better fallback than
    nothing, and which one was used is recorded in ``operation`` context.
    """
    name = props.get("modelName") or props.get("ModelName")
    if isinstance(name, str) and name.strip():
        version = props.get("modelVersion") or props.get("ModelVersion")
        if isinstance(version, str) and version.strip():
            return f"{name.strip()}:{version.strip()}"
        return name.strip()
    deployment = props.get("modelDeploymentName") or props.get("ModelDeploymentName")
    if isinstance(deployment, str) and deployment.strip():
        return deployment.strip()
    return None


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_record(
    raw: Any,
    *,
    config: AzureAdapterConfig,
    cursor: str,
    source_uri: Optional[str] = None,
) -> NormalizedInvocationRecord:
    """Parse one Azure diagnostic-log record into the normalized contract.

    Raises :class:`AzureRecordError` (or a subclass) on records that cannot be
    interpreted — the caller decides whether to skip or fail the batch. A
    malformed record is never turned into a half-populated observation, because
    a fabricated record is worse than a skipped one in an evidence system.
    """
    if isinstance(raw, str):
        if len(raw) > MAX_RECORD_CHARS:
            raise AzureRecordTooLarge(
                f"record exceeds {MAX_RECORD_CHARS}-char cap ({len(raw)})"
            )
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AzureRecordError(f"record is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise AzureRecordError(
            f"record is not a JSON object (got {type(raw).__name__})"
        )

    category = raw.get("category") or raw.get("Category")
    if category and str(category) != SUPPORTED_CATEGORY:
        raise AzureCategorySkipped(
            f"category {category!r} is not {SUPPORTED_CATEGORY!r} — not interpreted"
        )

    props = raw.get("properties") or raw.get("Properties") or {}
    if not isinstance(props, dict):
        props = {}

    availability: dict[str, FieldAvailability] = {}

    # ── Identity ────────────────────────────────────────────────────────────
    request_id = (
        raw.get("correlationId") or raw.get("CorrelationId") or props.get("requestId")
    )
    if not request_id:
        raise AzureRecordError(
            "record has no correlationId — cannot identify the invocation"
        )

    operation = raw.get("operationName") or raw.get("OperationName")
    if not operation:
        raise AzureRecordError("record has no operationName")

    timestamp = _parse_timestamp(
        raw.get("time") or raw.get("Time") or raw.get("timeStamp")
    )
    if timestamp is None:
        raise AzureRecordError("record has no parseable timestamp")

    model_id = _model_id(props)
    if model_id is None:
        # Azure normally emits model identity; its absence is a data-quality gap
        # (the record is still usable for coverage), not a schema limitation.
        model_id = ""
        availability["model_id"] = FieldAvailability.MISSING

    region = raw.get("location") or raw.get("Location")
    if not region:
        region = None
        availability["region"] = FieldAvailability.MISSING

    # ── Token counts — present only on some configurations ──────────────────
    input_tokens = _int_or_none(props.get("promptTokens") or props.get("PromptTokens"))
    output_tokens = _int_or_none(
        props.get("completionTokens") or props.get("CompletionTokens")
    )
    usage_reported = any(
        k in props
        for k in (
            "promptTokens",
            "PromptTokens",
            "completionTokens",
            "CompletionTokens",
        )
    )
    if input_tokens is None:
        availability["input_token_count"] = (
            FieldAvailability.MISSING
            if usage_reported
            else FieldAvailability.UNAVAILABLE
        )
    if output_tokens is None:
        availability["output_token_count"] = (
            FieldAvailability.MISSING
            if usage_reported
            else FieldAvailability.UNAVAILABLE
        )

    # ── Outcome ─────────────────────────────────────────────────────────────
    result_type = str(raw.get("resultType") or raw.get("ResultType") or "").lower()
    result_signature = str(
        raw.get("resultSignature") or raw.get("ResultSignature") or ""
    )
    error_code: Optional[str] = None
    if result_type and result_type not in _SUCCESS_RESULT_TYPES:
        error_code = result_signature or result_type
    elif result_signature and not result_signature.startswith("2"):
        error_code = result_signature

    # ── Structural gaps in the Azure schema ─────────────────────────────────
    # Azure does not report why generation stopped, so truncation is not
    # observable here. truncated=False means "not observed", NOT "not truncated"
    # — RP-OBS-COMPLETE reads the availability map, not the bare flag.
    availability["stop_reason"] = FieldAvailability.UNAVAILABLE
    availability["truncated"] = FieldAvailability.UNAVAILABLE

    tools = _extract_tools(props)
    if tools is None:
        tools = ()
        availability["tools"] = FieldAvailability.UNAVAILABLE

    return NormalizedInvocationRecord(
        provenance=SourceProvenance(
            adapter_id=config.adapter_id,
            source_uri=source_uri,
            cursor=cursor,
            record_hash=_record_hash(raw),
        ),
        # INV-3: tenancy comes from operator config. Azure records carry
        # subscription/objectId/Entra GUIDs that must never influence this.
        tenant_id=config.tenant_id,
        request_id=str(request_id),
        model_id=model_id,
        operation=str(operation),
        region=region,
        timestamp=timestamp,
        input_token_count=input_tokens,
        output_token_count=output_tokens,
        stop_reason=None,
        truncated=False,
        error_code=error_code,
        tools=tools,
        field_availability=availability,
    )
