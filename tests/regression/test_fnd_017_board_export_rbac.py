"""FND-017: GET /api/v1/risk/board-export lacked a board-persona RBAC guard.

``_require_board_persona`` (risk_officer / super_admin only) was defined but never
wired into the board PDF export, so any authenticated tenant user — including the
read-only ``ai_auditor`` and ``operator`` personas — could pull the formatted
board risk pack. The newer SPEC-FE2 board-summary export gates via
``_require_board_access``; this older export was left open.

Fix: call ``_require_board_persona(current_user)`` at the top of the export route.

Pinned behaviourally: a non-board persona is rejected with 403 *before* any data
work, while a board persona is not rejected by the guard.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from auth import get_current_user
from database import get_db
from main import app
from models import User
from routers.risk_dashboard import _require_board_access as _require_board_persona

pytestmark = pytest.mark.regression

_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000017")


def _user(role: str):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = f"{role}@test.example"
    u.role = role
    u.persona_role = role
    u.tenant_id = _TENANT_ID
    u.is_active = True
    u.read_only = False
    return u


def _db_empty():
    def _dep():
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.join.return_value = q
        q.outerjoin.return_value = q
        q.all.return_value = []
        q.first.return_value = None
        db.query.return_value = q
        yield db
    return _dep


def _client(role: str):
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    app.dependency_overrides[get_db] = _db_empty()
    return TestClient(app)


def _clear():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ── Guard-unit level ─────────────────────────────────────────────────────────

def test_require_board_persona_denies_ai_auditor():
    with pytest.raises(HTTPException) as exc:
        _require_board_persona(_user("ai_auditor"))
    assert exc.value.status_code == 403


def test_require_board_persona_denies_operator():
    with pytest.raises(HTTPException) as exc:
        _require_board_persona(_user("operator"))
    assert exc.value.status_code == 403


def test_require_board_persona_allows_risk_officer():
    # Should not raise.
    _require_board_persona(_user("risk_officer"))


# ── Route level — the actual regression ──────────────────────────────────────

def test_board_export_forbidden_for_non_board_persona():
    c = _client("ai_auditor")
    try:
        r = c.get("/api/v1/risk/board-export", headers={"Authorization": "Bearer t"})
        assert r.status_code == 403, (
            "board-export must reject non-board personas (FND-017); "
            f"got {r.status_code}"
        )
    finally:
        _clear()


def test_board_export_not_forbidden_for_risk_officer():
    c = _client("risk_officer")
    try:
        r = c.get("/api/v1/risk/board-export", headers={"Authorization": "Bearer t"})
        assert r.status_code != 403, (
            "board-export must not 403 a risk_officer (FND-017 over-correction)"
        )
    finally:
        _clear()
