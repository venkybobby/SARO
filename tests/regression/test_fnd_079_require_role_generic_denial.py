"""FND-079: `require_role`'s 403 must not echo the required role tuple.

`require_role_or_persona` deliberately returns a generic denial (FND-036
hardening: "do not echo role/persona identifiers"), but `require_role` said
"Role 'x' is not authorised... Required: ('super_admin', ...)" — an
inconsistent disclosure posture that enumerates the privilege model to any
authenticated caller. The full detail still lands server-side via
`_log_authz_denial`; only the client-facing message goes generic.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from auth import get_current_user
from main import app

pytestmark = [pytest.mark.regression, pytest.mark.integration]


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


def _denial_detail() -> str:
    """Hit a require_role-gated route with an unauthorized role."""
    app.dependency_overrides[get_current_user] = lambda: _user("viewer")
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/v1/evaluations/trigger", json={"datasets": ["truthfulqa"]}
    )
    assert resp.status_code == 403
    return str(resp.json().get("detail", ""))


def test_403_does_not_echo_the_required_roles():
    detail = _denial_detail()
    for identifier in ("super_admin", "operator", "admin", "Required", "('"):
        assert identifier not in detail, (
            f"403 detail discloses the privilege model ({identifier!r}): {detail}"
        )


def test_403_does_not_echo_the_caller_role_either():
    detail = _denial_detail()
    assert "viewer" not in detail, f"403 detail echoes the caller's role: {detail}"


def test_403_still_carries_a_human_message():
    detail = _denial_detail()
    assert detail.strip(), "denial must still explain itself generically"
    assert "authoris" in detail.lower() or "authoriz" in detail.lower()
