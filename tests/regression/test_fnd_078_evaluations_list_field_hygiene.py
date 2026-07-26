"""FND-078: the evaluations LIST/TRIGGER responses must not expose internal
infrastructure detail.

`EvaluationRunOut` serialized `api_url` (the raw SARO_API_URL — an internal
infrastructure endpoint) and `error_message` (`str(exc)[:2000]` — arbitrary
internal exception text that can carry paths/URLs from TestRunner failures)
to every listing role. Neither is something a list consumer needs; both stay
available on `EvaluationRunDetailOut` (super_admin/operator only).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import Base, get_db
from main import app
from models import EvaluationRun

pytestmark = [pytest.mark.regression, pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

RUN_ID = uuid.uuid4()


def _seed() -> None:
    db = _Session()
    db.add(EvaluationRun(
        id=RUN_ID,
        triggered_by="api",
        datasets_requested="truthfulqa",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status="failed",
        api_url="http://internal-infra:8000",
        error_message="Traceback ... /home/runner/secret-path/runner.py boom",
    ))
    db.commit()
    db.close()


_seed()


def _user(role: str):
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
    u.tenant_id = uuid.uuid4()
    u.is_active = True
    u.read_only = False
    u.email = "u@t.test"
    return u


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def _client_as(role: str) -> TestClient:
    app.dependency_overrides[get_db] = lambda: _Session()
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    return TestClient(app, raise_server_exceptions=False)


def test_list_response_has_no_internal_fields():
    """The regression: no listing role receives api_url / error_message."""
    body = _client_as("admin").get("/api/v1/evaluations").json()
    assert body, "seeded run missing"
    for run in body:
        assert "api_url" not in run, "api_url leaked on the list response"
        assert "error_message" not in run, "error_message leaked on the list response"


def test_detail_response_keeps_the_fields_for_operators():
    """Failure forensics stay reachable on the gated detail route."""
    body = _client_as("operator").get(f"/api/v1/evaluations/{RUN_ID}").json()
    assert body["api_url"] == "http://internal-infra:8000"
    assert "secret-path" in (body["error_message"] or "")


def test_list_still_serves_the_operational_fields():
    """Slimming must not drop what the page actually renders."""
    run = _client_as("admin").get("/api/v1/evaluations").json()[0]
    for key in ("id", "status", "datasets_attempted", "datasets_passed",
                "total_samples_uploaded", "started_at", "created_at"):
        assert key in run, f"list response lost {key}"
