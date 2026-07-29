"""FND-088: GET /api/v1/demo/token trusted SARO_DEMO_TENANT_ID on presence
alone, never checking it resolves to a real tenant.

Red-team QA review (2026-07-28) reproduced this live: the deployed
saro-backend's SARO_DEMO_TENANT_ID pointed at a tenant UUID absent from the
`tenants` table. The public /demo flow still issued a 200 token for it —
every subsequent read came back empty, indistinguishable from a legitimately
fresh tenant, so the misconfiguration was invisible to anyone but a human
reading the dashboard. The endpoint must fail loud (503) instead of silently
minting a token for a phantom tenant.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from middleware import rate_limiter
from models import Tenant

pytestmark = [pytest.mark.regression, pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

REAL_TENANT = uuid.uuid4()
PHANTOM_TENANT = uuid.uuid4()  # never inserted — simulates the live misconfig


def _seed() -> None:
    db = _Session()
    db.add(Tenant(id=REAL_TENANT, name="Demo", slug="fnd088-demo"))
    db.commit()
    db.close()


_seed()


@pytest.fixture(autouse=True)
def _reset_overrides(monkeypatch):
    app.dependency_overrides[get_db] = lambda: _Session()
    # FND-090 made /api/v1/demo/token subject to the strict per-IP rate limit.
    # This module exercises token-validation logic, not throttling, and its
    # repeated real calls would otherwise share a live Redis bucket with every
    # other test hitting an _AUTH_STRICT_PREFIXES route in the same run.
    monkeypatch.setattr(
        rate_limiter,
        "check_rate_limit",
        lambda key, limit: {
            "allowed": True,
            "count": 0,
            "limit": limit,
            "remaining": limit,
            "retry_after": 1,
            "reset_epoch": 0,
        },
    )
    yield
    app.dependency_overrides.clear()


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_phantom_tenant_id_fails_loud_not_silent(monkeypatch):
    """The exact live bug: SARO_DEMO_TENANT_ID set to a UUID no tenant has."""
    monkeypatch.setenv("SARO_DEMO_TENANT_ID", str(PHANTOM_TENANT))
    resp = _client().get("/api/v1/demo/token")
    assert resp.status_code == 503, (
        f"phantom SARO_DEMO_TENANT_ID silently issued a token: {resp.status_code} {resp.text}"
    )
    assert "does not match any" in resp.json()["detail"]


def test_malformed_tenant_id_fails_loud(monkeypatch):
    monkeypatch.setenv("SARO_DEMO_TENANT_ID", "not-a-uuid")
    resp = _client().get("/api/v1/demo/token")
    assert resp.status_code == 503
    assert "not a valid UUID" in resp.json()["detail"]


def test_real_tenant_id_still_issues_a_token(monkeypatch):
    """Regression guard: the validation must not lock out the working case."""
    monkeypatch.setenv("SARO_DEMO_TENANT_ID", str(REAL_TENANT))
    resp = _client().get("/api/v1/demo/token")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["read_only"] is True


def test_unset_tenant_id_still_fails_loud(monkeypatch):
    monkeypatch.delenv("SARO_DEMO_TENANT_ID", raising=False)
    resp = _client().get("/api/v1/demo/token")
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"]
