"""STORY-TAB-004: Evaluations RBAC — nav visibility and backend gates must agree.

Pre-fix: GET /api/v1/evaluations was gated require_role("super_admin","operator")
while the sidebar showed the Evaluations tab to the admin and compliance_lead
personas — an admin opening their own tab got a bare 403. Owner decision
(least privilege): `admin` may LIST runs (read-only QA metadata); trigger stays
super_admin-only; the compliance_lead persona loses the nav entry instead of
gaining backend access.
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

pytestmark = [pytest.mark.integration]

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


# ── AC-1: list access matrix ──────────────────────────────────────────────────

@pytest.mark.parametrize("role", ["admin", "super_admin", "operator"])
def test_list_permitted_roles(role):
    """AC-1: admin (new), super_admin and operator can list evaluation runs."""
    resp = _client_as(_user(role)).get("/api/v1/evaluations")
    assert resp.status_code == 200, f"role={role} blocked from list: {resp.status_code}"


@pytest.mark.parametrize(
    "role,persona",
    [
        ("viewer", "compliance_lead"),  # persona alone must not grant access
        ("viewer", "ai_auditor"),
        ("demo_viewer", "compliance_lead"),
        ("viewer", None),
    ],
)
def test_list_denied_roles(role, persona):
    """AC-1 (negative): the roles axis gates the list; personas grant nothing."""
    resp = _client_as(_user(role, persona)).get("/api/v1/evaluations")
    assert resp.status_code == 403, f"role={role} persona={persona}: {resp.status_code}"


# ── AC-3/AC-5: trigger gate unchanged ─────────────────────────────────────────

def test_trigger_still_denied_to_admin():
    """AC-3: widening the LIST gate must not widen the TRIGGER gate."""
    resp = _client_as(_user("admin")).post(
        "/api/v1/evaluations/trigger", json={"datasets": ["truthfulqa"]}
    )
    assert resp.status_code == 403


def test_trigger_gate_still_admits_super_admin():
    """AC-5 regression guard: super_admin passes the auth gate. An unknown
    dataset makes validation fail *after* auth and *before* any run/background
    task is created — a 422 proves the gate, with zero side effects."""
    resp = _client_as(_user("super_admin")).post(
        "/api/v1/evaluations/trigger", json={"datasets": ["definitely_not_a_dataset"]}
    )
    assert resp.status_code == 422
    assert "Unknown datasets" in str(resp.json().get("detail", ""))


def test_trigger_denied_operator():
    """Operator can list but never trigger (unchanged pre-existing posture)."""
    resp = _client_as(_user("operator")).post(
        "/api/v1/evaluations/trigger", json={"datasets": ["truthfulqa"]}
    )
    assert resp.status_code == 403
