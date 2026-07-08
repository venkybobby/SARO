"""Bedrock invocation-log adapter (STORY-406).

Turns a customer's AWS Bedrock *model-invocation logs* into SARO's two evidence
streams — observation-coverage heartbeats and async risk audits — WITHOUT SARO
ever invoking a hosted model. The adapter is a read-only parser of logs the
customer already emitted (CloudWatch Logs / S3); it only ever reaches AWS S3 to
fetch an externalized message body, never a model-inference endpoint.

Two branches with an enforced seam (INV-2):

* **coverage** — envelope-only. :func:`emit_coverage` takes an :class:`Envelope`
  (modelId, cursor, timestamp) and never sees a body. Structurally incapable of
  leaking observed content into the evidence store.
* **audit** — may resolve message bodies (inline, or S3-externalized via an
  injected, read-only ``resolve_body``) and submit ``prompt`` + ``raw_output``
  to the SARO engine.

This story implements the **backfill** (historical replay) path with a monotonic
stream cursor as the coverage watermark; live-tail is a follow-on that reuses the
same primitive. See ``specs/stories/STORY-406.md``.
"""

from __future__ import annotations

from adapters.bedrock.records import (
    AuditSubmission,
    BedrockAdapterConfig,
    Envelope,
)
from adapters.bedrock.parse import (
    build_audit_submission,
    extract_prompt_output,
    map_source_model,
    parse_envelope,
)
from adapters.bedrock.replay import BackfillResult, emit_coverage, replay_backfill

__all__ = [
    "AuditSubmission",
    "BedrockAdapterConfig",
    "Envelope",
    "BackfillResult",
    "build_audit_submission",
    "extract_prompt_output",
    "map_source_model",
    "parse_envelope",
    "emit_coverage",
    "replay_backfill",
]
