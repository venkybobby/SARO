"""FND-063: `GET /remediation/oauth/jira/start` must be an admin capability.

The route depended on bare `get_current_user`, so ANY authenticated tenant
user — including read-only personas — could initiate a new OAuth flow and
rebind the whole tenant's Jira integration to their own Atlassian account
(insider-integrity, not cross-tenant). Completing FND-061's TM-F1 work:
/start now requires an admin-class role AND write access.

Residual (documented, unchanged): the pending state nonce remains a single
per-tenant slot on Tenant.settings_json, so two concurrent ADMIN flows can
clobber each other — low risk now that the surface is admin-only.
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

TENANT = uuid.uuid4()


def _seed() -> None:
    db = _Session()
    db.add(Tenant(id=TENANT, name="T", slug="fnd063"))
    db.commit()
    db.close()


_seed()


def _user(role: str, read_only: bool = False):
    class _U:
        id: uuid.UUID
        role: str
        persona_role: str | None
        tenant_id: uuid.UUID
        is_active: bool
        read_only: bool
        email: str

    u = _U()
    u.id = uuid.uuid4()
    u.role = role
    u.persona_role = None
    u.tenant_id = TENANT
    u.is_active = True
    u.read_only = read_only
    u.email = "u@t.test"
    return u


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def _start_as(user) -> int:
    app.dependency_overrides[get_db] = lambda: _Session()
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app, raise_server_exceptions=False)
    return client.get("/api/v1/remediation/oauth/jira/start").status_code


@pytest.mark.parametrize("role", ["operator", "viewer", "ai_auditor"])
def test_non_admin_roles_cannot_start_oauth(role):
    """The regression: rebinding the tenant Jira connection is not a
    capability of every authenticated user."""
    assert _start_as(_user(role)) == 403


def test_read_only_demo_token_cannot_start_oauth():
    assert _start_as(_user("demo_viewer", read_only=True)) == 403


@pytest.mark.parametrize("role", ["admin", "super_admin"])
def test_admin_roles_pass_the_gate(role):
    """Admins pass the auth gate — anything but 401/403 (the handler may
    still 4xx/5xx on missing Jira client config; that's not the gate)."""
    assert _start_as(_user(role)) not in (401, 403)
