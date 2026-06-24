"""FND-025 (CHUB-002): GET /api/v1/audits excluded the compliance_lead persona.

The Compliance Hub landing page (built for the ``compliance_lead`` persona) reads
``/api/v1/audits``, but the route was gated ``require_role("super_admin",
"operator", "demo_viewer")``. ``compliance_lead`` is a *persona_role*, not a system
*role*, so a real compliance lead received 403, the frontend swallowed it, and the
table always showed "No audits yet."

Fix: the route now uses ``require_role_or_persona`` — access by system role OR by
persona_role. Tenant scoping is unchanged.

Authz scope reconciliation (FND-035, lead decision 2026-06-24): two merged PRs set
conflicting persona sets for ``/api/v1/audits``. The canonical set is the reconciled
``_require_audits_list_read`` helper — roles {super_admin, operator, demo_viewer} OR
personas {ai_auditor, compliance_lead} (== TRACE_READ_*), aligning audits-read with
TRACE evidence read (least-privilege). The earlier CHUB set (risk_officer / admin) is
superseded; this test is updated to the canonical set, not weakened.

Pinned behaviourally: the audit/compliance personas and demo_viewer reach the handler
(no 403); a persona outside the canonical set is still rejected with 403.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from auth import get_current_user, require_role_or_persona
from database import get_db
from main import app
from models import User

pytestmark = pytest.mark.regression

_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000025")

_AUDIT_ROLES = ("super_admin", "operator", "demo_viewer")
# Reconciled canonical set (FND-035) — matches routers.scan._require_audits_list_read.
_AUDIT_PERSONAS = ("ai_auditor", "compliance_lead")


def _user(role: str, persona: str | None):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = f"{role}.{persona}@test.example"
    u.role = role
    u.persona_role = persona
    u.tenant_id = _TENANT_ID
    u.is_active = True
    u.read_only = False
    return u


def _db_empty():
    def _dep():
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.outerjoin.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.offset.return_value = q
        q.all.return_value = []
        db.query.return_value = q
        yield db

    return _dep


def _client(role: str, persona: str | None):
    app.dependency_overrides[get_current_user] = lambda: _user(role, persona)
    app.dependency_overrides[get_db] = _db_empty()
    return TestClient(app)


def _clear():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ── Guard-unit level ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_guard_grants_compliance_lead_persona():
    dep = require_role_or_persona(roles=_AUDIT_ROLES, personas=_AUDIT_PERSONAS)
    user = _user("viewer", "compliance_lead")
    assert await dep(user, None) is user  # no raise


@pytest.mark.asyncio
async def test_guard_grants_demo_viewer_role():
    dep = require_role_or_persona(roles=_AUDIT_ROLES, personas=_AUDIT_PERSONAS)
    user = _user("demo_viewer", None)
    assert await dep(user, None) is user


@pytest.mark.asyncio
async def test_guard_denies_unauthorised_role_and_persona():
    dep = require_role_or_persona(roles=_AUDIT_ROLES, personas=_AUDIT_PERSONAS)
    with pytest.raises(HTTPException) as exc:
        # risk_officer is outside the reconciled canonical set (FND-035).
        await dep(_user("viewer", "risk_officer"), None)
    assert exc.value.status_code == 403


# ── Route level — the actual regression ──────────────────────────────────────


@pytest.mark.parametrize(
    "role,persona",
    [
        ("viewer", "compliance_lead"),
        ("viewer", "ai_auditor"),  # reconciled canonical persona (FND-035)
        ("demo_viewer", None),  # regression: demo path preserved
        ("super_admin", None),
    ],
)
def test_audits_readable_by_permitted_role_or_persona(role, persona):
    c = _client(role, persona)
    try:
        r = c.get("/api/v1/audits", headers={"Authorization": "Bearer t"})
        assert r.status_code == 200, (
            f"{role}/{persona} must read audits (FND-025/FND-035); got {r.status_code}"
        )
        assert r.json() == []
    finally:
        _clear()


@pytest.mark.parametrize("persona", ["risk_officer", "admin"])
def test_audits_forbidden_for_persona_outside_canonical_set(persona):
    """Personas outside the reconciled set (FND-035) are rejected — risk_officer/admin
    were in the superseded CHUB set and no longer read audit evidence."""
    c = _client("viewer", persona)
    try:
        r = c.get("/api/v1/audits", headers={"Authorization": "Bearer t"})
        assert r.status_code == 403, (
            f"persona {persona} outside canonical set must 403 on audits; got {r.status_code}"
        )
    finally:
        _clear()
