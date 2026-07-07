"""STORY-DISP-001 — finding disposition lifecycle.

Covers:
  AC-1  failing finding -> OPEN disposition (de-identified); recurrence links to prior chain
  AC-2  transitions logged in an append-only hash-chained log; illegal transitions rejected
  AC-3  expired WAIVED auto-reopens to OPEN + emits a notification (first notifications consumer)
  AC-4  disposition report (counts, state breakdown, mean-time-to-ack, waivers, lineage)
  AC-5  persona gates; waiver requires justification+approver+expiry; four-eyes; no bulk-waive
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from config import settings
from database import Base, get_db
from main import app
from models import Disposition, DispositionTransition, Notification, User
import services.disposition_service as ds

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000d1")


def _reset(db):
    for tbl in (DispositionTransition, Notification, Disposition):
        db.query(tbl).delete()
    db.commit()


# ── service unit ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_lifecycle_and_transition_chain():
    db = _Session()
    try:
        _reset(db)
        d = ds.create_disposition(
            db,
            tenant_id=_TENANT,
            rule_id="R1",
            system_id="S1",
            gate_id="gate2",
            severity="high",
            actor="a@x",
        )
        assert d.state == ds.OPEN
        ds.acknowledge(db, d, actor="a@x")
        assert d.state == ds.ACKNOWLEDGED and d.acknowledged_at is not None
        ds.remediate(db, d, actor="a@x")
        assert d.state == ds.REMEDIATED
        assert ds.verify_transition_chain(db, d.id)["valid"] is True
    finally:
        db.close()


@pytest.mark.unit
def test_illegal_transition_rejected():
    db = _Session()
    try:
        _reset(db)
        d = ds.create_disposition(
            db, tenant_id=_TENANT, rule_id="R", system_id="S", actor="a"
        )
        with pytest.raises(ds.IllegalTransitionError):
            ds.remediate(db, d, actor="a")  # cannot remediate straight from OPEN
    finally:
        db.close()


@pytest.mark.unit
def test_waiver_requires_fields_and_four_eyes(monkeypatch):
    db = _Session()
    try:
        _reset(db)
        d = ds.create_disposition(
            db, tenant_id=_TENANT, rule_id="R", system_id="S", actor="a"
        )
        ds.acknowledge(db, d, actor="a")
        with pytest.raises(ds.WaiverRequirementError):
            ds.waive(
                db,
                d,
                actor="a",
                justification="",
                approver="b",
                expiry=date.today() + timedelta(days=30),
            )
        monkeypatch.setattr(settings, "saro_disposition_four_eyes", True)
        with pytest.raises(ds.WaiverRequirementError):
            ds.waive(
                db,
                d,
                actor="a",
                justification="ok",
                approver="a",  # approver == actor
                expiry=date.today() + timedelta(days=30),
            )
    finally:
        db.close()


@pytest.mark.unit
def test_expired_waiver_reopens_and_notifies():
    db = _Session()
    try:
        _reset(db)
        d = ds.create_disposition(
            db, tenant_id=_TENANT, rule_id="R", system_id="S", actor="a"
        )
        ds.acknowledge(db, d, actor="a")
        ds.waive(
            db,
            d,
            actor="a",
            justification="accepted risk",
            approver="mgr",
            expiry=date.today() + timedelta(days=5),  # valid future waiver
        )
        assert d.state == ds.WAIVED
        # Sweep with a 'now' past the expiry -> the waiver has lapsed.
        reopened = ds.expire_waivers(db, tenant_id=_TENANT, now=date.today() + timedelta(days=10))
        assert len(reopened) == 1 and reopened[0].state == ds.OPEN
        # First notifications consumer:
        assert (
            db.query(Notification)
            .filter(Notification.type == "disposition_reopened")
            .count()
            == 1
        )
    finally:
        db.close()


@pytest.mark.unit
def test_waiver_expiry_bounds():
    db = _Session()
    try:
        _reset(db)
        d = ds.create_disposition(
            db, tenant_id=_TENANT, rule_id="R", system_id="S", actor="a"
        )
        ds.acknowledge(db, d, actor="a")
        # past expiry rejected
        with pytest.raises(ds.WaiverRequirementError):
            ds.waive(
                db,
                d,
                actor="a",
                justification="j",
                approver="b",
                expiry=date.today() - timedelta(days=1),
            )
        # far-future beyond max horizon rejected
        with pytest.raises(ds.WaiverRequirementError):
            ds.waive(
                db,
                d,
                actor="a",
                justification="j",
                approver="b",
                expiry=date.today() + timedelta(days=100000),
            )
    finally:
        db.close()


@pytest.mark.unit
def test_four_eyes_blocks_approver_equal_acknowledger(monkeypatch):
    db = _Session()
    try:
        _reset(db)
        monkeypatch.setattr(settings, "saro_disposition_four_eyes", True)
        d = ds.create_disposition(
            db, tenant_id=_TENANT, rule_id="R", system_id="S", actor="x"
        )
        ds.acknowledge(db, d, actor="ack@x")  # acknowledger recorded
        assert d.acknowledged_by == "ack@x"
        # A DIFFERENT actor waives, but names the acknowledger as approver -> rejected.
        with pytest.raises(ds.WaiverRequirementError):
            ds.waive(
                db,
                d,
                actor="waiver@x",
                justification="j",
                approver="ack@x",
                expiry=date.today() + timedelta(days=30),
            )
        # A genuinely independent approver is allowed.
        ds.waive(
            db,
            d,
            actor="waiver@x",
            justification="j",
            approver="mgr@x",
            expiry=date.today() + timedelta(days=30),
        )
        assert d.state == ds.WAIVED
    finally:
        db.close()


@pytest.mark.unit
def test_evaluation_failure_opens_disposition():
    """AC-1: a FAIL finding from the audit path opens a disposition linked to evidence."""
    from grc.orchestrator import _open_dispositions_for_failures

    db = _Session()
    try:
        _reset(db)
        ev_id = uuid.uuid4()
        record = MagicMock()
        record.id = ev_id
        result = {
            "findings": [
                {"check": "pii_leak", "disposition": "FAIL", "risk": {"band": "HIGH"}},
                {"check": "ok_check", "disposition": "PASS", "risk": {"band": "LOW"}},
            ]
        }
        _open_dispositions_for_failures(db, _TENANT, record, result, "sys-1")
        disps = db.query(Disposition).filter(Disposition.tenant_id == _TENANT).all()
        assert len(disps) == 1  # only the FAIL finding
        assert disps[0].rule_id == "pii_leak"
        assert disps[0].evidence_record_id == ev_id
        assert disps[0].state == ds.OPEN
    finally:
        db.close()


@pytest.mark.unit
def test_recurrence_links_to_prior_chain():
    db = _Session()
    try:
        _reset(db)
        d1 = ds.create_disposition(
            db, tenant_id=_TENANT, rule_id="R", system_id="S", actor="a"
        )
        d2 = ds.create_disposition(
            db, tenant_id=_TENANT, rule_id="R", system_id="S", actor="a"
        )
        assert d2.id == d1.id  # same active finding -> linked, not duplicated
        assert d2.recurrence_count == 1
    finally:
        db.close()


@pytest.mark.unit
def test_report_shape():
    db = _Session()
    try:
        _reset(db)
        d = ds.create_disposition(
            db, tenant_id=_TENANT, rule_id="R", system_id="S", actor="a"
        )
        ds.acknowledge(db, d, actor="a")
        rep = ds.disposition_report(db, _TENANT)
        assert rep["findings_count"] == 1
        assert rep["state_breakdown"].get("ACKNOWLEDGED") == 1
        assert rep["mean_time_to_acknowledge_seconds"] is not None
    finally:
        db.close()


# ── integration ──────────────────────────────────────────────────────────────
def _user(role="operator", persona="risk_officer", tenant=_TENANT):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "risk@test.example"
    u.role = role
    u.persona_role = persona
    u.tenant_id = tenant
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
def test_api_acknowledge_and_report():
    with _Session() as s:
        _reset(s)
        d = ds.create_disposition(
            s, tenant_id=_TENANT, rule_id="R", system_id="S", actor="seed"
        )
        did = str(d.id)
    client = _client(_user())
    r = client.post(f"/api/v1/dispositions/{did}/acknowledge", json={})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "ACKNOWLEDGED"
    r = client.get("/api/v1/dispositions/report")
    assert r.status_code == 200 and r.json()["findings_count"] == 1


@pytest.mark.integration
def test_api_no_bulk_waive_endpoint():
    # bulk-waive is intentionally not offered (each waiver needs individual justification).
    client = _client(_user())
    r = client.post("/api/v1/dispositions/bulk-waive", json={"disposition_ids": []})
    assert r.status_code in (404, 405)


@pytest.mark.integration
def test_api_cross_tenant_404():
    other = uuid.uuid4()
    with _Session() as s:
        _reset(s)
        d = ds.create_disposition(
            s, tenant_id=other, rule_id="R", system_id="S", actor="x"
        )
        did = str(d.id)
    client = _client(_user(tenant=_TENANT))
    r = client.post(f"/api/v1/dispositions/{did}/acknowledge", json={})
    assert r.status_code == 404
