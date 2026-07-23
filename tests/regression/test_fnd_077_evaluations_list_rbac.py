"""FND-077 / STORY-TAB-004: Evaluations RBAC and nav visibility must agree.

Pre-fix: the sidebar showed the Evaluations tab to the admin persona while
GET /api/v1/evaluations was gated require_role("super_admin","operator") —
an admin opening their own tab got a bare 403. Owner decision (least
privilege): admin may LIST runs; POST /trigger stays super_admin-only; the
compliance_lead persona lost the nav entry instead of gaining backend access
(that half is pinned by frontend/src/pages/Evaluations.test.jsx and
frontend/src/components/Sidebar.test.jsx).
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

pytestmark = [pytest.mark.regression, pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


def _user(role, persona=None):
    class _U:
        pass

    u = _U()
    u.id = uuid.uuid4()
    u.role = role
    u.persona_role = persona
    u.tenant_id = uuid.uuid4()
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


def test_admin_can_list_evaluation_runs():
    """The regression: admin's own tab must not 403 on its only endpoint."""
    assert _client_as(_user("admin")).get("/api/v1/evaluations").status_code == 200


def test_admin_still_cannot_trigger():
    """Widening the LIST gate must never widen the TRIGGER gate."""
    resp = _client_as(_user("admin")).post(
        "/api/v1/evaluations/trigger", json={"datasets": ["truthfulqa"]}
    )
    assert resp.status_code == 403


def test_persona_alone_grants_nothing():
    """The gate is on the roles axis — a compliance_lead persona on an
    unprivileged role stays denied (nav fix, not an authz widening)."""
    resp = _client_as(_user("viewer", "compliance_lead")).get("/api/v1/evaluations")
    assert resp.status_code == 403
