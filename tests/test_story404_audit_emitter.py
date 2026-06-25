"""STORY-404 — Audit-Event Emitter + SIEM Export tests.

AC coverage (see specs/stories/STORY-404.md):
- AC-1 event schema (policy_version, trigger_mode, decision+rationale, pointers, actor,
  timestamp, input_hash, output_hash, latency, fail_mode); NO raw input/output content
- AC-2 per-tenant hash chains (prev-hash within tenant; isolated; appends serialize)
- AC-3 JSON + Parquet export via an injected transport
- AC-4 SARO-side retention limited to chain lineage; events emitted outward
- AC-5 chain verification confirms integrity and flags a deliberately altered event

Invariant guard: deterministic crypto only — no external model/network; events never embed raw content.
"""

from __future__ import annotations

import dataclasses
import io
import json

import pytest

from services import audit_emitter
from services.audit_emitter import AuditEmitter, AuditEvent


def _event(
    tenant_id: str,
    *,
    actor: str = "svc",
    input_text: str = "in",
    output_text: str = "out",
) -> AuditEvent:
    return AuditEvent(
        tenant_id=tenant_id,
        policy_version=3,
        trigger_mode="block",
        decision="allow",
        rationale="block: completed in budget",
        evidence_pointers=["audit:abc123"],
        actor=actor,
        timestamp="2026-06-24T00:00:00+00:00",
        input_hash=audit_emitter.hash_content(input_text),
        output_hash=audit_emitter.hash_content(output_text),
        latency_ms=12.5,
        fail_mode_applied=None,
    )


# ---------------------------------------------------------------------------
# AC-1 — event schema; no raw content
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_event_has_required_fields() -> None:
    fields = {f.name for f in dataclasses.fields(AuditEvent)}
    required = {
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
    }
    assert required <= fields, f"missing fields: {required - fields}"


@pytest.mark.unit
def test_event_schema_carries_no_raw_content() -> None:
    fields = {f.name for f in dataclasses.fields(AuditEvent)}
    for forbidden in (
        "prompt",
        "raw_output",
        "output",
        "input",
        "samples",
        "text",
        "content",
    ):
        assert forbidden not in fields, (
            f"AuditEvent must not carry raw content field {forbidden!r}"
        )


@pytest.mark.unit
def test_validate_event_rejects_missing_required_field() -> None:
    ev = _event("t1")
    audit_emitter.validate_event(ev)  # well-formed passes
    ev.input_hash = ""  # blank required hash
    with pytest.raises(ValueError):
        audit_emitter.validate_event(ev)


@pytest.mark.unit
def test_input_output_hashing_is_deterministic_sha256() -> None:
    h = audit_emitter.hash_content("the quick brown fox")
    assert h == audit_emitter.hash_content("the quick brown fox")
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
    # The raw text must never equal its stored hash (i.e. content is not stored verbatim).
    assert h != "the quick brown fox"


# ---------------------------------------------------------------------------
# AC-2 / AC-5 — per-tenant hash chains + verification
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_intact_single_tenant_chain_verifies() -> None:
    sink: list[AuditEvent] = []
    em = AuditEmitter(transport=sink.append)
    for _ in range(5):
        em.emit(_event("tenant-a"))
    result = audit_emitter.verify_chain(sink)
    assert result["valid"] is True and result["events_checked"] == 5


@pytest.mark.unit
def test_altered_event_is_detected() -> None:
    sink: list[AuditEvent] = []
    em = AuditEmitter(transport=sink.append)
    for _ in range(4):
        em.emit(_event("tenant-a"))
    sink[2].decision = "block"  # tamper after sealing
    result = audit_emitter.verify_chain(sink)
    assert result["valid"] is False
    assert result["break_at_index"] == 2


@pytest.mark.unit
def test_per_tenant_chains_are_isolated() -> None:
    sink: list[AuditEvent] = []
    em = AuditEmitter(transport=sink.append)
    # Interleave two tenants.
    em.emit(_event("A"))
    em.emit(_event("B"))
    a2 = em.emit(_event("A"))
    em.emit(_event("B"))

    a_events = [e for e in sink if e.tenant_id == "A"]
    b_events = [e for e in sink if e.tenant_id == "B"]
    # Each tenant's chain verifies independently.
    assert audit_emitter.verify_chain(a_events)["valid"] is True
    assert audit_emitter.verify_chain(b_events)["valid"] is True
    # A's second event chains to A's first, never to B's.
    assert a2.prev_hash == a_events[0].event_hash
    assert a2.prev_hash not in {e.event_hash for e in b_events}


@pytest.mark.unit
def test_verify_chain_rejects_mixed_tenants() -> None:
    """A chain must be single-tenant — mixing is the isolation failure the pack forbids."""
    sink: list[AuditEvent] = []
    em = AuditEmitter(transport=sink.append)
    em.emit(_event("A"))
    em.emit(_event("B"))
    with pytest.raises(ValueError):
        audit_emitter.verify_chain(sink)  # mixed tenants


@pytest.mark.unit
def test_chain_seq_tamper_is_detected() -> None:
    """F2: chain_seq is sealed — renumbering an event breaks verification."""
    sink: list[AuditEvent] = []
    em = AuditEmitter(transport=sink.append)
    for _ in range(4):
        em.emit(_event("t"))
    sink[1].chain_seq = 99
    assert audit_emitter.verify_chain(sink)["valid"] is False


@pytest.mark.unit
def test_prev_hash_tamper_is_detected() -> None:
    sink: list[AuditEvent] = []
    em = AuditEmitter(transport=sink.append)
    for _ in range(3):
        em.emit(_event("t"))
    sink[2].prev_hash = "deadbeef"
    assert audit_emitter.verify_chain(sink)["valid"] is False


@pytest.mark.unit
def test_tail_truncation_detected_with_anchor() -> None:
    """F1: replay alone can't see a truncated tail; the emitter's head/count anchor does."""
    sink: list[AuditEvent] = []
    em = AuditEmitter(transport=sink.append)
    for _ in range(5):
        em.emit(_event("t"))
    head, count = em.chain_head("t"), em.chain_length("t")
    truncated = sink[:3]  # drop the last 2 events
    # Unanchored replay is fooled (self-consistent prefix)...
    assert audit_emitter.verify_chain(truncated)["valid"] is True
    # ...the trusted anchor catches it.
    assert (
        audit_emitter.verify_chain(truncated, expected_head=head, expected_count=count)[
            "valid"
        ]
        is False
    )


@pytest.mark.unit
def test_concurrent_same_tenant_emits_stay_in_chain_order() -> None:
    """Concurrency must-fix: parallel same-tenant emits reach the transport in chain order."""
    import threading

    sink: list[AuditEvent] = []
    # emit() calls the transport inside the per-tenant lock, so same-tenant appends serialize.
    em = AuditEmitter(transport=sink.append)

    def worker() -> None:
        for _ in range(25):
            em.emit(_event("t"))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(sink) == 100
    result = audit_emitter.verify_chain(sink, expected_count=em.chain_length("t"))
    assert result["valid"] is True


@pytest.mark.unit
def test_parquet_schema_is_stable_across_batches() -> None:
    """Should-fix: an all-None latency_ms batch keeps the same physical schema as a populated one."""
    import pyarrow.parquet as pq

    em = AuditEmitter(transport=lambda e: None)
    populated = [em.emit(_event("a"))]
    none_batch_ev = _event("b")
    none_batch_ev.latency_ms = None
    none_batch = [em.emit(none_batch_ev)]
    s1 = pq.read_table(io.BytesIO(audit_emitter.export_parquet(populated))).schema
    s2 = pq.read_table(io.BytesIO(audit_emitter.export_parquet(none_batch))).schema
    assert s1.equals(s2), "Parquet schema drifts across batches"


@pytest.mark.unit
def test_genesis_event_has_no_prev_hash() -> None:
    sink: list[AuditEvent] = []
    em = AuditEmitter(transport=sink.append)
    first = em.emit(_event("solo"))
    assert first.prev_hash is None and first.event_hash


# ---------------------------------------------------------------------------
# AC-3 — JSON + Parquet export (no raw content)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_export_json_is_schema_valid_and_content_free() -> None:
    events = [_event("t", input_text="SENSITIVE-PHI-123"), _event("t")]
    sealed: list = []
    em = AuditEmitter(transport=sealed.append)
    for e in events:
        em.emit(e)
    raw = audit_emitter.export_json(sealed)
    parsed = json.loads(raw)
    assert len(parsed) == 2
    assert "SENSITIVE-PHI-123" not in raw  # only the hash is present
    assert all("input_hash" in row and "event_hash" in row for row in parsed)


@pytest.mark.unit
def test_export_parquet_is_schema_valid_and_content_free() -> None:
    import pyarrow.parquet as pq

    sealed: list = []
    em = AuditEmitter(transport=sealed.append)
    em.emit(_event("t", input_text="SENSITIVE-PHI-456"))
    blob = audit_emitter.export_parquet(sealed)
    assert isinstance(blob, (bytes, bytearray)) and len(blob) > 0
    table = pq.read_table(io.BytesIO(blob))
    cols = set(table.column_names)
    assert {
        "tenant_id",
        "input_hash",
        "output_hash",
        "event_hash",
        "policy_version",
    } <= cols
    assert b"SENSITIVE-PHI-456" not in blob


# ---------------------------------------------------------------------------
# AC-3/AC-4 — injected transport; retention limited to chain lineage
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_injected_transport_receives_each_event() -> None:
    received: list[AuditEvent] = []
    em = AuditEmitter(transport=received.append)
    em.emit(_event("t"))
    em.emit(_event("t"))
    assert len(received) == 2


@pytest.mark.unit
def test_default_transport_is_a_safe_noop() -> None:
    em = AuditEmitter()  # no transport
    sealed = em.emit(_event("t"))  # must not raise
    assert sealed.event_hash


@pytest.mark.unit
def test_emitter_retains_only_chain_lineage_not_events() -> None:
    """AC-4: SARO retains per-tenant chain lineage (head hash + seq), not the events
    themselves (those are emitted outward; the client SIEM is system-of-record)."""
    em = AuditEmitter(transport=lambda e: None)
    for _ in range(10):
        em.emit(_event("t"))
    state = vars(em)
    # No attribute should hold the full list of emitted events.
    for value in state.values():
        if isinstance(value, list):
            assert all(not isinstance(x, AuditEvent) for x in value), (
                "emitter retains full events"
            )


# ---------------------------------------------------------------------------
# Invariant guards
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_external_model_or_network() -> None:
    import inspect

    src = inspect.getsource(audit_emitter)
    for needle in ("requests", "httpx", "urllib", "anthropic", "openai", "socket"):
        assert needle not in src, (
            f"audit_emitter must not reference {needle} (Epic 14 invariant)"
        )


@pytest.mark.unit
def test_no_overclaim_language() -> None:
    import inspect

    src = inspect.getsource(audit_emitter).lower()
    # Compliance matrix: "tamper-evident" is allowed; "tamper-proof"/"guarantee" are not.
    for phrase in ("tamper-proof", "tamperproof", "guarantee", "immutable storage"):
        assert phrase not in src, f"compliance: audit_emitter must not claim {phrase!r}"
