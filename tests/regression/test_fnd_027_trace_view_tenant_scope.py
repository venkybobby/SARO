"""STORY-TRACE-002: tenant-scope the TRACE timeline endpoint (cross-tenant leak).

`routers/trace_view.py`'s `_get_audit_or_404(db, audit_uuid)` filtered only on
`Audit.id` with no tenant predicate, so any authenticated user could read any
tenant's full TRACE (reasoning + findings) by UUID via `GET /api/v1/audit/{id}/trace`
and its export variants. This pins the fix: the timeline endpoint and all three
export variants are scoped to the caller's tenant, returning 404 (no existence
disclosure) for foreign-tenant or nonexistent audits, while the owning tenant
still gets 200.

Mirrors the already-correct `/api/v1/traces/{id}` isolation harness
(tests/test_tenant_isolation.py) — see STORY-015 / CHUB-010.
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

# Dedicated in-memory engine for this module (the conftest PG→SQLite shims are
# already applied at import time). StaticPool keeps a single shared connection.
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()
AUDIT_A = uuid.uuid4()  # owned by tenant A
AUDIT_B = uuid.uuid4()  # owned by tenant B
MISSING = uuid.uuid4()  # never inserted


def _seed() -> None:
    db = _Session()
    db.add(Tenant(id=TENANT_A, name="A", slug="trace002-a"))
    db.add(Tenant(id=TENANT_B, name="B", slug="trace002-b"))
    for aid, tid in ((AUDIT_A, TENANT_A), (AUDIT_B, TENANT_B)):
        db.add(
            Audit(
                id=aid,
                tenant_id=tid,
                dataset_name="scan",
                sample_count=50,
                status="completed",
            )
        )
    db.commit()
    db.close()


_seed()


def _user(tenant_id):
    class _U:
        id = uuid.uuid4()
        role = "operator"
        persona_role = "ai_auditor"
        is_active = True
        read_only = False

    u = _U()
    u.tenant_id = tenant_id
    return u


def _client_as(tenant_id) -> TestClient:
    app.dependency_overrides[get_db] = lambda: _Session()
    app.dependency_overrides[get_current_user] = lambda: _user(tenant_id)
    return TestClient(app, raise_server_exceptions=False)


# Every export variant on the trace_view router, plus the timeline itself.
_TENANT_SCOPED_PATHS = [
    "/api/v1/audit/{id}/trace",
    "/api/v1/audit/{id}/trace/export",
    "/api/v1/audit/{id}/export/json",
    "/api/v1/audit/{id}/export/pdf",
]


@pytest.mark.parametrize("path", _TENANT_SCOPED_PATHS)
def test_cross_tenant_request_returns_404(path):
    """AC-2/AC-3: tenant B's audit is invisible to tenant A on every variant."""
    client = _client_as(TENANT_A)
    resp = client.get(path.format(id=AUDIT_B))
    assert resp.status_code == 404, (
        f"{path}: tenant A read tenant B's audit (got {resp.status_code}) — cross-tenant leak"
    )


def test_owning_tenant_gets_200_on_timeline():
    """AC-4: the owning tenant still reads its own trace (no regression)."""
    client = _client_as(TENANT_A)
    resp = client.get(f"/api/v1/audit/{AUDIT_A}/trace")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body.get("steps"), list)


@pytest.mark.parametrize("path", _TENANT_SCOPED_PATHS)
def test_foreign_and_missing_responses_are_identical(path):
    """AC-2 edge: a foreign-tenant UUID and a nonexistent UUID are indistinguishable
    on every variant (the generic 404 is raised in the shared helper before any
    variant-specific response building)."""
    client = _client_as(TENANT_A)
    foreign = client.get(path.format(id=AUDIT_B))
    missing = client.get(path.format(id=MISSING))
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json(), (
        f"{path}: foreign-tenant and nonexistent audits must return identical 404 "
        "bodies (no existence oracle)"
    )
