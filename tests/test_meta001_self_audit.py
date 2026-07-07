"""STORY-META-001 — SARO self-audit spine.

Covers:
  AC-1  chained content-free events persist for the action classes (metadata only)
  AC-2  immutability is service-enforced (no update path) + chain verify detects tamper
  AC-4  filtered query + chain-verification; export self-references (EXPORT event)
  Edge  fail-closed (record_privileged raises) vs fail-open (record_access swallows)
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
from database import Base, get_db
from main import app
from models import (
    AuditEvent,
    EUAIActRule,
    GovernanceRule,
    GRCEvidenceRecord,
    RulePackSnapshot,
    User,
)
from grc.evidence import EvidenceCapture, capture_evidence
import services.self_audit as sa

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000c1")


# ── service unit ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_events_chain_per_tenant():
    db = _Session()
    try:
        db.query(AuditEvent).delete()
        db.commit()
        e1 = sa.record_event(
            db,
            tenant_id=_TENANT,
            actor="a@x",
            action_class=sa.EXPORT,
            target_type="t",
            target_id="1",
        )
        e2 = sa.record_event(
            db,
            tenant_id=_TENANT,
            actor="a@x",
            action_class=sa.EVIDENCE_ACCESS,
            target_type="t",
            target_id="2",
        )
        assert e1.seq == 1 and e2.seq == 2
        assert e2.prev_hash == e1.event_hash
        assert sa.verify_audit_chain(db, _TENANT)["valid"] is True
    finally:
        db.close()


@pytest.mark.unit
def test_content_free_no_payload():
    db = _Session()
    try:
        db.query(AuditEvent).delete()
        db.commit()
        e = sa.record_event(
            db,
            tenant_id=_TENANT,
            actor="a@x",
            action_class=sa.EVIDENCE_ACCESS,
            target_type="evidence_record",
            target_id="42",
            metadata={"exported_count": 3},
        )
        # Only metadata/hashes — never raw prompt/decision/output.
        assert set(e.event_data.keys()) <= {
            "exported_count",
            "timestamp",
            "content_hash",
        }
    finally:
        db.close()


@pytest.mark.unit
def test_verify_detects_tamper():
    db = _Session()
    try:
        db.query(AuditEvent).delete()
        db.commit()
        e = sa.record_event(
            db,
            tenant_id=_TENANT,
            actor="a@x",
            action_class=sa.ADMIN_ACTION,
            target_type="t",
            target_id="1",
        )
        # Tamper via a raw UPDATE (simulating an out-of-band DB edit bypassing the trigger).
        db.query(AuditEvent).filter(AuditEvent.id == e.id).update(
            {"outcome": "TAMPERED"}
        )
        db.commit()
        assert sa.verify_audit_chain(db, _TENANT)["valid"] is False
    finally:
        db.close()


@pytest.mark.unit
def test_unknown_action_class_rejected():
    db = _Session()
    try:
        with pytest.raises(ValueError):
            sa.record_event(db, tenant_id=_TENANT, actor="a", action_class="NOPE")
    finally:
        db.close()


@pytest.mark.unit
def test_fail_closed_vs_fail_open():
    db = _Session()
    try:
        # record_privileged raises on an unauditable action; record_access swallows.
        with pytest.raises(sa.UnauditableActionError):
            sa.record_privileged(db, tenant_id=_TENANT, actor="a", action_class="NOPE")
        assert (
            sa.record_access(db, tenant_id=_TENANT, actor="a", action_class="NOPE")
            is None
        )
    finally:
        db.close()


@pytest.mark.unit
def test_query_filters():
    db = _Session()
    try:
        db.query(AuditEvent).delete()
        db.commit()
        sa.record_event(
            db,
            tenant_id=_TENANT,
            actor="alice",
            action_class=sa.EXPORT,
            target_type="t",
            target_id="1",
        )
        sa.record_event(
            db,
            tenant_id=_TENANT,
            actor="bob",
            action_class=sa.EVIDENCE_ACCESS,
            target_type="t",
            target_id="2",
        )
        assert len(sa.query_events(db, _TENANT, action_class=sa.EXPORT)) == 1
        assert len(sa.query_events(db, _TENANT, actor="bob")) == 1
    finally:
        db.close()


# ── integration ──────────────────────────────────────────────────────────────
def _user(role="operator", persona="ai_auditor", tenant=None):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "auditor@test.example"
    u.role = role
    u.persona_role = persona
    u.tenant_id = tenant or uuid.uuid4()
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
def test_publish_records_rule_pack_change_and_query_api():
    with _Session() as s:
        for tbl in (AuditEvent, RulePackSnapshot, GovernanceRule, EUAIActRule):
            s.query(tbl).delete()
        s.add(
            EUAIActRule(title="x", description="d", validation_status="SME_VALIDATED")
        )
        s.commit()

    pub = _user(role="operator")
    client = _client(pub)
    r = client.post(
        "/api/v1/rules/versions", json={"version": "1.0.0", "include_legacy": True}
    )
    assert r.status_code == 201, r.text

    # RULE_PACK_CHANGE landed on the system (global) audit chain.
    r = client.get("/api/v1/audit/events?scope=system&action_class=RULE_PACK_CHANGE")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] >= 1
    assert body["chain_verification"]["valid"] is True


@pytest.mark.integration
def test_evidence_read_records_evidence_access():
    tenant = uuid.uuid4()
    with _Session() as s:
        for tbl in (AuditEvent, GRCEvidenceRecord):
            s.query(tbl).delete()
        rec = capture_evidence(
            s,
            tenant_id=tenant,
            capture=EvidenceCapture(
                output_id="o",
                model_version="m",
                prompt="p",
                decision="d",
                confidence=0.5,
                consumer="c",
            ),
        )
        rec_id = str(rec.id)

    client = _client(_user(role="operator", tenant=tenant))
    assert client.get(f"/api/v1/evidence/{rec_id}/criteria").status_code == 200

    r = client.get("/api/v1/audit/events?action_class=EVIDENCE_ACCESS")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


@pytest.mark.integration
def test_export_is_self_referential():
    tenant = uuid.uuid4()
    with _Session() as s:
        s.query(AuditEvent).delete()
        s.commit()
    client = _client(_user(role="operator", tenant=tenant))
    r = client.get("/api/v1/audit/events?export=true")
    assert r.status_code == 200
    assert r.json().get("export_recorded") is True
    # The export created an EXPORT event.
    r2 = client.get("/api/v1/audit/events?action_class=EXPORT")
    assert r2.json()["count"] >= 1


@pytest.mark.integration
def test_system_scope_requires_operator():
    client = _client(_user(role="viewer", persona="ai_auditor"))
    r = client.get("/api/v1/audit/events?scope=system")
    assert r.status_code == 403


# ── AC-5 retention (archival, never deletion) ────────────────────────────────
@pytest.mark.unit
def test_retention_sweep_records_archival_and_never_deletes():
    from datetime import datetime, timedelta, timezone

    db = _Session()
    try:
        db.query(AuditEvent).delete()
        db.commit()
        # Seed a real chained event, then sweep with a 'now' far in the future so it
        # is past the 365-day floor. Nothing is deleted; an archival event is recorded.
        sa.record_event(
            db,
            tenant_id=_TENANT,
            actor="a",
            action_class=sa.EXPORT,
            target_type="t",
            target_id="1",
        )
        future = datetime.now(tz=timezone.utc) + timedelta(days=400)
        count = sa.record_retention_sweep(db, _TENANT, now=future)
        assert count == 1  # the seeded event is a candidate
        # Never deletes: the original event still exists (+ the new archival event).
        assert db.query(AuditEvent).filter(AuditEvent.tenant_id == _TENANT).count() == 2
        archival = sa.query_events(db, _TENANT, action_class=sa.ADMIN_ACTION)
        assert archival and archival[0].target_type == "audit_retention"
    finally:
        db.close()


# ── AC-2/AC-3 Postgres-only DDL guard (complements live Supabase verification) ──
@pytest.mark.unit
def test_migration_033_defines_immutability_and_oob_capture():
    from pathlib import Path

    sql = (
        Path(__file__).parent.parent / "migrations" / "033_self_audit_spine.sql"
    ).read_text(encoding="utf-8")
    assert "trg_audit_events_immutable" in sql  # AC-2 immutability trigger
    assert "audit_events_capture_rule_write" in sql  # AC-3 out-of-band capture
    assert "FOR EACH STATEMENT" in sql  # statement-level (row-count, not per-row)
    assert "system:backfill" in sql and "retroactive" in sql.lower()  # backfill
