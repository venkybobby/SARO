"""FND-067: breach-notification readiness — template + per-tenant contact.

support-model.md §4 commits to notifying an affected customer within 72 hours
of confirming a reportable incident, but there was no drafted notification
template and no recorded per-tenant security contact — the two artifacts you
do not want to produce mid-incident. Pins:
  1. the committed template exists with initial/update/closure sections and
     explicit counsel-review gating;
  2. `tenants.security_contact_email` exists and round-trips through the
     admin-gated endpoints;
  3. non-admin and read-only tokens cannot set it; bad emails are rejected.
"""

from __future__ import annotations

import uuid
from pathlib import Path

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

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "docs" / "ops" / "breach-notification-template.md"

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
    db.add(Tenant(id=TENANT, name="T", slug="fnd067"))
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


def _client_as(user) -> TestClient:
    app.dependency_overrides[get_db] = lambda: _Session()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


# ── 1. the template artifact ──────────────────────────────────────────────────


def test_template_exists_with_all_three_notices():
    text = TEMPLATE.read_text(encoding="utf-8")
    for section in ("Initial notification", "Update notification", "Closure notification"):
        assert section in text, f"template missing section: {section}"
    # counsel gating is explicit, not implied
    assert "[HUMAN — COUNSEL REVIEW]" in text
    # tied to the actual commitment and recipient mechanism
    assert "72" in text and "security_contact_email" in text


def test_migration_042_exists():
    assert (REPO / "migrations" / "042_tenant_security_contact.sql").exists()


# ── 2/3. the contact round-trip and its gates ─────────────────────────────────


def test_admin_sets_and_reads_the_contact():
    put = _client_as(_user("admin")).put(
        "/api/v1/clients/security-contact",
        json={"security_contact_email": "secteam@tenant.example"},
    )
    assert put.status_code == 200, put.text
    got = _client_as(_user("admin")).get("/api/v1/clients/security-contact").json()
    assert got["security_contact_email"] == "secteam@tenant.example"


def test_non_admin_cannot_set_the_contact():
    resp = _client_as(_user("operator")).put(
        "/api/v1/clients/security-contact",
        json={"security_contact_email": "attacker@evil.example"},
    )
    assert resp.status_code == 403


def test_read_only_admin_persona_cannot_set_the_contact():
    resp = _client_as(_user("admin", read_only=True)).put(
        "/api/v1/clients/security-contact",
        json={"security_contact_email": "demo@evil.example"},
    )
    assert resp.status_code == 403


def test_invalid_email_is_rejected():
    resp = _client_as(_user("admin")).put(
        "/api/v1/clients/security-contact",
        json={"security_contact_email": "not-an-email"},
    )
    assert resp.status_code == 422
