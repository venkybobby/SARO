"""FND-009 (PT-009): insight/risk write authz is an ALLOWLIST, not a denylist.

Root cause: ``record_insight_action`` denied only ai_auditor; persona_role is
nullable, so NULL or any future persona defaulted to write access. Fixed by
``auth.require_write_persona`` — write is granted only to an explicit set.
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from auth import require_write_persona

pytestmark = pytest.mark.regression

_REQ = SimpleNamespace(url=SimpleNamespace(path="/api/v1/insights/x/action"))


def _user(*, role="operator", persona=None, read_only=False):
    return SimpleNamespace(
        id="u", tenant_id="t", role=role, persona_role=persona, read_only=read_only
    )


def _call(user):
    return asyncio.run(require_write_persona(user, _REQ))


def _denied(user):
    with pytest.raises(HTTPException) as exc:
        _call(user)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("persona", ["compliance_lead", "risk_officer", "admin"])
def test_write_personas_allowed(persona):
    assert _call(_user(role="admin", persona=persona)) is not None


def test_ai_auditor_denied():
    _denied(_user(role="admin", persona="ai_auditor"))


def test_null_persona_non_system_role_denied():
    # The exact regression: nullable persona must NOT default to write.
    _denied(_user(role="member", persona=None))


def test_unknown_future_persona_denied():
    _denied(_user(role="member", persona="data_scientist_2027"))


def test_read_only_denied_even_with_write_persona():
    _denied(_user(role="admin", persona="compliance_lead", read_only=True))


def test_system_roles_without_persona_allowed():
    assert _call(_user(role="super_admin", persona=None)) is not None
    assert _call(_user(role="operator", persona=None)) is not None
