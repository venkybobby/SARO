"""FND-085 / STORY-TAB-008 AC-5: the remediate mutation must reject read-only tokens.

PATCH /api/v1/remediation/traces/{id}/remediate marked a trace remediated for
any authenticated tenant user — including a read-only demo JWT — because it
never attached `require_write_access` (the FND-015 class). STORY-TAB-008
embeds the remediation queue on TRACE View, a demo-visible tab, which makes
the missing gate load-bearing: the UI hides the button for read-only users,
but the backend gate is the control.
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
from models import Audit, AuditTrace, Tenant

pytestmark = [pytest.mark.regression, pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT = uuid.uuid4()
AUDIT = uuid.uuid4()
TRACE = uuid.uuid4()


def _seed() -> None:
    db = _Session()
    db.add(Tenant(id=TENANT, name="T", slug="fnd085"))
    db.add(Audit(id=AUDIT, tenant_id=TENANT, dataset_name="scan", sample_count=50, status="completed"))
    db.add(AuditTrace(
        id=TRACE, audit_id=AUDIT, tenant_id=TENANT,
        check_type="keyword", check_name="PII: email", gate_name="Gate 2",
        result="fail", reason="x", is_remediated=False,
    ))
    db.commit()
    db.close()


_seed()


def _user(read_only: bool):
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
    u.role = "demo_viewer" if read_only else "operator"
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


def test_read_only_token_cannot_remediate():
    """The regression: a read-only (demo) token must 403 BEFORE any mutation."""
    resp = _client_as(_user(read_only=True)).patch(
        f"/api/v1/remediation/traces/{TRACE}/remediate",
        json={"remediation_note": "attempted from a demo session"},
    )
    assert resp.status_code == 403, f"read-only token reached the mutation: {resp.status_code}"
    # and the trace stayed open
    db = _Session()
    trace = db.get(AuditTrace, TRACE)
    assert trace.is_remediated is False
    db.close()


def test_writable_user_still_remediates():
    """Regression guard: the gate must not lock out legitimate writers."""
    resp = _client_as(_user(read_only=False)).patch(
        f"/api/v1/remediation/traces/{TRACE}/remediate",
        json={"remediation_note": "verified and masked"},
    )
    assert resp.status_code == 200, resp.text
    db = _Session()
    trace = db.get(AuditTrace, TRACE)
    assert trace.is_remediated is True
    # restore for test-order independence
    trace.is_remediated = False
    db.commit()
    db.close()
