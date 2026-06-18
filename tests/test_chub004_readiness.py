"""CHUB-004: Compliance Hub readiness checklist — persistence, tenant scoping,
derived items. In-memory SQLite (no live DB), mirroring tests/test_evf_sprint3.py.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── SQLite setup: neutralise Postgres-only column types ───────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON as PG_JSON
import sqlalchemy.types as sa_types

# StaticPool + a single shared connection so the FastAPI handler thread and the
# test thread see the same in-memory DB (TestClient runs requests off-thread).
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)

_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]

from database import Base, get_db  # noqa: E402
import models  # noqa: E402,F401
from models import AIMSDocument, User  # noqa: E402
from services.readiness_service import (  # noqa: E402
    _resolve_aims_inventory,
    get_readiness,
    set_readiness,
)

Base.metadata.create_all(engine)

pytestmark = pytest.mark.integration

_TENANT_A = uuid.uuid4()
_TENANT_B = uuid.uuid4()


@pytest.fixture
def db():
    s = TestingSessionLocal()
    try:
        # clean slate per test
        from models import ComplianceReadinessItem

        s.query(ComplianceReadinessItem).delete()
        s.query(AIMSDocument).delete()
        s.commit()
        yield s
    finally:
        s.close()


# ── Service layer ─────────────────────────────────────────────────────────────


def test_empty_store_manual_unchecked_derived_from_source(db):
    items = get_readiness(db, _TENANT_A)
    by_key = {it["key"]: it for it in items}
    assert by_key["dpa_in_place"]["completed"] is False
    assert by_key["dpa_in_place"]["editable"] is True
    # derived item: no AIMS rows → not completed, read-only, has a source tooltip
    ai = by_key["ai_systems_registered"]
    assert ai["completed"] is False
    assert ai["editable"] is False
    assert ai["source"]


def test_set_readiness_persists_across_fresh_query(db):
    set_readiness(db, _TENANT_A, "dpa_in_place", True)
    # fresh read
    items = {it["key"]: it for it in get_readiness(db, _TENANT_A)}
    assert items["dpa_in_place"]["completed"] is True
    # toggle back off
    set_readiness(db, _TENANT_A, "dpa_in_place", False)
    items = {it["key"]: it for it in get_readiness(db, _TENANT_A)}
    assert items["dpa_in_place"]["completed"] is False


def test_set_readiness_rejects_derived_item(db):
    with pytest.raises(ValueError):
        set_readiness(db, _TENANT_A, "ai_systems_registered", True)


def test_set_readiness_rejects_unknown_item(db):
    with pytest.raises(ValueError):
        set_readiness(db, _TENANT_A, "does_not_exist", True)


def test_tenant_isolation_no_foreign_state(db):
    set_readiness(db, _TENANT_A, "dpa_in_place", True)
    b_items = {it["key"]: it for it in get_readiness(db, _TENANT_B)}
    assert b_items["dpa_in_place"]["completed"] is False, (
        "tenant B must not see A's state"
    )


def test_derived_completed_when_aims_records_exist(db):
    db.add(
        AIMSDocument(
            tenant_id=_TENANT_A,
            title="AIMS Policy",
            version="1.0.0",
            owner_email="o@x.com",
        )
    )
    db.commit()
    items = {it["key"]: it for it in get_readiness(db, _TENANT_A)}
    assert items["ai_systems_registered"]["completed"] is True
    # other tenant still sees it as not-completed (tenant-scoped derive)
    b = {it["key"]: it for it in get_readiness(db, _TENANT_B)}
    assert b["ai_systems_registered"]["completed"] is False


def test_derived_resolver_unknown_on_source_error():
    broken = MagicMock()
    broken.query.side_effect = RuntimeError("db down")
    assert _resolve_aims_inventory(broken, _TENANT_A) is None  # unknown, never True


# ── Router layer ──────────────────────────────────────────────────────────────

from fastapi.testclient import TestClient  # noqa: E402
from auth import get_current_user  # noqa: E402
from main import app  # noqa: E402


def _user(tenant_id):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "lead@test.example"
    u.role = "viewer"
    u.persona_role = "compliance_lead"
    u.tenant_id = tenant_id
    u.is_active = True
    u.read_only = False
    return u


def _override_db():
    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()


def _client(tenant_id):
    app.dependency_overrides[get_current_user] = lambda: _user(tenant_id)
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


def _clear():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_route_get_returns_tenant_checklist():
    c = _client(_TENANT_A)
    try:
        r = c.get("/api/v1/compliance/readiness", headers={"Authorization": "Bearer t"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body and body["total"] == len(body["items"])
        assert any(it["key"] == "ai_systems_registered" for it in body["items"])
    finally:
        _clear()


def test_route_put_persists_and_is_tenant_scoped():
    tA = uuid.uuid4()
    tB = uuid.uuid4()
    cA = _client(tA)
    try:
        r = cA.put(
            "/api/v1/compliance/readiness/dpa_in_place",
            json={"completed": True},
            headers={"Authorization": "Bearer t"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["completed"] is True
        # fresh GET as same tenant reflects persistence
        g = cA.get(
            "/api/v1/compliance/readiness", headers={"Authorization": "Bearer t"}
        )
        items = {it["key"]: it for it in g.json()["items"]}
        assert items["dpa_in_place"]["completed"] is True
    finally:
        _clear()
    # different tenant does not see it
    cB = _client(tB)
    try:
        g = cB.get(
            "/api/v1/compliance/readiness", headers={"Authorization": "Bearer t"}
        )
        items = {it["key"]: it for it in g.json()["items"]}
        assert items["dpa_in_place"]["completed"] is False
    finally:
        _clear()


def test_route_put_derived_item_rejected():
    c = _client(uuid.uuid4())
    try:
        r = c.put(
            "/api/v1/compliance/readiness/ai_systems_registered",
            json={"completed": True},
            headers={"Authorization": "Bearer t"},
        )
        assert r.status_code == 400
    finally:
        _clear()
