"""FND-065 — authentication events must be recorded.

Found by the STORY-371 tabletop: `AUTH_EVENT` existed in the self-audit
vocabulary but **nothing emitted it**, so "was this leaked credential used, and
by whom?" — the question that decides whether an exposure is reportable — had no
answer. Failed attempts matter more than successes here: credential stuffing is
invisible without them.

Red-first: every emission test failed before the fix.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import services.self_audit as sa  # noqa: E402

pytestmark = pytest.mark.regression

_TENANT = uuid.uuid4()


def _user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="clinician@example.com",
        role="operator",
        persona_role="compliance_lead",
        tenant_id=_TENANT,
        is_active=True,
        token_version=1,
        hashed_password="x",
    )


def _client():
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app, raise_server_exceptions=False)


def _db_override(user):
    from database import get_db
    from main import app

    def _dep():
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        yield db

    app.dependency_overrides[get_db] = _dep
    return app


# ── Emission on success ─────────────────────────────────────────────────────


def test_successful_login_records_an_auth_event():
    from main import app

    user = _user()
    _db_override(user)
    try:
        with patch("routers.auth.authenticate_user", return_value=user), patch(
            "routers.auth.record_auth_event"
        ) as rec:
            resp = _client().post(
                "/api/v1/auth/token",
                json={"email": user.email, "password": "irrelevant"},
            )
        assert resp.status_code == 200
        assert rec.called, "a successful login was not audited"
        kwargs = rec.call_args.kwargs
        assert kwargs["outcome"] == sa.OUTCOME_SUCCESS
        assert kwargs["actor"] == user.email
    finally:
        app.dependency_overrides.clear()


def test_failed_login_records_an_auth_event():
    """The half that makes brute force visible."""
    from main import app

    _db_override(None)
    try:
        with patch("routers.auth.authenticate_user", return_value=None), patch(
            "routers.auth.record_auth_event"
        ) as rec:
            resp = _client().post(
                "/api/v1/auth/token",
                json={"email": "attacker@example.com", "password": "guess"},
            )
        assert resp.status_code == 401
        assert rec.called, "a failed login was not audited — brute force is invisible"
        assert rec.call_args.kwargs["outcome"] == sa.OUTCOME_FAILURE
        assert rec.call_args.kwargs["actor"] == "attacker@example.com"
    finally:
        app.dependency_overrides.clear()


def test_failed_login_for_unknown_email_uses_the_system_chain():
    """An unknown email has no tenant; the event must still be recorded."""
    from routers.auth import _auth_event_tenant

    assert _auth_event_tenant(None) == sa.SYSTEM_TENANT_ID


# ── Availability: the audit must not be able to lock everyone out ───────────


def test_login_still_succeeds_when_the_audit_write_fails():
    """Fail OPEN.

    Fail-closed would mean a self-audit database problem locks out every user
    INCLUDING the operator trying to diagnose it — an audit gap escalating into
    a total outage you cannot log in to fix.
    """
    from main import app

    user = _user()
    _db_override(user)
    try:
        with patch("routers.auth.authenticate_user", return_value=user), patch(
            "services.self_audit.record_access", side_effect=RuntimeError("audit db down")
        ):
            resp = _client().post(
                "/api/v1/auth/token",
                json={"email": user.email, "password": "irrelevant"},
            )
        assert resp.status_code == 200, "an audit failure must not block authentication"
    finally:
        app.dependency_overrides.clear()


# ── Content of the event ────────────────────────────────────────────────────


def test_auth_event_uses_the_auth_event_action_class():
    assert sa.AUTH_EVENT in sa.ACTION_CLASSES


def test_auth_event_records_source_ip_for_attribution():
    src = (ROOT / "routers" / "auth.py").read_text(encoding="utf-8")
    assert "source_ip" in src, "an auth trail without origin cannot answer 'who used this'"


def test_auth_event_carries_no_password_material():
    """Nothing about the credential itself may reach the trail."""
    import ast

    src = (ROOT / "routers" / "auth.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    emitter = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "record_auth_event"
    )
    # Strip the docstring before scanning: it legitimately contains the word
    # "password" while PROMISING none is recorded, and failing on that would
    # punish the code for documenting its own guarantee. Compare executable
    # statements only — this is about what the function does, not what it says.
    body = emitter.body[1:] if ast.get_docstring(emitter) else emitter.body
    executable = "\n".join(ast.unparse(stmt) for stmt in body).lower()
    for banned in ("password", "hashed_password", "access_token"):
        assert banned not in executable, f"auth event emitter handles {banned!r}"


# ── The query path (already existed; assert it is usable) ───────────────────


def test_auth_events_are_queryable_by_actor_and_class():
    """Reconstructing one principal's session history is the point."""
    src = (ROOT / "routers" / "self_audit.py").read_text(encoding="utf-8")
    assert "actor" in src and "action_class" in src


# ── Registry classification must now reflect reality ───────────────────────


def test_login_route_is_classified_as_audited():
    from services.admin_audit_registry import classification

    assert classification("POST", "/api/v1/auth/token") == "AUDITED", (
        "login is now audited — the registry must say so"
    )


def test_registry_no_longer_carries_the_inaccurate_justification():
    src = (ROOT / "services" / "admin_audit_registry.py").read_text(encoding="utf-8")
    assert "auth events handled by the auth path" not in src
