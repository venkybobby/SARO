"""Typed records for the Vertex AI observation adapter (STORY-360).

Vertex AI activity reaches a customer-owned sink as **Cloud Logging LogEntry**
JSON (Cloud Audit Logs for `aiplatform.googleapis.com`), exported to GCS. SARO
reads that export; it never calls the GCP control plane (INV-6).

What the audit schema carries:

* `insertId`, `timestamp` (nanosecond precision), `resource.labels`
  (`project_id`, `location`, `endpoint_id`/`model_id`), `severity`
* `protoPayload.methodName` (e.g. `…PredictionService.GenerateContent`),
  `.resourceName`, `.status` (a `google.rpc.Status`), `.authenticationInfo`

What it does **not** carry: token counts, stop reason, and tool/function-call
data. Those are structural gaps, surfaced as `FieldAvailability.UNAVAILABLE`.

**The INV-2 hazard that makes this adapter different from Azure.** Vertex Data
Access audit logs *can* include `protoPayload.request` and
`protoPayload.response`, and for generative calls those hold the actual prompt
and model output — real PHI. Azure's diagnostic logs contain no payload at all,
so INV-2 held there by luck of the schema. Here the payload may genuinely be
present in the source, and the parser must refuse to read it *by construction*.
It does: no code path touches those keys, and
`tests/test_story360_vertex_adapter.py` feeds records with PHI-shaped payloads
present and asserts nothing reaches the normalized record.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from adapters.export_source import ExportRecordError, RecordSkipped

VERTEX_AI_ADAPTER_ID = "vertex-ai-audit-log"

# Body-size cap — exported log objects are untrusted input (FND-2 class).
MAX_RECORD_CHARS = 1_000_000

# Only Vertex AI (`aiplatform`) entries are interpreted. A sink often carries
# many services' audit logs in one export; misreading another service's entry
# would fabricate an observation that never happened.
SUPPORTED_SERVICE = "aiplatform.googleapis.com"

# Payload keys that may contain prompt/completion content. Listed here solely so
# the prohibition is explicit and testable — nothing reads them.
FORBIDDEN_PAYLOAD_KEYS = ("request", "response")

# google.rpc.Code — 0 is OK; the rest are failures worth surfacing as error_code.
RPC_CODE_NAMES = {
    0: "OK",
    1: "CANCELLED",
    2: "UNKNOWN",
    3: "INVALID_ARGUMENT",
    4: "DEADLINE_EXCEEDED",
    5: "NOT_FOUND",
    6: "ALREADY_EXISTS",
    7: "PERMISSION_DENIED",
    8: "RESOURCE_EXHAUSTED",
    9: "FAILED_PRECONDITION",
    10: "ABORTED",
    11: "OUT_OF_RANGE",
    12: "UNIMPLEMENTED",
    13: "INTERNAL",
    14: "UNAVAILABLE",
    15: "DATA_LOSS",
    16: "UNAUTHENTICATED",
}


@dataclass(frozen=True)
class VertexAdapterConfig:
    """Per-stream binding supplied by the operator — NOT read from the log.

    ``tenant_id`` decides which SARO tenant an export maps to. Vertex records
    carry `resource.labels.project_id` and principal emails that look
    tenant-shaped; none of them may set SARO tenancy (INV-3). A log is
    attacker-influenced input.
    """

    tenant_id: uuid.UUID
    container: str
    prefix: str = ""
    adapter_id: str = VERTEX_AI_ADAPTER_ID


class VertexRecordError(ExportRecordError):
    """A record could not be interpreted as a Vertex AI invocation."""


class VertexRecordTooLarge(VertexRecordError):
    """Record exceeds the size cap — refused before parsing."""


class VertexServiceSkipped(VertexRecordError, RecordSkipped):
    """Entry belongs to another GCP service — skipped, never guessed at."""
