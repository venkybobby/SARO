"""
Tests for the Risk Register / Risk Detail screen interrogation audit fixes.

Covers:
  - GET    /api/v1/risks/{id}     — single risk lookup by R-XXXXXX id
  - PATCH  /api/v1/risks/{id}     — owner / status override
  - DELETE /api/v1/risks/{id}     — soft-delete (dismiss), excluded from list
  - POST   /api/v1/risks/bulk     — assign_owner / change_status / delete

All tests use in-memory SQLite — no live DB required.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── SQLite setup ────────────────────────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON as PG_JSON
import sqlalchemy.types as sa_types

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
PG_JSON.none_as_null = False

from database import Base, get_db
import models  # noqa: E402
from models import Audit, ScanReport, Tenant, User
Base.metadata.create_all(engine)

from fastapi.testclient import TestClient
from main import app
from auth import get_current_user

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _seed():
    db = TestingSessionLocal()
    db.add(Tenant(id=TENANT_ID, name="Acme", slug="acme"))
    audit = Audit(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        dataset_name="Quarterly fairness scan",
        sample_count=50,
        status="completed",
    )
    db.add(audit)
    db.flush()
    db.add(ScanReport(
        audit_id=audit.id,
        overall_risk_score=82,
        report_json={},
    ))
    db.commit()
    risk_id = f"R-{str(audit.id)[:6].upper()}"
    db.close()
    return risk_id


RISK_ID = _seed()


def _override_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _override_user():
    return User(
        id=USER_ID, tenant_id=TENANT_ID, email="user@acme.test",
        hashed_password="x", role="admin", persona_role="admin", is_active=True,
    )


client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}


@pytest.fixture(autouse=True)
def _reset_overrides():
    """
    Other test modules set app.dependency_overrides[get_db] /
    [get_current_user] inside individual test functions, which can clobber
    these module-level overrides depending on test execution order across
    the full suite. Re-apply ours before every test in this module.
    """
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    yield


class TestGetSingleRisk:
    def test_get_existing_risk(self):
        r = client.get(f"/api/v1/risks/{RISK_ID}", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == RISK_ID
        assert body["title"] == "Quarterly fairness scan"
        assert body["risk_score"] == 82
        assert body["severity"] == "critical"

    def test_get_unknown_risk_404(self):
        r = client.get("/api/v1/risks/R-FFFFFF", headers=AUTH)
        assert r.status_code == 404


class TestUpdateRisk:
    def test_patch_owner_and_status(self):
        r = client.patch(
            f"/api/v1/risks/{RISK_ID}",
            json={"owner": "Alex Rivera", "status": "In Review"},
            headers=AUTH,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["owner"] == "Alex Rivera"
        assert body["status"] == "In Review"

        # List should reflect the override too
        listed = client.get("/api/v1/risks", headers=AUTH).json()
        match = next(x for x in listed if x["id"] == RISK_ID)
        assert match["owner"] == "Alex Rivera"
        assert match["status"] == "In Review"


class TestBulkActions:
    def test_bulk_assign_owner_requires_owner(self):
        r = client.post(
            "/api/v1/risks/bulk",
            json={"ids": [RISK_ID], "action": "assign_owner"},
            headers=AUTH,
        )
        assert r.status_code == 422

    def test_bulk_assign_owner(self):
        r = client.post(
            "/api/v1/risks/bulk",
            json={"ids": [RISK_ID], "action": "assign_owner", "owner": "Sam Patel"},
            headers=AUTH,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["updated"] == [RISK_ID]
        assert body["not_found"] == []

    def test_bulk_unknown_id_reported_not_found(self):
        r = client.post(
            "/api/v1/risks/bulk",
            json={"ids": ["R-FFFFFF"], "action": "change_status", "status": "Closed"},
            headers=AUTH,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["updated"] == []
        assert body["not_found"] == ["R-FFFFFF"]


class TestDeleteRisk:
    def test_delete_then_excluded_from_list(self):
        r = client.delete(f"/api/v1/risks/{RISK_ID}", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["dismissed"] is True

        listed = client.get("/api/v1/risks", headers=AUTH).json()
        assert all(x["id"] != RISK_ID for x in listed)

        single = client.get(f"/api/v1/risks/{RISK_ID}", headers=AUTH)
        assert single.status_code == 404

    def test_delete_unknown_404(self):
        r = client.delete("/api/v1/risks/R-FFFFFF", headers=AUTH)
        assert r.status_code == 404
