"""
SAR-014: GET /api/v1/auth/users — admin user list endpoint.

Tests:
- admin gets 200 with a list
- non-admin (compliance_lead) gets 403
- unauthenticated gets 401
- PATCH /api/v1/auth/users/{id}/persona now accepts super_admin and operator
- PATCH rejects unknown persona roles with 422
"""
from __future__ import annotations

import os
import sys
import uuid
from unittest.mock import MagicMock

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-sar014")

from fastapi.testclient import TestClient  # noqa: E402
from auth import get_current_user  # noqa: E402
from database import get_db  # noqa: E402
from main import app  # noqa: E402
from models import User  # noqa: E402

client = TestClient(app)

_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _mock_user(role: str = "admin") -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = f"{role}@test.example"
    u.role = role
    u.tenant_id = _TENANT_ID
    u.persona_role = role
    u.is_active = True
    u.read_only = False
    return u


def _override_current_user(user: MagicMock):
    async def _dep():
        return user
    return _dep


def _override_db_list(users: list):
    def _dep():
        mock_db = MagicMock()
        q = MagicMock()
        q.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = users
        mock_db.query.return_value = q
        yield mock_db
    return _dep


# ── GET /api/v1/auth/users ────────────────────────────────────────────────────


def test_admin_list_users_returns_200():
    admin = _mock_user("admin")
    member = _mock_user("compliance_lead")
    member.email = "member@test.example"

    app.dependency_overrides[get_current_user] = _override_current_user(admin)
    app.dependency_overrides[get_db] = _override_db_list([admin, member])
    try:
        r = client.get("/api/v1/auth/users")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_non_admin_gets_403():
    user = _mock_user("compliance_lead")
    app.dependency_overrides[get_current_user] = _override_current_user(user)
    try:
        r = client.get("/api/v1/auth/users")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_unauthenticated_gets_401():
    r = client.get("/api/v1/auth/users")
    assert r.status_code == 401


# ── PATCH persona — super_admin and operator now valid ────────────────────────


def _patch_db_with_target(target: MagicMock):
    def _dep():
        mock_db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = target
        mock_db.query.return_value = q
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda x: None
        yield mock_db
    return _dep


def test_patch_persona_accepts_super_admin():
    sa = _mock_user("super_admin")
    target = _mock_user("compliance_lead")
    target.persona_role = "compliance_lead"

    app.dependency_overrides[get_current_user] = _override_current_user(sa)
    app.dependency_overrides[get_db] = _patch_db_with_target(target)
    try:
        r = client.patch(f"/api/v1/auth/users/{target.id}/persona?persona_role=super_admin")
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_patch_persona_accepts_operator():
    sa = _mock_user("super_admin")
    target = _mock_user("compliance_lead")

    app.dependency_overrides[get_current_user] = _override_current_user(sa)
    app.dependency_overrides[get_db] = _patch_db_with_target(target)
    try:
        r = client.patch(f"/api/v1/auth/users/{target.id}/persona?persona_role=operator")
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_patch_persona_rejects_unknown_role():
    sa = _mock_user("super_admin")
    target = _mock_user("compliance_lead")

    app.dependency_overrides[get_current_user] = _override_current_user(sa)
    app.dependency_overrides[get_db] = _patch_db_with_target(target)
    try:
        r = client.patch(f"/api/v1/auth/users/{target.id}/persona?persona_role=hacker")
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_patch_persona_non_super_admin_gets_403():
    admin = _mock_user("admin")
    target = _mock_user("compliance_lead")

    app.dependency_overrides[get_current_user] = _override_current_user(admin)
    app.dependency_overrides[get_db] = _patch_db_with_target(target)
    try:
        r = client.patch(f"/api/v1/auth/users/{target.id}/persona?persona_role=operator")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
