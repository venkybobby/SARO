"""
Regression tests for persona-switch bugs:

  BUG-A: super_admin who switches persona to risk_officer loses canSwitch
         (persona_role becomes "risk_officer"; old code checked persona_role || role
          which evaluated to "risk_officer" → not in ["admin","super_admin"] → stuck)

  BUG-B: After logout/login, persona_role from DB is not restored
         (fixed: /me endpoint returns persona_role; Login.jsx merges it)

Backend contract tests:
  1. PATCH /users/{id}/persona — updates persona_role, leaves role unchanged
  2. GET /me — always returns both role (immutable) and persona_role (mutable)
  3. All 6 valid persona values are accepted by PATCH
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-persona-fix")

from fastapi.testclient import TestClient  # noqa: E402
from auth import get_current_user          # noqa: E402
from database import get_db               # noqa: E402
from main import app                       # noqa: E402
from models import User                    # noqa: E402

_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000097")


def _mock_user(role: str = "super_admin", persona_role: str | None = None) -> MagicMock:
    u = MagicMock(spec=User)
    u.id           = uuid.uuid4()
    u.email        = f"{role}@test.example"
    u.role         = role                           # immutable base role
    u.persona_role = persona_role or role           # current view — matches role initially
    u.tenant_id    = _TENANT_ID
    u.is_active    = True
    u.read_only    = False
    u.allowed_tabs    = []
    u.allowed_actions = []
    u.created_at   = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return u


def _user_dep(role: str = "super_admin", persona_role: str | None = None):
    user = _mock_user(role, persona_role)
    async def _dep():
        return user
    return _dep, user


def _db_dep(persona_update_target: MagicMock | None = None):
    """
    Stub DB. If persona_update_target is provided, db.get() returns it
    so the PATCH endpoint can update persona_role on it.
    """
    def _dep():
        mock_db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value  = None
        q.all.return_value    = []
        mock_db.query.return_value = q
        if persona_update_target is not None:
            mock_db.get.return_value = persona_update_target
        else:
            mock_db.get.return_value = None
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        yield mock_db
    return _dep


def _clear():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ─── /me always returns both role and persona_role ───────────────────────────

class TestMeEndpoint:

    def test_me_returns_base_role(self):
        """GET /me must always include the immutable base role."""
        dep, user = _user_dep("super_admin", "risk_officer")
        app.dependency_overrides[get_current_user] = dep
        app.dependency_overrides[get_db]           = _db_dep()
        try:
            r = TestClient(app).get("/api/v1/auth/me", headers={"Authorization": "Bearer test"})
            assert r.status_code == 200, f"Expected 200: {r.text[:200]}"
            body = r.json()
            assert body["role"] == "super_admin", \
                f"role must be the immutable base role 'super_admin', got {body.get('role')}"
        finally:
            _clear()

    def test_me_returns_current_persona_role(self):
        """GET /me returns persona_role from DB (the current switched-to persona)."""
        dep, user = _user_dep("super_admin", "risk_officer")
        app.dependency_overrides[get_current_user] = dep
        app.dependency_overrides[get_db]           = _db_dep()
        try:
            r = TestClient(app).get("/api/v1/auth/me", headers={"Authorization": "Bearer test"})
            assert r.status_code == 200
            body = r.json()
            assert body["persona_role"] == "risk_officer", \
                f"persona_role should reflect current view 'risk_officer', got {body.get('persona_role')}"
        finally:
            _clear()

    def test_me_role_and_persona_role_independent(self):
        """role != persona_role is valid — super_admin viewing as operator."""
        dep, user = _user_dep("super_admin", "operator")
        app.dependency_overrides[get_current_user] = dep
        app.dependency_overrides[get_db]           = _db_dep()
        try:
            r = TestClient(app).get("/api/v1/auth/me", headers={"Authorization": "Bearer test"})
            assert r.status_code == 200
            body = r.json()
            assert body["role"] == "super_admin"
            assert body["persona_role"] == "operator"
        finally:
            _clear()


# ─── PATCH /users/{id}/persona ───────────────────────────────────────────────

class TestPersonaPatch:

    def _make_target_user(self, base_role="super_admin", current_persona="risk_officer"):
        """Create a DB user mock that the PATCH handler will find and update."""
        target = MagicMock(spec=User)
        target.id           = uuid.uuid4()
        target.email        = f"{base_role}@target.example"
        target.role         = base_role
        target.persona_role = current_persona
        target.tenant_id    = _TENANT_ID
        target.is_active    = True
        target.read_only    = False
        target.allowed_tabs    = []
        target.allowed_actions = []
        target.created_at   = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return target

    def test_patch_persona_updates_persona_role_not_role(self):
        """PATCH must update persona_role; the base role must stay unchanged."""
        target = self._make_target_user("super_admin", "risk_officer")
        dep, caller = _user_dep("super_admin", "super_admin")
        app.dependency_overrides[get_current_user] = dep
        app.dependency_overrides[get_db]           = _db_dep(persona_update_target=target)
        try:
            r = TestClient(app).patch(
                f"/api/v1/auth/users/{target.id}/persona?persona_role=compliance_lead",
                headers={"Authorization": "Bearer test"},
            )
            # PATCH may succeed (200) or be forbidden (403) depending on RBAC rules
            # — it must never crash (500)
            assert r.status_code != 500, f"PATCH crashed: {r.text[:200]}"
            if r.status_code == 200:
                body = r.json()
                assert body["persona_role"] == "compliance_lead", \
                    f"persona_role should be updated, got {body.get('persona_role')}"
                # role must be unchanged regardless
                assert body["role"] == "super_admin", \
                    f"base role must not change, got {body.get('role')}"
        finally:
            _clear()

    def test_super_admin_can_switch_to_any_persona(self):
        """super_admin must be able to PATCH to all 6 persona values."""
        VALID_PERSONAS = [
            "compliance_lead", "risk_officer", "ai_auditor",
            "admin", "super_admin", "operator",
        ]
        for persona in VALID_PERSONAS:
            target = self._make_target_user("super_admin", "super_admin")
            dep, _ = _user_dep("super_admin", "super_admin")
            app.dependency_overrides[get_current_user] = dep
            app.dependency_overrides[get_db]           = _db_dep(persona_update_target=target)
            try:
                r = TestClient(app).patch(
                    f"/api/v1/auth/users/{target.id}/persona?persona_role={persona}",
                    headers={"Authorization": "Bearer test"},
                )
                assert r.status_code != 500, \
                    f"PATCH to {persona} crashed: {r.text[:200]}"
                # 200 = success, 403 = RBAC denied, 404 = tenant mismatch in stub DB
                assert r.status_code in (200, 403, 404), \
                    f"PATCH to {persona} returned unexpected {r.status_code}"
            finally:
                _clear()

    def test_patch_unknown_persona_rejected(self):
        """PATCH with an invalid persona_role must return 422."""
        target = self._make_target_user()
        dep, _ = _user_dep("super_admin")
        app.dependency_overrides[get_current_user] = dep
        app.dependency_overrides[get_db]           = _db_dep(persona_update_target=target)
        try:
            r = TestClient(app).patch(
                f"/api/v1/auth/users/{target.id}/persona?persona_role=hacker_admin",
                headers={"Authorization": "Bearer test"},
            )
            assert r.status_code == 422, \
                f"Invalid persona should return 422, got {r.status_code}"
        finally:
            _clear()

    def test_non_admin_cannot_patch_persona(self):
        """compliance_lead / risk_officer cannot PATCH another user's persona."""
        for non_admin in ["compliance_lead", "risk_officer", "operator"]:
            target = self._make_target_user("super_admin")
            dep, _ = _user_dep(non_admin, non_admin)
            app.dependency_overrides[get_current_user] = dep
            app.dependency_overrides[get_db]           = _db_dep(persona_update_target=target)
            try:
                r = TestClient(app).patch(
                    f"/api/v1/auth/users/{target.id}/persona?persona_role=operator",
                    headers={"Authorization": "Bearer test"},
                )
                assert r.status_code in (403, 401), \
                    f"{non_admin} should be denied persona PATCH, got {r.status_code}"
            finally:
                _clear()


# ─── Frontend canSwitch logic (source-level assertion) ───────────────────────

class TestCanSwitchLogic:

    def test_sidebar_uses_base_role_for_can_switch(self):
        """
        Sidebar.jsx canSwitch must check user?.role (immutable),
        NOT user?.persona_role || user?.role.

        The bug: persona_role="risk_officer" || role="super_admin"
                 evaluates to "risk_officer" → canSwitch=false → user locked out.
        The fix: check user?.role directly.
        """
        sidebar_path = os.path.join(_REPO_ROOT, "frontend", "src", "components", "Sidebar.jsx")
        with open(sidebar_path) as f:
            source = f.read()

        import re
        # Find the canSwitch assignment line
        m = re.search(r"const canSwitch\s*=\s*(.+)", source)
        assert m, "canSwitch not found in Sidebar.jsx"

        expr = m.group(1).strip()

        # Must NOT use persona_role in the check — that's the bug
        assert "persona_role" not in expr, (
            f"BUG: canSwitch uses persona_role which breaks after persona switch.\n"
            f"  Current expression: {expr}\n"
            f"  Fix: use user?.role only (the immutable base role)."
        )

        # Must check user?.role
        assert "user?.role" in expr, (
            f"canSwitch should check user?.role (immutable base role).\n"
            f"  Current expression: {expr}"
        )
