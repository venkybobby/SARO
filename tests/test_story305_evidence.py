"""STORY-305 — Append-only, tamper-evident evidence store tests.

AC coverage:
- A captured output is retrievable verbatim by id.
- Rows are append-only (DB-layer trigger ships in migration 025; app exposes no
  update/delete path).
- chain_hash correctly chains each row to its predecessor.
- The integrity-verify routine passes on an untampered chain and flags a
  deliberately mutated row.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlalchemy.types as sa_types

_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]
PG_JSON.none_as_null = False

from database import Base  # noqa: E402
from models import GRCEvidenceRecord  # noqa: E402
from grc.evidence import (  # noqa: E402
    GENESIS,
    EvidenceCapture,
    capture_evidence,
    compute_chain_hash,
    compute_content_hash,
    get_evidence,
    verify_chain,
    verify_tenant_chain,
)

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)


def _capture(db, tenant_id, **over) -> GRCEvidenceRecord:
    base: dict = dict(
        output_id="out-1",
        system_id="sys-1",
        model_version="claude-sonnet-4",
        prompt="What is the claim status?",
        retrieved_context="Policy doc chunk 3",
        decision="Approved",
        confidence=0.91,
        consumer="agent-007",
    )
    base.update(over)
    return capture_evidence(db, tenant_id=tenant_id, capture=EvidenceCapture(**base))


# ── Unit: hashing ──────────────────────────────────────────────────────────
@pytest.mark.unit
def test_content_hash_is_deterministic() -> None:
    data = {"output_id": "o", "decision": "x", "confidence": 0.5}
    assert compute_content_hash(data) == compute_content_hash(dict(data))


@pytest.mark.unit
def test_content_hash_changes_with_payload() -> None:
    a = compute_content_hash({"output_id": "o", "decision": "x"})
    b = compute_content_hash({"output_id": "o", "decision": "y"})
    assert a != b


@pytest.mark.unit
def test_chain_hash_links_to_predecessor() -> None:
    c1 = compute_content_hash({"output_id": "1"})
    h1 = compute_chain_hash(c1, GENESIS)
    c2 = compute_content_hash({"output_id": "2"})
    h2 = compute_chain_hash(c2, h1)
    assert h2 == compute_chain_hash(c2, h1)
    assert h1 != h2


# ── Integration: persistence + chain ───────────────────────────────────────
@pytest.mark.integration
def test_capture_and_retrieve_verbatim() -> None:
    tenant = uuid.uuid4()
    db = TestingSessionLocal()
    try:
        rec = _capture(db, tenant, decision="Approved with conditions")
        got = get_evidence(db, tenant_id=tenant, evidence_id=rec.id)
        assert got is not None
        assert got.decision == "Approved with conditions"
        assert got.model_version == "claude-sonnet-4"
    finally:
        db.close()


@pytest.mark.integration
def test_genesis_then_chained() -> None:
    tenant = uuid.uuid4()
    db = TestingSessionLocal()
    try:
        r1 = _capture(db, tenant, output_id="g1")
        assert r1.prev_chain_hash == GENESIS
        assert r1.seq == 1
        r2 = _capture(db, tenant, output_id="g2")
        assert r2.prev_chain_hash == r1.chain_hash
        assert r2.seq == 2
    finally:
        db.close()


@pytest.mark.integration
def test_verify_passes_on_untampered_chain() -> None:
    tenant = uuid.uuid4()
    db = TestingSessionLocal()
    try:
        for i in range(3):
            _capture(db, tenant, output_id=f"clean-{i}")
        result = verify_tenant_chain(db, tenant_id=tenant)
        assert result.valid is True
        assert result.records_checked == 3
    finally:
        db.close()


@pytest.mark.integration
def test_verify_flags_mutated_row() -> None:
    other = uuid.uuid4()
    db = TestingSessionLocal()
    try:
        a = capture_evidence(
            db, tenant_id=other, capture=EvidenceCapture(output_id="m0", decision="A")
        )
        capture_evidence(
            db, tenant_id=other, capture=EvidenceCapture(output_id="m1", decision="B")
        )
        records = (
            db.query(GRCEvidenceRecord)
            .filter(GRCEvidenceRecord.tenant_id == other)
            .order_by(GRCEvidenceRecord.seq.asc())
            .all()
        )
        # Tamper: mutate a persisted field without recomputing its content_hash.
        records[0].decision = "HACKED"
        result = verify_chain(records)
        assert result.valid is False
        assert result.first_broken_id == str(a.id)
        assert "content_hash" in (result.reason or "")
    finally:
        db.close()


@pytest.mark.unit
def test_verify_chain_empty_is_valid() -> None:
    assert verify_chain([]).valid is True


# ── DB-layer append-only enforcement ships in the migration ────────────────
@pytest.mark.unit
def test_migration_declares_append_only_trigger() -> None:
    sql = (
        Path(__file__).parent.parent / "migrations" / "025_grc_evidence_store.sql"
    ).read_text(encoding="utf-8")
    assert "BEFORE UPDATE OR DELETE ON grc_evidence_records" in sql
    assert "append-only" in sql.lower()
