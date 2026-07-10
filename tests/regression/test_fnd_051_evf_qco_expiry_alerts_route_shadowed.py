"""FND-051: GET /api/v1/evf/qco/expiry-alerts was shadowed by evf_sprint2's
generic GET /qco/{qco_id} route.

Both routers share the /api/v1/evf prefix; FastAPI/Starlette matches routes
in registration order, and main.py included evf_sprint2_router (the generic
"/qco/{qco_id}" route) before evf_sprint3_router (the static
"/qco/expiry-alerts" route). Every call to expiry-alerts was parsed as
qco_id="expiry-alerts", a 422 uuid_parsing error, for every caller — not
demo-specific. Found while building STORY-412's demo-tab endpoint census
(ComplianceHub.jsx's ComplianceCalendar polls this endpoint on load).

Fix: main.py now includes evf_sprint3_router before evf_sprint2_router.
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
from models import Tenant

pytestmark = [pytest.mark.regression, pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT_ID = uuid.uuid4()


def _seed() -> None:
    db = _Session()
    db.add(Tenant(id=TENANT_ID, name="FND-051 tenant", slug="fnd051"))
    db.commit()
    db.close()


_seed()


def _user():
    class _U:
        pass

    u = _U()
    u.id = uuid.uuid4()
    u.role = "operator"
    u.persona_role = None
    u.tenant_id = TENANT_ID
    u.is_active = True
    u.read_only = False
    u.email = "u@t.test"
    return u


def _client() -> TestClient:
    app.dependency_overrides[get_db] = lambda: _Session()
    app.dependency_overrides[get_current_user] = lambda: _user()
    return TestClient(app, raise_server_exceptions=False)


def test_expiry_alerts_route_not_shadowed_by_qco_id_route():
    r = _client().get("/api/v1/evf/qco/expiry-alerts?limit=20")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_qco_by_id_route_still_reachable():
    """Regression guard on the fix itself: reordering must not shadow the
    other direction — a real qco_id must still resolve through evf_sprint2,
    not fall through to any route in evf_sprint3."""
    some_id = uuid.uuid4()
    r = _client().get(f"/api/v1/evf/qco/{some_id}")
    # Not found (no such QCO seeded) is the correct outcome — the important
    # assertion is that it's a domain 404, not a 422 UUID-parsing error or an
    # unrelated 200 from a different handler shadowing this path.
    assert r.status_code == 404, r.text
