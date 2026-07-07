"""STORY-MTR-001 — PHI-free usage metering.

Covers:
  AC-1  PHI-free by construction: closed meter/dimension vocabulary; free-text rejected
  AC-2  idempotent increments (retry-safe); best-effort never raises
  AC-3  immutable usage statement with content hash (reissue returns the same artifact)
  AC-4  threshold crossing records + notifies, never a cutoff
  AC-5  reconciliation flags drift beyond tolerance as a data-quality finding
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from config import settings
from database import Base, get_db
from grc.evidence import EvidenceCapture, capture_evidence
from main import app
from models import (
    GRCEvidenceRecord,
    Notification,
    UsageMeter,
    UsageStatement,
    User,
)
import services.metering_service as m

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

# NB: avoid an all-numeric or exponent-like ('...e1') UUID — SQLite NUMERIC affinity
# would coerce it to an int on readback in the test harness (real Postgres is fine).
_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000f1")
_P = "2026-07"


def _reset(db):
    for tbl in (UsageMeter, UsageStatement, Notification, GRCEvidenceRecord):
        db.query(tbl).delete()
    db.query(m.UsageMeterIdempotency).delete()
    db.commit()


# ── AC-1 closed vocabulary ───────────────────────────────────────────────────
@pytest.mark.unit
def test_unknown_meter_key_and_dimension_rejected():
    db = _Session()
    try:
        _reset(db)
        with pytest.raises(m.MeteringError):
            m.increment(db, tenant_id=_TENANT, meter_key="free_text_key", period=_P)
        with pytest.raises(m.MeteringError):
            m.increment(
                db,
                tenant_id=_TENANT,
                meter_key=m.EVALUATIONS_EXECUTED,
                period=_P,
                dimensions={"prompt": "raw pii here"},
            )
    finally:
        db.close()


# ── AC-2 idempotency + best-effort ───────────────────────────────────────────
@pytest.mark.unit
def test_increment_and_idempotency():
    db = _Session()
    try:
        _reset(db)
        m.increment(
            db,
            tenant_id=_TENANT,
            meter_key=m.EVALUATIONS_EXECUTED,
            period=_P,
            idempotency_key="inv-1",
        )
        # retry with same key -> deduped, count stays 1
        assert (
            m.increment(
                db,
                tenant_id=_TENANT,
                meter_key=m.EVALUATIONS_EXECUTED,
                period=_P,
                idempotency_key="inv-1",
            )
            is None
        )
        assert m.meter_totals(db, _TENANT, _P)[m.EVALUATIONS_EXECUTED] == 1
    finally:
        db.close()


@pytest.mark.unit
def test_safe_increment_never_raises():
    db = _Session()
    try:
        _reset(db)
        # invalid key would raise in increment(); safe_increment swallows it.
        m.safe_increment(db, tenant_id=_TENANT, meter_key="bogus", period=_P)
        assert m.meter_totals(db, _TENANT, _P) == {}
    finally:
        db.close()


@pytest.mark.unit
def test_dimension_values_bounded():
    """AC-1 by construction: values (not just keys) are bounded — no payload smuggling."""
    db = _Session()
    try:
        _reset(db)
        # over-length value
        with pytest.raises(m.MeteringError):
            m.increment(
                db,
                tenant_id=_TENANT,
                meter_key=m.EVALUATIONS_EXECUTED,
                period=_P,
                dimensions={"gate_id": "x" * 200},
            )
        # non-scalar value
        with pytest.raises(m.MeteringError):
            m.increment(
                db,
                tenant_id=_TENANT,
                meter_key=m.EVALUATIONS_EXECUTED,
                period=_P,
                dimensions={"gate_id": {"raw": "content"}},
            )
        # value outside the closed allow-list for 'outcome'
        with pytest.raises(m.MeteringError):
            m.increment(
                db,
                tenant_id=_TENANT,
                meter_key=m.EVALUATIONS_EXECUTED,
                period=_P,
                dimensions={"outcome": "SECRET_PAYLOAD"},
            )
    finally:
        db.close()


@pytest.mark.unit
def test_safe_increment_fires_threshold(monkeypatch):
    """AC-4 wired: safe_increment triggers the threshold notification at runtime."""
    db = _Session()
    try:
        _reset(db)
        monkeypatch.setattr(
            settings, "saro_metering_thresholds", {m.EVALUATIONS_EXECUTED: 1}
        )
        m.safe_increment(
            db, tenant_id=_TENANT, meter_key=m.EVALUATIONS_EXECUTED, period=_P
        )
        assert (
            db.query(Notification)
            .filter(Notification.type == "usage_threshold")
            .count()
            == 1
        )
    finally:
        db.close()


@pytest.mark.unit
def test_eval_style_idempotency_dedup():
    db = _Session()
    try:
        _reset(db)
        m.safe_increment(
            db,
            tenant_id=_TENANT,
            meter_key=m.EVALUATIONS_EXECUTED,
            period=_P,
            idempotency_key="eval:rec-1",
        )
        m.safe_increment(
            db,
            tenant_id=_TENANT,
            meter_key=m.EVALUATIONS_EXECUTED,
            period=_P,
            idempotency_key="eval:rec-1",
        )  # retry
        assert m.meter_totals(db, _TENANT, _P)[m.EVALUATIONS_EXECUTED] == 1
    finally:
        db.close()


@pytest.mark.unit
def test_high_water_mark():
    db = _Session()
    try:
        _reset(db)
        m.record_high_water(
            db,
            tenant_id=_TENANT,
            meter_key=m.ACTIVE_OBSERVED_SYSTEMS,
            value=5,
            period=_P,
        )
        m.record_high_water(
            db,
            tenant_id=_TENANT,
            meter_key=m.ACTIVE_OBSERVED_SYSTEMS,
            value=3,
            period=_P,
        )
        assert (
            m.meter_totals(db, _TENANT, _P)[m.ACTIVE_OBSERVED_SYSTEMS] == 5
        )  # max, not sum
    finally:
        db.close()


# ── AC-3 immutable statement ─────────────────────────────────────────────────
@pytest.mark.unit
def test_statement_hash_and_immutable_reissue():
    db = _Session()
    try:
        _reset(db)
        m.increment(db, tenant_id=_TENANT, meter_key=m.EVALUATIONS_EXECUTED, period=_P)
        s1 = m.generate_statement(db, _TENANT, _P)
        assert len(s1.content_hash) == 64 and s1.totals[m.EVALUATIONS_EXECUTED] == 1
        # Reissue returns the SAME already-issued artifact (immutable once issued).
        s2 = m.generate_statement(db, _TENANT, _P)
        assert s2.id == s1.id and s2.content_hash == s1.content_hash
    finally:
        db.close()


# ── AC-4 threshold (records + notifies, no cutoff) ───────────────────────────
@pytest.mark.unit
def test_threshold_records_and_notifies_without_cutoff(monkeypatch):
    db = _Session()
    try:
        _reset(db)
        monkeypatch.setattr(
            settings, "saro_metering_thresholds", {m.EVALUATIONS_EXECUTED: 2}
        )
        m.increment(
            db, tenant_id=_TENANT, meter_key=m.EVALUATIONS_EXECUTED, period=_P, amount=3
        )
        crossed = m.check_threshold(db, _TENANT, m.EVALUATIONS_EXECUTED, period=_P)
        assert crossed is True
        assert (
            db.query(Notification)
            .filter(Notification.type == "usage_threshold")
            .count()
            == 1
        )
        # No cutoff: metering still accepts further increments.
        m.increment(db, tenant_id=_TENANT, meter_key=m.EVALUATIONS_EXECUTED, period=_P)
        assert m.meter_totals(db, _TENANT, _P)[m.EVALUATIONS_EXECUTED] == 4
    finally:
        db.close()


# ── AC-5 reconciliation ──────────────────────────────────────────────────────
@pytest.mark.unit
def test_reconcile_flags_drift():
    db = _Session()
    try:
        _reset(db)
        # 3 authoritative evidence rows, but meter says 0 -> 100% drift.
        for i in range(3):
            db.add(
                GRCEvidenceRecord(
                    tenant_id=_TENANT,
                    output_id=f"o{i}",
                    seq=i + 1,
                    content_hash="c",
                    prev_chain_hash="GENESIS",
                    chain_hash="h",
                )
            )
        db.commit()
        rep = m.reconcile(db, _TENANT, _P)
        assert rep["within_tolerance"] is False and rep["authoritative"] == 3
        assert (
            db.query(Notification).filter(Notification.type == "data_quality").count()
            == 1
        )
    finally:
        db.close()


@pytest.mark.unit
def test_reconcile_is_period_scoped():
    """Reviewer B1: a monthly meter must reconcile against the SAME month's authoritative
    count, not the all-time count (else it false-fires once a tenant spans >1 period)."""
    from datetime import datetime, timezone

    db = _Session()
    try:
        _reset(db)
        # 1 evidence row in July, 1 in August (all-time = 2).
        db.add(
            GRCEvidenceRecord(
                tenant_id=_TENANT,
                output_id="jul",
                seq=1,
                content_hash="c",
                prev_chain_hash="GENESIS",
                chain_hash="h",
                created_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
            )
        )
        db.add(
            GRCEvidenceRecord(
                tenant_id=_TENANT,
                output_id="aug",
                seq=2,
                content_hash="c",
                prev_chain_hash="GENESIS",
                chain_hash="h",
                created_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
            )
        )
        db.commit()
        # Meter July = 1 (matches July's authoritative count of 1) -> no drift, no false finding.
        m.increment(
            db,
            tenant_id=_TENANT,
            meter_key=m.EVIDENCE_RECORDS_PERSISTED,
            period="2026-07",
        )
        rep = m.reconcile(db, _TENANT, "2026-07")
        assert rep["authoritative"] == 1 and rep["metered"] == 1
        assert rep["within_tolerance"] is True
        assert (
            db.query(Notification).filter(Notification.type == "data_quality").count()
            == 0
        )
    finally:
        db.close()


@pytest.mark.unit
def test_capture_evidence_meters_persistence():
    db = _Session()
    try:
        _reset(db)
        capture_evidence(
            db,
            tenant_id=_TENANT,
            capture=EvidenceCapture(
                output_id="o",
                model_version="m",
                prompt="p",
                decision="d",
                confidence=0.5,
                consumer="c",
            ),
        )
        period = m.current_period()
        assert (
            m.meter_totals(db, _TENANT, period).get(m.EVIDENCE_RECORDS_PERSISTED) == 1
        )
    finally:
        db.close()


# ── integration ──────────────────────────────────────────────────────────────
def _user(role="operator", persona="admin"):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "founder@test.example"
    u.role = role
    u.persona_role = persona
    u.tenant_id = _TENANT
    u.is_active = True
    u.read_only = False
    return u


def _client(user):
    def _get_db():
        db = _Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


@pytest.mark.integration
def test_api_usage_and_statement():
    with _Session() as s:
        _reset(s)
        m.increment(
            s,
            tenant_id=_TENANT,
            meter_key=m.EVALUATIONS_EXECUTED,
            period=m.current_period(),
        )
    client = _client(_user())
    r = client.get("/api/v1/metering/usage")
    assert r.status_code == 200, r.text
    assert r.json()["totals"].get("evaluations_executed") == 1
    r = client.post("/api/v1/metering/statement")
    assert r.status_code == 200
    assert len(r.json()["content_hash"]) == 64


@pytest.mark.integration
def test_api_requires_privilege():
    client = _client(_user(role="viewer", persona="compliance_lead"))
    r = client.get("/api/v1/metering/usage")
    assert r.status_code == 403
