"""STORY-TAB-007: the AIMS model registry must not fabricate classification data.

Pre-fix, GET /api/v1/aims/models stamped every model `risk_tier: "high"` and
`lifecycle_stage: "production"` (constants, admitted by the inline comment) and
`framework_coverage: ["ISO-42001", "EU-AI-ACT-2024"]` (also a constant) — an
ISO 42001 evidence surface presenting values no one ever recorded.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import Base, get_db
from main import app
from models import AIMSDocument, Tenant

pytestmark = [pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()


def _seed() -> None:
    db = _Session()
    db.add(Tenant(id=TENANT_A, name="A", slug="tab007-a"))
    db.add(Tenant(id=TENANT_B, name="B", slug="tab007-b"))
    db.add(AIMSDocument(
        tenant_id=TENANT_A,
        title="Claims triage model",
        version="2.1.0",
        effective_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        owner_email="owner@tenant-a.test",
        linked_audit_ids=[str(uuid.uuid4()), str(uuid.uuid4())],
    ))
    db.add(AIMSDocument(
        tenant_id=TENANT_B,
        title="Other tenant model",
        version="1.0.0",
        owner_email="owner@tenant-b.test",
        linked_audit_ids=[],
    ))
    db.commit()
    db.close()


_seed()


def _user(tenant_id=TENANT_A):
    class _U:
        pass

    u = _U()
    u.id = uuid.uuid4()
    u.role = "operator"
    u.persona_role = "compliance_lead"
    u.tenant_id = tenant_id
    u.is_active = True
    u.read_only = False
    u.email = "u@t.test"
    return u


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def _client_as(user) -> TestClient:
    app.dependency_overrides[get_db] = lambda: _Session()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def test_no_fabricated_classification_fields():
    """AC-1: hardcoded risk_tier / lifecycle_stage / framework_coverage are gone."""
    body = _client_as(_user()).get("/api/v1/aims/models").json()
    assert body["models"], "seeded model missing — fixture broken"
    for model in body["models"]:
        assert "risk_tier" not in model, "fabricated risk_tier still emitted"
        assert "lifecycle_stage" not in model, "fabricated lifecycle_stage still emitted"
        assert "framework_coverage" not in model, "fabricated framework_coverage still emitted"


def test_real_fields_survive():
    """AC-2: the registry keeps every field that comes from stored data."""
    body = _client_as(_user()).get("/api/v1/aims/models").json()
    m = body["models"][0]
    assert m["name"] == "Claims triage model"
    assert m["version"] == "2.1.0"
    assert m["owner_email"] == "owner@tenant-a.test"
    assert m["linked_audit_count"] == 2
    assert m["effective_date"].startswith("2026-05-01")
    assert m["created_at"]


def test_note_has_no_mojibake_prone_chars():
    """AC-5: the note renders without encoding-fragile punctuation."""
    body = _client_as(_user()).get("/api/v1/aims/models").json()
    note = body.get("note", "")
    assert "—" not in note and "â€" not in note, f"mojibake-prone note: {note!r}"
    assert note.isascii(), f"non-ascii note: {note!r}"


def test_tenant_scoping_unchanged():
    """Regression guard: the registry stays scoped to the JWT's tenant."""
    body = _client_as(_user(TENANT_A)).get("/api/v1/aims/models").json()
    titles = {m["name"] for m in body["models"]}
    assert "Other tenant model" not in titles


def test_cross_tenant_query_param_is_ignored():
    """The hostile form: a TENANT_A user requesting ?tenant_id=<TENANT_B>
    still gets only TENANT_A's models — the query param is display-compat
    only and never widens scope."""
    body = (
        _client_as(_user(TENANT_A))
        .get(f"/api/v1/aims/models?tenant_id={TENANT_B}")
        .json()
    )
    titles = {m["name"] for m in body["models"]}
    assert "Other tenant model" not in titles
    assert body["tenant_id"] == str(TENANT_A)
