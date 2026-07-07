"""STORY-COV-001 — observation-gap (coverage) attestations (adapter-independent core).

Covers:
  AC-1/AC-2  checkpoint interface (idempotent); a stale (system,adapter) opens a gap; cause UNKNOWN
  AC-3       a resuming checkpoint closes the gap with duration + watermark delta
  AC-4       coverage report: % under observation, gaps w/ causes, max lag, methodology
  AC-5       lag p50/p95/max recorded as measured evidence
  Edge       SARO_OUTAGE self-detect (retroactive); PLANNED_MAINTENANCE w/ approver; idempotent re-read
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import Base, get_db
from main import app
from models import ObservationCheckpoint, ObservationGap, ObservationLagSample, User
import services.observation_coverage_service as cov

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

# Non-exponent-like UUID (avoid SQLite NUMERIC affinity coercion).
_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000fa")
_NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _reset(db):
    for tbl in (ObservationCheckpoint, ObservationGap, ObservationLagSample):
        db.query(tbl).delete()
    db.commit()


def _cp(db, ts, pos):
    return cov.record_checkpoint(
        db,
        tenant_id=_TENANT,
        system_id="sys-1",
        adapter_id="bedrock",
        watermark_position=pos,
        watermark_timestamp=ts,
    )


# ── AC-1/AC-2 checkpoint + gap open ──────────────────────────────────────────
@pytest.mark.unit
def test_checkpoint_idempotent_and_gap_opens_when_stale():
    db = _Session()
    try:
        _reset(db)
        assert _cp(db, _NOW - timedelta(hours=1), "pos-1") is not None
        assert _cp(db, _NOW - timedelta(hours=1), "pos-1") is None  # idempotent re-read
        # Latest checkpoint is 1h old, cadence 300s -> stale -> gap opens (UNKNOWN).
        opened = cov.detect_gaps(db, tenant_id=_TENANT, now=_NOW, cadence_seconds=300)
        assert len(opened) == 1 and opened[0].cause_class == cov.UNKNOWN
        # A second detect doesn't double-open (one open gap already).
        assert (
            cov.detect_gaps(db, tenant_id=_TENANT, now=_NOW, cadence_seconds=300) == []
        )
    finally:
        db.close()


# ── AC-3 resume closes the gap ───────────────────────────────────────────────
@pytest.mark.unit
def test_resuming_checkpoint_closes_gap():
    db = _Session()
    try:
        _reset(db)
        _cp(db, _NOW - timedelta(hours=2), "pos-1")
        cov.detect_gaps(db, tenant_id=_TENANT, now=_NOW, cadence_seconds=300)
        # Observation resumes.
        _cp(db, _NOW, "pos-2")
        gap = db.query(ObservationGap).first()
        assert gap.gap_end is not None and gap.duration_seconds > 0
        assert gap.watermark_end == "pos-2"
    finally:
        db.close()


@pytest.mark.unit
def test_diagnose_gap_sets_cause():
    db = _Session()
    try:
        _reset(db)
        _cp(db, _NOW - timedelta(hours=1), "pos-1")
        opened = cov.detect_gaps(db, tenant_id=_TENANT, now=_NOW, cadence_seconds=300)
        cov.diagnose_gap(db, opened[0].id, cov.CREDENTIAL_EXPIRY)
        assert db.get(ObservationGap, opened[0].id).cause_class == cov.CREDENTIAL_EXPIRY
        with pytest.raises(cov.CoverageError):
            cov.diagnose_gap(db, opened[0].id, "BOGUS_CAUSE")
    finally:
        db.close()


# ── edges: SARO_OUTAGE + planned maintenance ─────────────────────────────────
@pytest.mark.unit
def test_saro_outage_is_retroactive():
    db = _Session()
    try:
        _reset(db)
        g = cov.detect_saro_outage(
            db,
            tenant_id=_TENANT,
            system_id="sys-1",
            adapter_id="bedrock",
            downtime_start=_NOW - timedelta(minutes=30),
            downtime_end=_NOW,
        )
        assert g.cause_class == cov.SARO_OUTAGE and g.retroactive is True
        assert g.duration_seconds == 1800
    finally:
        db.close()


@pytest.mark.unit
def test_planned_maintenance_has_approver():
    db = _Session()
    try:
        _reset(db)
        g = cov.declare_maintenance(
            db,
            tenant_id=_TENANT,
            system_id="sys-1",
            adapter_id="bedrock",
            start=_NOW,
            end=_NOW + timedelta(hours=1),
            approver="ops@x",
        )
        assert g.cause_class == cov.PLANNED_MAINTENANCE and g.approver == "ops@x"
    finally:
        db.close()


# ── AC-5 lag ─────────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_lag_percentiles():
    db = _Session()
    try:
        _reset(db)
        row = cov.record_lag_sample(
            db,
            tenant_id=_TENANT,
            system_id="sys-1",
            adapter_id="bedrock",
            window_bucket="2026-07-07T12",
            samples_ms=[100, 200, 300, 400, 1000],
        )
        assert row.p50_ms == 300 and row.max_ms == 1000 and row.p95_ms >= 400
    finally:
        db.close()


# ── AC-4 coverage report ─────────────────────────────────────────────────────
@pytest.mark.unit
def test_coverage_report_percentage():
    db = _Session()
    try:
        _reset(db)
        start = _NOW - timedelta(hours=10)
        end = _NOW
        # One 1-hour gap in a 10-hour window -> 90% coverage.
        db.add(
            ObservationGap(
                tenant_id=_TENANT,
                system_id="sys-1",
                adapter_id="bedrock",
                gap_start=_NOW - timedelta(hours=5),
                gap_end=_NOW - timedelta(hours=4),
                cause_class=cov.ADAPTER_FAILURE,
            )
        )
        # Lag sample recorded WITHIN the window (max lag is window-bounded).
        db.add(
            ObservationLagSample(
                tenant_id=_TENANT,
                system_id="sys-1",
                adapter_id="bedrock",
                window_bucket="w",
                p50_ms=50,
                p95_ms=900,
                max_ms=900,
                recorded_at=_NOW - timedelta(hours=3),
            )
        )
        db.commit()
        rep = cov.coverage_report(db, _TENANT, "sys-1", start, end)
        assert rep["coverage_pct"] == 90.0
        assert rep["max_observation_lag_ms"] == 900
        assert len(rep["gaps"]) == 1 and "methodology" in rep
    finally:
        db.close()


# ── integration ──────────────────────────────────────────────────────────────
def _user(role="operator", persona="ai_auditor"):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "ciso@test.example"
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
def test_api_checkpoint_and_report():
    with _Session() as s:
        _reset(s)
    client = _client(_user())
    r = client.post(
        "/api/v1/observation-coverage/checkpoint",
        json={
            "system_id": "sys-1",
            "adapter_id": "bedrock",
            "watermark_position": "pos-1",
            "watermark_timestamp": _NOW.isoformat(),
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["recorded"] is True
    r = client.get(
        "/api/v1/observation-coverage/report",
        params={
            "system_id": "sys-1",
            "start": (_NOW - timedelta(hours=1)).isoformat(),
            "end": _NOW.isoformat(),
        },
    )
    assert r.status_code == 200, r.text
    assert "coverage_pct" in r.json()


@pytest.mark.integration
def test_api_checkpoint_requires_operator():
    client = _client(_user(role="viewer", persona="compliance_lead"))
    r = client.post(
        "/api/v1/observation-coverage/checkpoint",
        json={
            "system_id": "s",
            "adapter_id": "a",
            "watermark_position": "p",
            "watermark_timestamp": _NOW.isoformat(),
        },
    )
    assert r.status_code == 403


# ── AC-3 gap evidence hash chain ─────────────────────────────────────────────
@pytest.mark.unit
def test_gap_chain_finalizes_and_detects_tamper():
    db = _Session()
    try:
        _reset(db)
        cov.declare_maintenance(
            db,
            tenant_id=_TENANT,
            system_id="sys-1",
            adapter_id="bedrock",
            start=_NOW,
            end=_NOW + timedelta(hours=1),
            approver="ops",
        )
        cov.detect_saro_outage(
            db,
            tenant_id=_TENANT,
            system_id="sys-1",
            adapter_id="bedrock",
            downtime_start=_NOW - timedelta(hours=2),
            downtime_end=_NOW,
        )
        assert cov.verify_gap_chain(db, _TENANT)["valid"] is True
        # Tamper a finalized gap's cause without re-sealing -> chain breaks.
        g = db.query(ObservationGap).first()
        db.query(ObservationGap).filter(ObservationGap.id == g.id).update(
            {"cause_class": "UNKNOWN"}
        )
        db.commit()
        assert cov.verify_gap_chain(db, _TENANT)["valid"] is False
    finally:
        db.close()


# ── AC-4 overlapping gaps counted as UNION (reviewer S2) ─────────────────────
@pytest.mark.unit
def test_coverage_union_no_double_count():
    db = _Session()
    try:
        _reset(db)
        start, end = _NOW - timedelta(hours=10), _NOW
        # Two OVERLAPPING gaps (different adapters): 5h->3h ago and 4h->2h ago.
        # Union blind = 5h->2h = 3h -> 70% coverage (NOT 60% from naive summing).
        db.add(
            ObservationGap(
                tenant_id=_TENANT,
                system_id="sys-1",
                adapter_id="a1",
                gap_start=_NOW - timedelta(hours=5),
                gap_end=_NOW - timedelta(hours=3),
                cause_class=cov.ADAPTER_FAILURE,
            )
        )
        db.add(
            ObservationGap(
                tenant_id=_TENANT,
                system_id="sys-1",
                adapter_id="a2",
                gap_start=_NOW - timedelta(hours=4),
                gap_end=_NOW - timedelta(hours=2),
                cause_class=cov.SOURCE_UNAVAILABLE,
            )
        )
        db.commit()
        rep = cov.coverage_report(db, _TENANT, "sys-1", start, end)
        assert rep["coverage_pct"] == 70.0
    finally:
        db.close()


@pytest.mark.integration
def test_api_rejects_freetext_watermark():
    """INV-2: an over-long / free-text watermark_position is rejected (no PII smuggling)."""
    client = _client(_user())
    r = client.post(
        "/api/v1/observation-coverage/checkpoint",
        json={
            "system_id": "sys-1",
            "adapter_id": "bedrock",
            "watermark_position": "SSN=123-45-6789 patient note here",
            "watermark_timestamp": _NOW.isoformat(),
        },
    )
    assert r.status_code == 422
