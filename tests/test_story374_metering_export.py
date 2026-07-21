"""STORY-374 — usage metering delta: exact recount + export.

DELTA on STORY-MTR-001, which already built PHI-free meters, idempotency, and
immutable statements. This covers the three things the pack adds: metering at
the evaluate/attest boundary, a 0%-exact recount, and CSV/JSON export.

The recount is the load-bearing test: metering underlies invoicing, so "close"
is a bug, not a variance.
"""

from __future__ import annotations

import csv
import io
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import sqlalchemy.types as sa_types  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import JSON as PG_JSON  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(bind=engine)

_orig = PG_UUID.__init__
PG_UUID.__init__ = lambda self, *a, **k: (k.pop("as_uuid", None), _orig(self, *a, **k))[1]  # type: ignore
PG_JSON.__init__ = lambda self, *a, **k: sa_types.Text.__init__(self)  # type: ignore

from database import Base  # noqa: E402
import models  # noqa: E402,F401
from models import Audit, ScanReport  # noqa: E402
import services.metering_service as metering  # noqa: E402

Base.metadata.create_all(engine)

pytestmark = pytest.mark.integration

DOC = ROOT / "docs" / "ops" / "usage-metering.md"


@pytest.fixture
def db():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    s = TestingSessionLocal()
    yield s
    s.rollback()
    s.close()


def _period():
    return metering.current_period()


def _seed_attestations(db, tenant_id, n):
    """Create n audits + scan reports — the authoritative attestation rows."""
    for i in range(n):
        audit_id = uuid.uuid4()
        db.add(Audit(id=audit_id, tenant_id=tenant_id, status="complete", sample_count=1))
        db.add(
            ScanReport(
                audit_id=audit_id,
                tenant_id=tenant_id,
                overall_risk_score=0.5,
                report_json={},
                created_at=datetime.now(tz=timezone.utc),
            )
        )
    db.commit()


# ── AC-2: exact recount ─────────────────────────────────────────────────────


def test_meter_matching_the_table_verifies_exactly(db):
    t = uuid.uuid4()
    _seed_attestations(db, t, 3)
    for i in range(3):
        metering.increment(
            db, tenant_id=t, meter_key=metering.ATTESTATIONS_ISSUED,
            idempotency_key=f"a{i}",
        )
    result = metering.verify_exact(db, t)
    attest = [c for c in result["checks"] if c["meter_key"] == metering.ATTESTATIONS_ISSUED][0]
    assert attest["exact"] is True
    assert attest["metered"] == attest["authoritative"] == 3


def test_undercount_fails_the_exact_check(db):
    """A meter one short of the table is a failure, not a tolerable variance."""
    t = uuid.uuid4()
    _seed_attestations(db, t, 5)
    for i in range(4):  # one fewer than the table
        metering.increment(
            db, tenant_id=t, meter_key=metering.ATTESTATIONS_ISSUED,
            idempotency_key=f"a{i}",
        )
    result = metering.verify_exact(db, t)
    assert result["exact"] is False
    attest = [c for c in result["checks"] if c["meter_key"] == metering.ATTESTATIONS_ISSUED][0]
    assert attest["delta"] == -1


def test_overcount_fails_the_exact_check(db):
    t = uuid.uuid4()
    _seed_attestations(db, t, 2)
    for i in range(3):  # one MORE than the table
        metering.increment(
            db, tenant_id=t, meter_key=metering.ATTESTATIONS_ISSUED,
            idempotency_key=f"a{i}",
        )
    result = metering.verify_exact(db, t)
    assert result["exact"] is False


def test_verify_exact_is_period_scoped(db):
    """A meter compared against an all-time count would false-fire across months.

    Seeding creates both an audit and a scan report per row, so BOTH the
    attestations and evaluations meters must be incremented to match — mirroring
    the real boundary, which increments both.
    """
    t = uuid.uuid4()
    _seed_attestations(db, t, 2)
    # a stray meter in a DIFFERENT period must not affect this period's check
    metering.increment(
        db, tenant_id=t, meter_key=metering.ATTESTATIONS_ISSUED,
        period="2000-01", idempotency_key="old",
    )
    for i in range(2):
        metering.increment(
            db, tenant_id=t, meter_key=metering.ATTESTATIONS_ISSUED, idempotency_key=f"a{i}",
        )
        metering.increment(
            db, tenant_id=t, meter_key=metering.EVALUATIONS_EXECUTED, idempotency_key=f"e{i}",
        )
    assert metering.verify_exact(db, t)["exact"] is True


def test_meters_without_an_authoritative_table_are_unverifiable_not_passed(db):
    t = uuid.uuid4()
    metering.increment(
        db, tenant_id=t, meter_key=metering.ADAPTER_OBSERVATION_VOLUME,
        idempotency_key="v1", amount=10,
    )
    result = metering.verify_exact(db, t)
    assert metering.ADAPTER_OBSERVATION_VOLUME in result["unverifiable_meters"]


# ── AC-1: metering the attest boundary ──────────────────────────────────────


def test_attest_boundary_increments_are_idempotent_per_audit(db):
    """Re-submitting the same audit must not double-count (exact recount depends on it)."""
    t = uuid.uuid4()
    aid = uuid.uuid4()
    for _ in range(3):  # same audit id three times
        metering.safe_increment(
            db, tenant_id=t, meter_key=metering.ATTESTATIONS_ISSUED,
            idempotency_key=f"attest:{aid}",
        )
    assert metering.meter_totals(db, t, _period())[metering.ATTESTATIONS_ISSUED] == 1


# ── AC-3: export ────────────────────────────────────────────────────────────


def test_csv_export_has_a_header_and_one_row_per_meter(db):
    t = uuid.uuid4()
    metering.increment(db, tenant_id=t, meter_key=metering.EVALUATIONS_EXECUTED, idempotency_key="e")
    metering.increment(db, tenant_id=t, meter_key=metering.ATTESTATIONS_ISSUED, idempotency_key="a")
    text = metering.export_csv(db, t, _period())
    rows = list(csv.DictReader(io.StringIO(text)))
    assert {r["meter_key"] for r in rows} == {"evaluations_executed", "attestations_issued"}
    assert all(r["tenant_id"] == str(t) for r in rows)


def test_json_export_round_trips(db):
    t = uuid.uuid4()
    metering.increment(db, tenant_id=t, meter_key=metering.EVALUATIONS_EXECUTED, idempotency_key="e", amount=7)
    payload = json.loads(metering.export_json(db, t, _period()))
    assert payload["tenant_id"] == str(t)
    row = [r for r in payload["rows"] if r["meter_key"] == "evaluations_executed"][0]
    assert row["count"] == 7


def test_export_is_stable_ordered_for_diffable_months(db):
    t = uuid.uuid4()
    for key in (metering.ATTESTATIONS_ISSUED, metering.EVALUATIONS_EXECUTED):
        metering.increment(db, tenant_id=t, meter_key=key, idempotency_key=key)
    a = metering.export_csv(db, t, _period())
    b = metering.export_csv(db, t, _period())
    assert a == b
    lines = a.strip().splitlines()
    assert lines[1].split(",")[2] < lines[2].split(",")[2], "rows should be meter-key sorted"


# ── AC-5: PHI-free export (inherited, asserted) ─────────────────────────────


def test_export_columns_are_a_closed_set_with_no_free_text(db):
    t = uuid.uuid4()
    metering.increment(db, tenant_id=t, meter_key=metering.EVALUATIONS_EXECUTED, idempotency_key="e")
    header = metering.export_csv(db, t, _period()).splitlines()[0]
    assert header == "tenant_id,period,meter_key,count", (
        "export columns are fixed and carry no dimension/free-text field"
    )


# ── AC-4: doc says export-only ──────────────────────────────────────────────


def test_doc_states_export_only_no_payment_processor():
    doc = DOC.read_text(encoding="utf-8").lower()
    assert "export only" in doc or "export-only" in doc
    assert "no payment" in doc or "payment processor" in doc
    assert "stripe" in doc, "the later-story boundary should be named explicitly"


def test_doc_explains_the_recount_invariant():
    doc = DOC.read_text(encoding="utf-8").lower()
    assert "recount" in doc
    assert "0%" in doc or "exact" in doc
