"""FND-086: FND-085's remediation was incomplete — the batch and Jira mutation
twins of the remediate route had no `require_write_access` either.

security-auditor PoC (STORY-TAB-008 audit): a read-only public demo token
POSTing /api/v1/remediation/bulk-remediate returned 200 {"succeeded": 1} and
flipped the trace to is_remediated=True — a mutation reachable with a public
credential (GET /api/v1/demo/token). create-jira-issue is the same class
(writes detail_json + AuditEvent and triggers an outbound Jira call), reached
only incidentally 400 when no Jira config exists.
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
    db.add(Tenant(id=TENANT, name="T", slug="fnd086"))
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


def test_read_only_token_cannot_bulk_remediate():
    """The PoC route: a public demo token must 403 with zero mutations."""
    resp = _client_as(_user(read_only=True)).post(
        "/api/v1/remediation/bulk-remediate",
        json={"trace_ids": [str(TRACE)], "remediation_note": "from a demo session"},
    )
    assert resp.status_code == 403, f"read-only token reached bulk-remediate: {resp.status_code}"
    db = _Session()
    assert db.get(AuditTrace, TRACE).is_remediated is False
    db.close()


def test_read_only_token_cannot_create_jira_issue():
    """Same gate on the Jira mutation (403 BEFORE config lookup / egress)."""
    resp = _client_as(_user(read_only=True)).post(
        f"/api/v1/remediation/traces/{TRACE}/create-jira-issue",
        json={"summary": "x", "description": "y"},
    )
    assert resp.status_code == 403, f"read-only token reached create-jira-issue: {resp.status_code}"


def test_writable_user_can_still_bulk_remediate():
    """Regression guard: the gate must not lock out legitimate writers."""
    resp = _client_as(_user(read_only=False)).post(
        "/api/v1/remediation/bulk-remediate",
        json={"trace_ids": [str(TRACE)], "remediation_note": "verified and masked"},
    )
    assert resp.status_code == 200, resp.text
    db = _Session()
    trace = db.get(AuditTrace, TRACE)
    assert trace.is_remediated is True
    trace.is_remediated = False  # restore for order-independence
    db.commit()
    db.close()
