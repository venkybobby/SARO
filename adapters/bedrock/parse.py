"""Parsing + normalization for Bedrock model-invocation logs (STORY-406).

Pure functions — no I/O of their own. The audit branch may need to fetch an
S3-externalized body; that is done through an injected ``resolve_body`` callable
so this module never imports boto3 and stays trivially unit-testable. The
coverage branch calls :func:`parse_envelope` only (INV-2).

Supports both Bedrock invocation shapes:

* ``Converse`` / ``ConverseStream`` — ``content`` blocks are ``{"text": ...}``;
  offered tools live in ``toolConfig.tools[].toolSpec.name``; the model's
  intended actions are ``toolUse`` blocks; stop reason key is ``stopReason``.
* ``InvokeModel`` / ``InvokeModelWithResponseStream`` (Anthropic body) —
  ``content`` blocks are ``{"type": "text"|"tool_use"|"tool_result", ...}``;
  offered tools live in ``tools[].name``; stop reason key is ``stop_reason``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from urllib.parse import urlparse

from adapters.bedrock.records import (
    MAX_INLINE_BODY_CHARS,
    AuditSubmission,
    BedrockAdapterConfig,
    Envelope,
)

logger = logging.getLogger(__name__)

# Injected resolver: an S3 path (e.g. "s3://bucket/key") -> parsed JSON body.
BodyResolver = Callable[[str], dict[str, Any]]


class S3PathNotAllowed(ValueError):
    """An externalized-body S3 path is not on the operator's bucket allowlist."""


def validate_s3_path(s3_path: str, config: BedrockAdapterConfig) -> tuple[str, str]:
    """Validate an untrusted ``s3Path`` before any fetch (FND-1, confused-deputy).

    The path comes from the log producer, not the operator. Enforce the ``s3://``
    scheme and a deny-by-default bucket allowlist so a crafted record cannot make
    SARO read an arbitrary object with its own credentials. Returns (bucket, key).
    """
    parsed = urlparse(s3_path)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise S3PathNotAllowed(f"not an s3:// URI: {s3_path!r}")
    bucket, key = parsed.netloc, parsed.path.lstrip("/")
    if bucket not in config.allowed_s3_buckets:
        raise S3PathNotAllowed(
            f"bucket {bucket!r} is not in the operator allowlist "
            f"{sorted(config.allowed_s3_buckets)!r}"
        )
    return bucket, key


def _guarded_resolver(
    resolve_body: BodyResolver, config: BedrockAdapterConfig
) -> BodyResolver:
    """Return a resolver that allowlist-validates the path before delegating."""

    def _inner(s3_path: str) -> dict[str, Any]:
        validate_s3_path(s3_path, config)
        return resolve_body(s3_path)

    return _inner


_CONVERSE_OPS = frozenset({"Converse", "ConverseStream"})
_INVOKE_OPS = frozenset({"InvokeModel", "InvokeModelWithResponseStream"})
_TRUNCATION_STOP_REASONS = frozenset({"max_tokens"})
_MAX_BLOCK_DEPTH = 6  # bound recursion over nested toolResult content


def map_source_model(model_id: str) -> str:
    """Map a Bedrock ``modelId`` to SARO's narrow ``source_model`` enum (D1).

    ``anthropic.*`` (incl. cross-region ``us.anthropic.claude-*``) -> ``"claude"``;
    every other Bedrock model -> the ``"bedrock"`` catch-all. The exact model is
    never lost: callers keep it in ``system_id`` and ``metadata.modelId``.
    """
    segments = (model_id or "").lower().split(".")
    if "anthropic" in segments:
        return "claude"
    return "bedrock"


def _parse_timestamp(value: Any) -> datetime:
    """Parse the record's source-side timestamp into an aware UTC datetime.

    Uses the source-side time so watermark deltas are computed in the source's
    clock (documented skew tolerance in the story). Raises ``ValueError`` on a
    missing/unparseable timestamp — the caller (``replay_backfill``) treats that
    as a malformed record and skips it, so a heartbeat is never written against a
    bogus source-side time.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        text = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning("bedrock adapter: unparseable timestamp %r", value)
    raise ValueError(f"record has no parseable timestamp: {value!r}")


def parse_envelope(raw: dict[str, Any], *, cursor: str) -> Envelope:
    """Body-free envelope for the coverage branch. Reads ONLY envelope keys.

    ``cursor`` is the caller-supplied monotonic stream position (the log is
    positional; the record does not carry its own cursor). It becomes the
    coverage watermark for resumable backfill.
    """
    input_section = raw.get("input") or {}
    output_section = raw.get("output") or {}
    return Envelope(
        request_id=str(raw.get("requestId", "")),
        region=str(raw.get("region", "")),
        operation=str(raw.get("operation", "")),
        model_id=str(raw.get("modelId", "")),
        timestamp=_parse_timestamp(raw.get("timestamp")),
        cursor=cursor,
        input_token_count=input_section.get("inputTokenCount"),
        output_token_count=output_section.get("outputTokenCount"),
    )


def _load_body(
    section: dict[str, Any],
    json_key: str,
    s3_key: str,
    resolve_body: Optional[BodyResolver],
) -> dict[str, Any]:
    """Return a message body: inline JSON if present, else S3-resolved (audit
    branch only). Missing/failed -> ``{}`` (caller decides to skip)."""
    body = section.get(json_key)
    if body is None:
        s3_path = section.get(s3_key)
        if s3_path:
            if resolve_body is None:
                raise ValueError(
                    f"body externalized to {s3_path!r} but no resolver supplied"
                )
            body = resolve_body(s3_path)
    if isinstance(body, str):
        if len(body) > MAX_INLINE_BODY_CHARS:
            raise ValueError(
                f"inline body exceeds {MAX_INLINE_BODY_CHARS}-char cap "
                f"({len(body)}) — refusing to parse (FND-2)"
            )
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("bedrock adapter: body is a non-JSON string; ignoring")
            return {}
    return body if isinstance(body, dict) else {}


def _block_text(block: Any, depth: int = 0) -> str:
    """Flatten one content block to text, following tool-result nesting.

    Handles Converse (``{"text": ...}``, ``{"toolResult": {...}}``) and Anthropic
    (``{"type": "text"|"tool_result", ...}``) shapes. ``toolUse``/``tool_use``
    blocks contribute no text (their intent is captured separately in metadata).
    """
    if depth > _MAX_BLOCK_DEPTH or not isinstance(block, dict):
        return ""
    text = block.get("text")
    if isinstance(text, str):
        return text
    # Converse toolResult / Anthropic tool_result carry untrusted tool output.
    inner = block.get("toolResult")
    if inner is None and block.get("type") == "tool_result":
        inner = block
    if isinstance(inner, dict):
        content = inner.get("content")
        return _flatten_content(content, depth + 1)
    return ""


def _flatten_content(content: Any, depth: int = 0) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [_block_text(b, depth) for b in content]
        return "\n".join(p for p in parts if p)
    return ""


def _tool_use_names(content: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(content, list):
        return names
    for block in content:
        if not isinstance(block, dict):
            continue
        tu = block.get("toolUse")
        if isinstance(tu, dict) and tu.get("name"):
            names.append(str(tu["name"]))
        elif block.get("type") == "tool_use" and block.get("name"):
            names.append(str(block["name"]))
    return names


def _offered_tools(input_body: dict[str, Any]) -> list[str]:
    names: list[str] = []
    tool_config = input_body.get("toolConfig")
    if isinstance(tool_config, dict):  # Converse
        for t in tool_config.get("tools", []) or []:
            spec = t.get("toolSpec") if isinstance(t, dict) else None
            if isinstance(spec, dict) and spec.get("name"):
                names.append(str(spec["name"]))
    for t in input_body.get("tools", []) or []:  # Anthropic InvokeModel
        if isinstance(t, dict) and t.get("name"):
            names.append(str(t["name"]))
    return names


def _prompt_from_input(input_body: dict[str, Any]) -> str:
    """Flatten system + all conversation turns into a single readable prompt."""
    lines: list[str] = []
    system = input_body.get("system")
    system_text = _flatten_content(system) if system is not None else ""
    if system_text:
        lines.append(f"system: {system_text}")
    for msg in input_body.get("messages", []) or []:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", "user"))
        text = _flatten_content(msg.get("content"))
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines)


def _output_message_content(output_body: dict[str, Any]) -> Any:
    # Converse nests under output.message.content; Anthropic InvokeModel is flat.
    nested = output_body.get("output")
    if isinstance(nested, dict):
        message = nested.get("message")
        if isinstance(message, dict):
            return message.get("content")
    return output_body.get("content")


def extract_prompt_output(
    raw: dict[str, Any], *, resolve_body: Optional[BodyResolver] = None
) -> tuple[str, str, bool, dict[str, Any]]:
    """Audit-branch extraction: (prompt, raw_output, truncated, tool_metadata).

    May resolve S3-externalized bodies via ``resolve_body``. ``tool_metadata``
    carries the offered-tools manifest, the model's requested tool actions, and
    the stop reason — the data future evaluability rules consume.
    """
    input_section = raw.get("input") or {}
    output_section = raw.get("output") or {}
    input_body = _load_body(
        input_section, "inputBodyJson", "inputBodyS3Path", resolve_body
    )
    output_body = _load_body(
        output_section, "outputBodyJson", "outputBodyS3Path", resolve_body
    )

    prompt = _prompt_from_input(input_body)
    out_content = _output_message_content(output_body)
    raw_output = _flatten_content(out_content)

    stop_reason = output_body.get("stopReason") or output_body.get("stop_reason") or ""
    truncated = stop_reason in _TRUNCATION_STOP_REASONS
    tool_metadata = {
        "tool_config": _offered_tools(input_body),
        "tool_use": _tool_use_names(out_content),
        "stop_reason": stop_reason,
        "truncated": truncated,
    }
    return prompt, raw_output, truncated, tool_metadata


def build_audit_submission(
    raw: dict[str, Any],
    envelope: Envelope,
    config: BedrockAdapterConfig,
    *,
    resolve_body: Optional[BodyResolver] = None,
) -> Optional[AuditSubmission]:
    """Build an engine-ready audit payload, or ``None`` to skip (no usable text).

    Returning ``None`` (e.g. empty ``raw_output`` — SARO requires non-empty
    prompt+output) lets the caller skip the AUDIT while still emitting the
    coverage heartbeat: we observed the invocation even if there is nothing to
    score.
    """
    # Wrap the (possibly injected) resolver so every S3 fetch is allowlist-checked
    # against operator config before egress (FND-1) — even a test resolver.
    guarded = _guarded_resolver(resolve_body, config) if resolve_body else None
    prompt, raw_output, truncated, tool_metadata = extract_prompt_output(
        raw, resolve_body=guarded
    )
    if not prompt or not raw_output:
        logger.info(
            "bedrock adapter: skipping audit for %s (empty prompt/output)",
            envelope.request_id,
        )
        return None

    # Metadata key names match the AC-1 contract that downstream Wave-1 rules read.
    metadata = {
        "requestId": envelope.request_id,
        "region": envelope.region,
        "operation": envelope.operation,
        "modelId": envelope.model_id,
        "inputTokenCount": envelope.input_token_count,
        "outputTokenCount": envelope.output_token_count,
        "stopReason": tool_metadata["stop_reason"],
        "toolConfig": tool_metadata["tool_config"],
        "toolUse": tool_metadata["tool_use"],
        "truncated": tool_metadata["truncated"],
    }
    return AuditSubmission(
        prompt=prompt,
        raw_output=raw_output,
        source_model=map_source_model(envelope.model_id),
        vertical=config.vertical,
        truncated=truncated,
        metadata=metadata,
    )
