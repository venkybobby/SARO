"""Vertex AI Cloud Audit Log parsing (STORY-360).

Pure functions, no I/O, no GCP SDK — same split as the Bedrock and Azure
adapters, so parsing is unit-testable without cloud credentials.

**Body-blind by construction.** `protoPayload.request` / `.response` may contain
the prompt and completion for generative calls. No function in this module reads
them: the parser only ever indexes the specific envelope keys named below. That
is a stronger guarantee than filtering payloads out afterwards, because there is
no code path where the content is in scope in the first place.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from adapters.contract import (
    FieldAvailability,
    NormalizedInvocationRecord,
    SourceProvenance,
    ToolInvocation,
)
from adapters.vertex_ai.records import (
    MAX_RECORD_CHARS,
    RPC_CODE_NAMES,
    SUPPORTED_SERVICE,
    VertexAdapterConfig,
    VertexRecordError,
    VertexRecordTooLarge,
    VertexServiceSkipped,
)

logger = logging.getLogger(__name__)

# Optional tool keys. NOT part of the audit schema — present only when a
# customer enriches the export (e.g. a gateway log shipped in the same sink).
# Parsed when present; absent by default, which is the honest common case.
_TOOL_OFFERED_KEYS = ("tools", "toolDeclarations", "functionDeclarations")
_TOOL_INVOKED_KEYS = ("toolCalls", "functionCalls")


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Cloud Logging emits RFC 3339 with up to 9 fractional digits (nanoseconds)."""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:
        head, _, tail = text.partition(".")
        digits = "".join(c for c in tail if c.isdigit())
        offset = tail[len(digits):]
        # Python parses at most microseconds; nanosecond precision is truncated,
        # not rounded — ordering within the stream is preserved either way.
        text = f"{head}.{digits[:6]}{offset}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _record_hash(raw: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=True, default=str).encode()
    ).hexdigest()


def _model_from_resource_name(resource_name: str) -> Optional[str]:
    """Extract model identity from a Vertex resource name.

    ``…/publishers/google/models/gemini-1.5-pro`` → ``gemini-1.5-pro``.

    ``…/endpoints/1234567890`` returns **None**: an endpoint id is not a model
    id. Which model sits behind a customer's endpoint is not in the log, and
    passing the endpoint id off as a model would make a model-allowlist rule
    silently meaningless while appearing to work.
    """
    if not resource_name:
        return None
    parts = resource_name.split("/")
    for marker in ("models", "publishers"):
        if marker in parts:
            idx = parts.index("models") if "models" in parts else -1
            if idx != -1 and idx + 1 < len(parts):
                return parts[idx + 1] or None
            break
    return None


def _short_method(method_name: str) -> str:
    """``google.cloud.aiplatform.v1.PredictionService.GenerateContent`` →
    ``PredictionService.GenerateContent`` — enough to identify the operation
    without carrying the full package path into every record."""
    parts = method_name.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else method_name


def _tool_names(container: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(container, list):
        return names
    for item in container:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = item.get("name") or (item.get("functionDeclaration") or {}).get("name")
            if isinstance(name, str) and name:
                names.append(name)
    return names


def _extract_tools(source: dict[str, Any]) -> Optional[tuple[ToolInvocation, ...]]:
    """Return tool invocations, or None when no tool data is present at all.

    ``None`` (no tool information in the schema) and ``()`` (tool data present,
    no tools used) are different observations and must not be conflated.
    """
    offered: list[str] = []
    invoked: list[str] = []
    saw_tool_data = False

    for key in _TOOL_OFFERED_KEYS:
        if key in source:
            saw_tool_data = True
            offered.extend(_tool_names(source[key]))
    for key in _TOOL_INVOKED_KEYS:
        if key in source:
            saw_tool_data = True
            invoked.extend(_tool_names(source[key]))

    if not saw_tool_data:
        return None

    offered_set, invoked_set = set(offered), set(invoked)
    return tuple(
        ToolInvocation(name=n, offered=n in offered_set, invoked=n in invoked_set)
        for n in sorted(offered_set | invoked_set)
    )


def parse_record(
    raw: Any,
    *,
    config: VertexAdapterConfig,
    cursor: str,
    source_uri: Optional[str] = None,
) -> NormalizedInvocationRecord:
    """Parse one Cloud Logging LogEntry into the normalized contract.

    Raises :class:`VertexRecordError` on records that cannot be interpreted; a
    malformed record is never turned into a half-populated observation, because
    a fabricated record is worse than a skipped one in an evidence system.
    """
    if isinstance(raw, str):
        if len(raw) > MAX_RECORD_CHARS:
            raise VertexRecordTooLarge(
                f"record exceeds {MAX_RECORD_CHARS}-char cap ({len(raw)})"
            )
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VertexRecordError(f"record is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise VertexRecordError(f"record is not a JSON object (got {type(raw).__name__})")

    payload = raw.get("protoPayload") or {}
    if not isinstance(payload, dict):
        payload = {}

    service = payload.get("serviceName") or ""
    if service and service != SUPPORTED_SERVICE:
        raise VertexServiceSkipped(
            f"serviceName {service!r} is not {SUPPORTED_SERVICE!r} — not interpreted"
        )

    resource = raw.get("resource") or {}
    labels = resource.get("labels") or {} if isinstance(resource, dict) else {}

    availability: dict[str, FieldAvailability] = {}

    # ── Identity ────────────────────────────────────────────────────────────
    request_id = raw.get("insertId") or (raw.get("operation") or {}).get("id")
    if not request_id:
        raise VertexRecordError("entry has no insertId — cannot identify the invocation")

    method_name = payload.get("methodName")
    if not method_name:
        raise VertexRecordError("entry has no protoPayload.methodName")

    timestamp = _parse_timestamp(raw.get("timestamp") or raw.get("receiveTimestamp"))
    if timestamp is None:
        raise VertexRecordError("entry has no parseable timestamp")

    # ── Model identity ──────────────────────────────────────────────────────
    model_id = _model_from_resource_name(str(payload.get("resourceName") or ""))
    if model_id is None:
        # Endpoint-deployed models do not expose the model in the audit log.
        # MISSING (not UNAVAILABLE): Vertex *does* report model identity for
        # publisher models — this particular deployment shape does not.
        model_id = ""
        availability["model_id"] = FieldAvailability.MISSING

    region = labels.get("location") or None
    if not region:
        availability["region"] = FieldAvailability.MISSING

    # ── Outcome ─────────────────────────────────────────────────────────────
    status = payload.get("status") or {}
    error_code: Optional[str] = None
    if isinstance(status, dict):
        code = status.get("code")
        if isinstance(code, int) and code != 0:
            error_code = RPC_CODE_NAMES.get(code, f"RPC_{code}")

    # ── Structural gaps in the audit schema ─────────────────────────────────
    # Audit logs report that a call happened, not how generation went.
    availability["input_token_count"] = FieldAvailability.UNAVAILABLE
    availability["output_token_count"] = FieldAvailability.UNAVAILABLE
    availability["stop_reason"] = FieldAvailability.UNAVAILABLE
    availability["truncated"] = FieldAvailability.UNAVAILABLE

    # Tool data: only from an enriched export's own metadata — never from
    # protoPayload.request/.response, which may hold prompt/completion content.
    metadata = raw.get("labels") if isinstance(raw.get("labels"), dict) else {}
    tools = _extract_tools(metadata or {})
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
        # INV-3: tenancy from operator config. resource.labels.project_id and
        # authenticationInfo.principalEmail are log content and must not decide it.
        tenant_id=config.tenant_id,
        request_id=str(request_id),
        model_id=model_id,
        operation=_short_method(str(method_name)),
        region=region,
        timestamp=timestamp,
        input_token_count=None,
        output_token_count=None,
        stop_reason=None,
        truncated=False,
        error_code=error_code,
        tools=tools,
        field_availability=availability,
    )
