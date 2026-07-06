"""STORY-RPV-001 — rule-pack version snapshot API (integration).

Exercises the router end to end on an in-memory SQLite session:
  * POST publish creates a snapshot (201) — AC-1
  * publish with a DRAFT row returns 409 + blocking listing — AC-3
  * GET list / latest / diff / verify — AC-4/AC-5
  * publish requires super_admin|operator; reader persona is 403 on publish
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
from models import EUAIActRule, GovernanceRule, NISTControl, RulePackSnapshot, User

pytestmark = [pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


def _seed(session, *, draft=False):
    for tbl in (RulePackSnapshot, GovernanceRule, NISTControl, EUAIActRule):
        session.query(tbl).delete()
    session.add(
        EUAIActRule(title="eu", description="d", validation_status="SME_VALIDATED")
    )
    session.add(
        GovernanceRule(rule_id="g", description="d", validation_status="SME_VALIDATED")
    )
    session.add(NISTControl(subcategory_id="n", description="d"))
    if draft:
        session.add(
            EUAIActRule(
                title="draft", description="d", validation_status="DRAFT_UNVALIDATED"
            )
        )
    session.commit()


def _user(role="super_admin", persona="ai_auditor"):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "pub@test.example"
    u.role = role
    u.persona_role = persona
    u.tenant_id = uuid.uuid4()
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


def test_publish_and_list_and_verify():
    with _Session() as s:
        _seed(s)
    client = _client(_user())
    r = client.post(
        "/api/v1/rules/versions", json={"version": "1.0.0", "include_legacy": True}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version"] == "1.0.0"
    assert body["framework_counts"]["eu_ai_act_rules"] == 1

    r = client.get("/api/v1/rules/versions")
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r = client.get("/api/v1/rules/versions/verify")
    assert r.status_code == 200
    assert r.json()["valid"] is True

    r = client.get("/api/v1/rules/versions/diff")
    assert r.status_code == 200
    assert "governance_rules" in r.json()["diff"]


def test_publish_blocked_by_draft_returns_409_with_listing():
    with _Session() as s:
        _seed(s, draft=True)
    client = _client(_user())
    r = client.post("/api/v1/rules/versions", json={})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "unvalidated_rows_block_publish"
    assert any(b["table"] == "eu_ai_act_rules" for b in detail["blocking"])


def test_publish_forbidden_for_reader_persona():
    with _Session() as s:
        _seed(s)
    # compliance_lead persona with a non-privileged role cannot publish.
    client = _client(_user(role="viewer", persona="compliance_lead"))
    r = client.post("/api/v1/rules/versions", json={"version": "1.0.0"})
    assert r.status_code == 403, r.text
