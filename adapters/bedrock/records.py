"""Typed records for the Bedrock invocation-log adapter (STORY-406).

The ``Envelope`` is the *only* structure the coverage branch ever receives —
that is the INV-2 seam expressed in the type system: a function that takes an
``Envelope`` cannot, even by mistake, read a message body.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# The one adapter-family id these logs map to. Token-safe for the coverage store.
BEDROCK_ADAPTER_ID = "bedrock-invocation-log"

# Body-size caps (FND-2 — untrusted logs must not exhaust memory). An inline body
# larger than this, or an S3 object exceeding it, is rejected before parsing.
MAX_INLINE_BODY_CHARS = 5_000_000
MAX_S3_BODY_BYTES = 5_000_000


@dataclass(frozen=True)
class BedrockAdapterConfig:
    """Per-stream binding supplied by the operator — NOT present in the log.

    ``tenant_id`` decides which SARO tenant a log stream maps to; ``vertical``
    is the risk context for the audit. ``user_id`` attributes backfilled audits
    to the operator account that ran the replay.

    ``allowed_s3_buckets`` is a security control (FND-1): the ``inputBodyS3Path``
    / ``outputBodyS3Path`` fields are authored by the *log producer* (untrusted),
    yet the audit branch fetches them with SARO's own AWS credentials. Only
    buckets in this allowlist may be fetched. It is **deny-by-default** — an
    empty set means SARO fetches NO externalized body, so an operator must
    explicitly opt in to their own log bucket(s) to use S3 externalization.
    """

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    vertical: str = "general"
    adapter_id: str = BEDROCK_ADAPTER_ID
    allowed_s3_buckets: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Envelope:
    """Body-free view of one invocation record. All fields come from the log
    *envelope*; none require reading (or fetching) a message body."""

    request_id: str
    region: str
    operation: str
    model_id: str
    timestamp: datetime
    cursor: str  # monotonic stream position (e.g. "s3:key:L42") — the watermark
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None


@dataclass(frozen=True)
class AuditSubmission:
    """A normalized, engine-ready audit payload built by the audit branch."""

    prompt: str
    raw_output: str
    source_model: str
    vertical: str
    truncated: bool
    metadata: dict[str, Any] = field(default_factory=dict)
