"""STORY-404 (Epic 14): governance-runtime audit-event emitter + SIEM export.

Evidence-grade audit is the compliance product. SARO emits structured, tamper-evident
events; the **client SIEM is system-of-record** (SARO does not build WORM storage). This
module reuses the SHA-256 chaining approach of services/hash_chain_service.py (don't
reinvent the crypto) but for the governance-runtime event schema, and adds:

- a content-free event schema (hashes + pointers only — never raw input/output),
- **per-tenant** hash chains (each tenant has its own chain head, so chains are isolated
  and appends serialize within a tenant without a global bottleneck),
- JSON + Parquet export over a pluggable, injected transport (a no-op/local sink is fine
  for Phase 1; PrivateLink wiring is deployment-dependent and out of scope here),
- a chain-verification utility that flags a deliberately altered event.

Retention boundary (AC-4): SARO keeps only per-tenant chain *lineage* (the current head
hash + sequence) so it can chain the next event. Events are emitted outward, never durably
stored here as system-of-record.

Invariant guard (Epic 14): deterministic crypto only — no external model/network call; an
event never embeds raw input/output content (the compliance posture forbids it).
"""

from __future__ import annotations

import hashlib
import io
import json
import threading
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

# Fields sealed by the per-event hash. Includes chain_seq (the event's position) so the
# ordering is tamper-evident. event_hash is the output (excluded); prev_hash is fed in as the
# chaining input to compute_event_hash and re-checked on the verify path (not hashed directly).
_HASHED_FIELDS = (
    "tenant_id",
    "policy_version",
    "trigger_mode",
    "decision",
    "rationale",
    "evidence_pointers",
    "actor",
    "timestamp",
    "input_hash",
    "output_hash",
    "latency_ms",
    "fail_mode_applied",
    "chain_seq",
)

# Required non-empty fields for a well-formed event (AC-1 schema validation).
_REQUIRED_FIELDS = (
    "tenant_id",
    "policy_version",
    "trigger_mode",
    "decision",
    "actor",
    "timestamp",
    "input_hash",
    "output_hash",
)

EmitTransport = Callable[["AuditEvent"], None]


@dataclass
class AuditEvent:
    """A content-free, tamper-evident governance-runtime audit event.

    Only hashes (`input_hash`/`output_hash`) and pointers (`evidence_pointers`) are carried —
    never the raw prompt/output. `prev_hash`/`event_hash`/`chain_seq` are sealed by the emitter.
    """

    tenant_id: str
    policy_version: int
    trigger_mode: str
    decision: str  # "allow" | "block"
    rationale: str
    evidence_pointers: list[str]
    actor: str
    timestamp: str
    input_hash: str
    output_hash: str
    latency_ms: float | None = None
    fail_mode_applied: str | None = None
    # Sealed by AuditEmitter.emit():
    prev_hash: str | None = None
    event_hash: str | None = None
    chain_seq: int = 0


def hash_content(text: str) -> str:
    """SHA-256 hex of content destined for an event. The raw text is hashed, never stored."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_event(event: AuditEvent) -> None:
    """Raise ValueError if a required field is missing/empty (AC-1)."""
    for name in _REQUIRED_FIELDS:
        value = getattr(event, name)
        if value is None or (isinstance(value, str) and value == ""):
            raise ValueError(f"audit event missing required field: {name}")


def _canonical_payload(event: AuditEvent, prev_hash: str | None) -> dict:
    """Deterministic dict hashed for chaining — single definition for write + verify paths.

    latency_ms is canonicalized to a fixed-decimal string so the hash is stable across
    languages/serializers (a raw float's repr is not portable — a Go/Java SIEM re-deriving
    the hash must get the same bytes)."""
    payload: dict = {name: getattr(event, name) for name in _HASHED_FIELDS}
    if payload["latency_ms"] is not None:
        payload["latency_ms"] = f"{float(payload['latency_ms']):.3f}"
    payload["prev_hash"] = prev_hash or "GENESIS"
    return payload


def compute_event_hash(event: AuditEvent, prev_hash: str | None) -> str:
    canonical = json.dumps(
        _canonical_payload(event, prev_hash), sort_keys=True, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _noop_transport(_event: AuditEvent) -> None:
    """Default sink — replaced by the real SIEM transport (PrivateLink, etc.) in deployment."""


class AuditEmitter:
    """Seals events into per-tenant SHA-256 chains and emits them via an injected transport.

    Retains only per-tenant lineage (head hash + sequence), not the events themselves.
    Per-tenant locks let different tenants append concurrently (no global bottleneck);
    appends within one tenant serialize so the chain head advances atomically.
    """

    def __init__(self, transport: EmitTransport | None = None) -> None:
        self._transport: EmitTransport = transport or _noop_transport
        self._heads: dict[str, str] = {}  # tenant_id -> last event_hash (lineage)
        self._seq: dict[str, int] = {}  # tenant_id -> next chain sequence
        self._locks: dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    def _tenant_lock(self, tenant_id: str) -> threading.Lock:
        with self._meta_lock:
            return self._locks.setdefault(tenant_id, threading.Lock())

    def emit(self, event: AuditEvent) -> AuditEvent:
        validate_event(event)
        tid = event.tenant_id
        with self._tenant_lock(tid):
            prev = self._heads.get(tid)  # None == genesis for this tenant
            event.prev_hash = prev
            event.chain_seq = self._seq.get(tid, 0)
            event.event_hash = compute_event_hash(event, prev)
            self._heads[tid] = event.event_hash
            self._seq[tid] = event.chain_seq + 1
            # Delivery is at-most-once: the head advances above regardless of the transport
            # outcome, so SARO's lineage is authoritative and a transport failure surfaces as a
            # detectable gap (via the head/count anchors) rather than a rewritten chain.
            # Deliver INSIDE the per-tenant lock so concurrent same-tenant emits reach the
            # transport in chain order (sealing + delivery serialize together). Different
            # tenants hold different locks, so cross-tenant concurrency is preserved.
            self._transport(event)
        return event

    def chain_head(self, tenant_id: str) -> str | None:
        """Trusted anchor: the current head hash for a tenant (None if no events yet)."""
        with self._tenant_lock(tenant_id):
            return self._heads.get(tenant_id)

    def chain_length(self, tenant_id: str) -> int:
        """Trusted anchor: number of events sealed for a tenant (the next chain_seq)."""
        with self._tenant_lock(tenant_id):
            return self._seq.get(tenant_id, 0)


def verify_chain(
    events: Sequence[AuditEvent],
    *,
    expected_head: str | None = None,
    expected_count: int | None = None,
) -> dict:
    """Verify a single tenant's chain by replaying hashes; flags the first altered event.

    Pass the emitter's trusted anchors (``expected_head`` = AuditEmitter.chain_head, and/or
    ``expected_count`` = AuditEmitter.chain_length) to also detect tail TRUNCATION — replay
    alone cannot, since a truncated prefix is internally self-consistent. Each step asserts
    contiguous ``chain_seq`` and that the stored ``prev_hash`` matches the replayed link, so
    reordering / renumbering / back-pointer edits are caught too.

    Raises ValueError if events span more than one tenant — a chain is single-tenant by
    construction, and mixing tenants is the isolation failure this guards against.
    """
    tenants = {e.tenant_id for e in events}
    if len(tenants) > 1:
        raise ValueError(
            f"verify_chain requires a single-tenant chain; got tenants {sorted(tenants)}"
        )

    def _fail(index: int | None, reason: str, **extra: object) -> dict:
        return {
            "valid": False,
            "events_checked": len(events),
            "break_at_index": index,
            "reason": reason,
            **extra,
        }

    if expected_count is not None and len(events) != expected_count:
        return _fail(
            None,
            "length mismatch (truncated/extended)",
            expected_count=expected_count,
            actual_count=len(events),
        )

    prev_hash: str | None = None
    for index, event in enumerate(events):
        if event.chain_seq != index:
            return _fail(index, "chain_seq not contiguous")
        if event.prev_hash != prev_hash:
            return _fail(index, "stored prev_hash does not match chain")
        expected = compute_event_hash(event, prev_hash)
        if expected != event.event_hash:
            return _fail(
                index,
                "event_hash mismatch",
                expected_hash=expected,
                actual_hash=event.event_hash,
            )
        prev_hash = event.event_hash

    if expected_head is not None and prev_hash != expected_head:
        return _fail(
            None,
            "head mismatch (tail truncated)",
            expected_head=expected_head,
            actual_head=prev_hash,
        )

    return {"valid": True, "events_checked": len(events), "break_at_index": None}


def _event_rows(events: Sequence[AuditEvent]) -> list[dict]:
    return [asdict(e) for e in events]


def export_json(events: Sequence[AuditEvent]) -> str:
    """Structured JSON export (one object per event; hashes/pointers only)."""
    return json.dumps(_event_rows(events), sort_keys=True, default=str)


def _parquet_schema():
    import pyarrow as pa

    # Explicit schema so all-null columns (e.g. a batch with every latency_ms None) keep a
    # stable physical type across exports — a strict SIEM schema-on-read depends on it.
    return pa.schema(
        [
            ("tenant_id", pa.string()),
            ("policy_version", pa.int64()),
            ("trigger_mode", pa.string()),
            ("decision", pa.string()),
            ("rationale", pa.string()),
            ("evidence_pointers", pa.list_(pa.string())),
            ("actor", pa.string()),
            ("timestamp", pa.string()),
            ("input_hash", pa.string()),
            ("output_hash", pa.string()),
            ("latency_ms", pa.float64()),
            ("fail_mode_applied", pa.string()),
            ("prev_hash", pa.string()),
            ("event_hash", pa.string()),
            ("chain_seq", pa.int64()),
        ]
    )


def export_parquet(events: Sequence[AuditEvent]) -> bytes:
    """Parquet export (hashes/pointers only) with an explicit, stable schema."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = _event_rows(events)
    schema = _parquet_schema()
    table = pa.table(
        {field.name: [row.get(field.name) for row in rows] for field in schema},
        schema=schema,
    )
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()
