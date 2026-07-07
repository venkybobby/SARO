"""STORY-RPV-002 — reproduction + evidence-criteria API (integration).

* GET /api/v1/rules/versions/{version}/reproduce -> frozen content (AC-3)
* GET /api/v1/evidence/{id}/criteria -> reproduction for a pinned record (AC-3)
* GET /api/v1/evidence/{id}/criteria -> PRE-VERSIONING for an unpinned record (AC-4)
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
from grc.evidence import EvidenceCapture, capture_evidence
from main import app
from models import (
    EUAIActRule,
    GovernanceRule,
    GRCEvidenceRecord,
    RulePackSnapshot,
    User,
)
import services.rule_pack_snapshot_service as svc

pytestmark = [pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000bb")


def _user(tenant_id=_TENANT):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "aud@test.example"
    u.role = "operator"
    u.persona_role = "ai_auditor"
    u.tenant_id = tenant_id
    u.is_active = True
    u.read_only = False
    return u


def _client(user=None):
    if user is None:
        user = _user()

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


def test_evidence_criteria_cross_tenant_is_404():
    """Security should-fix #1: tenant B cannot read tenant A's evidence criteria.

    Same generic 404 as a nonexistent id — no cross-tenant existence oracle.
    """
    tenant_a = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
    with _Session() as s:
        for tbl in (GRCEvidenceRecord, RulePackSnapshot, GovernanceRule, EUAIActRule):
            s.query(tbl).delete()
        s.commit()
        rec = capture_evidence(
            s,
            tenant_id=tenant_a,
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

    # Caller is tenant B — must not see tenant A's record.
    tenant_b = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
    client = _client(_user(tenant_id=tenant_b))
    r = client.get(f"/api/v1/evidence/{rec_id}/criteria")
    assert r.status_code == 404
    assert r.json()["detail"] == "evidence record not found"


def test_reproduce_route_not_shadowed_by_version_route():
    """Security should-fix #2: /{version}/reproduce must not be shadowed by /{version}."""
    with _Session() as s:
        for tbl in (RulePackSnapshot, GovernanceRule, EUAIActRule):
            s.query(tbl).delete()
        s.add(
            EUAIActRule(title="X", description="d", validation_status="SME_VALIDATED")
        )
        s.commit()
        svc.publish_snapshot(s, version="1.0.0", include_legacy=True)

    client = _client()
    r = client.get("/api/v1/rules/versions/1.0.0/reproduce")
    assert r.status_code == 200
    # The reproduce payload has 'frameworks'; the /{version} serialization does not.
    assert "frameworks" in r.json()


def test_reproduce_version_and_evidence_criteria():
    with _Session() as s:
        for tbl in (GRCEvidenceRecord, RulePackSnapshot, GovernanceRule, EUAIActRule):
            s.query(tbl).delete()
        s.add(
            EUAIActRule(
                title="FROZEN", description="d", validation_status="SME_VALIDATED"
            )
        )
        s.add(
            GovernanceRule(
                rule_id="g", description="d", validation_status="SME_VALIDATED"
            )
        )
        s.commit()
        svc.publish_snapshot(s, version="1.0.0", include_legacy=True)
        rec = capture_evidence(
            s,
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
        rec_id = str(rec.id)

    client = _client()
    r = client.get("/api/v1/rules/versions/1.0.0/reproduce")
    assert r.status_code == 200, r.text
    assert any(
        row["title"] == "FROZEN" for row in r.json()["frameworks"]["eu_ai_act_rules"]
    )

    r = client.get(f"/api/v1/evidence/{rec_id}/criteria")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rule_pack_version_id"] == "1.0.0"
    assert body["pin_matches_snapshot"] is True


def test_evidence_criteria_pre_versioning():
    with _Session() as s:
        for tbl in (GRCEvidenceRecord, RulePackSnapshot, GovernanceRule, EUAIActRule):
            s.query(tbl).delete()
        s.commit()
        # No published snapshot -> capture yields a PRE-VERSIONING (unpinned) record.
        rec = capture_evidence(
            s,
            tenant_id=_TENANT,
            capture=EvidenceCapture(
                output_id="o2",
                model_version="m",
                prompt="p",
                decision="d",
                confidence=0.5,
                consumer="c",
            ),
        )
        rec_id = str(rec.id)

    client = _client()
    r = client.get(f"/api/v1/evidence/{rec_id}/criteria")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rule_pack_version_id"] == "PRE-VERSIONING"
    assert body["reproduction_available"] is False
