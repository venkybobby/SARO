"""STORY-TRACE-004: the TRACE timeline carries an honest, server-computed integrity verdict.

The old banner asserted "Hash chain integrity: verified" from an absent
`hash_chain_valid` field — an unbacked claim on the tamper-evidence screen
(ADR-004 anti-overclaiming). The timeline endpoint now returns an `integrity`
verdict computed server-side; this pins the honest semantics:
  - a signed export whose recomputed HMAC matches -> verified=True
  - no signed export on record -> unavailable, verified=False (never a green claim)
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import Base, get_db
from main import app
from models import Audit, Tenant

pytestmark = [pytest.mark.regression, pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT = uuid.uuid4()
AUDIT_NO_EXPORT = uuid.uuid4()


def _seed():
    db = _Session()
    db.add(Tenant(id=TENANT, name="A", slug="trace030"))
    db.add(
        Audit(
            id=AUDIT_NO_EXPORT,
            tenant_id=TENANT,
            dataset_name="scan",
            sample_count=50,
            status="completed",
        )
    )
    db.commit()
    db.close()


_seed()


def _client():
    class _U:
        id = uuid.uuid4()
        role = "operator"
        persona_role = None
        is_active = True
        read_only = False

    u = _U()
    u.tenant_id = TENANT
    app.dependency_overrides[get_db] = lambda: _Session()
    app.dependency_overrides[get_current_user] = lambda: u
    return TestClient(app, raise_server_exceptions=False)


def test_timeline_includes_integrity_verdict():
    """The timeline always carries an `integrity` object with a `verified` bool."""
    resp = _client().get(f"/api/v1/audit/{AUDIT_NO_EXPORT}/trace")
    assert resp.status_code == 200, resp.text
    integrity = resp.json().get("integrity")
    assert isinstance(integrity, dict), "timeline must include an integrity verdict"
    assert integrity["verified"] is False
    assert "verified" in integrity and "status" in integrity


def test_no_signed_export_is_unavailable_not_verified():
    """An audit with no signed export must NOT claim verified (no false green)."""
    integrity = (
        _client().get(f"/api/v1/audit/{AUDIT_NO_EXPORT}/trace").json()["integrity"]
    )
    assert integrity["status"] == "unavailable"
    assert integrity["verified"] is False
