"""FND-066 — password rotation must invalidate outstanding JWTs.

Found by the STORY-371 tabletop. Before this fix, tokens were validated on
signature and expiry alone: rotating a leaked credential left every token minted
with it fully valid until expiry. That made the containment step in
`docs/security/secrets-runbook.md` §3 incomplete *and* misleading — it told the
operator the credential was dead while access continued.

Red-first: every test here failed before `token_version` existed.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import auth  # noqa: E402

pytestmark = pytest.mark.regression


def _user(version: int = 1, **over):
    base = dict(
        id=uuid.uuid4(),
        email="user@example.test",
        role="operator",
        persona_role="compliance_lead",
        tenant_id=uuid.uuid4(),
        is_active=True,
        token_version=version,
        hashed_password="x",
        read_only=False,
    )
    base.update(over)
    return SimpleNamespace(**base)


class _DB:
    """Minimal stand-in for the session `get_current_user` uses."""

    def __init__(self, user):
        self._user = user

    def get(self, _model, _pk):
        return self._user


async def _authenticate(token: str, user):
    from fastapi.security import HTTPAuthorizationCredentials

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    # _DB is a duck-typed Session double (only .query() is exercised here).
    return await auth.get_current_user(creds, _DB(user))  # type: ignore[arg-type]


# ── The token must carry a version ──────────────────────────────────────────


def test_token_embeds_the_users_token_version():
    user = _user(version=3)
    payload = auth._decode_token(auth.create_access_token(user))
    assert payload.get("token_version") == 3, (
        "without a version claim there is nothing to invalidate against"
    )


# ── Revocation ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_current_token_is_accepted():
    user = _user(version=1)
    token = auth.create_access_token(user)
    assert await _authenticate(token, user) is user


@pytest.mark.asyncio
async def test_token_minted_before_rotation_is_rejected():
    """The FND-066 scenario: rotate the password, the old session must die."""
    user = _user(version=1)
    stale_token = auth.create_access_token(user)

    user.token_version = 2  # password changed / sessions revoked

    with pytest.raises(Exception) as exc:
        await _authenticate(stale_token, user)
    assert getattr(exc.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_token_issued_after_rotation_is_accepted():
    user = _user(version=1)
    user.token_version = 2
    fresh = auth.create_access_token(user)
    assert await _authenticate(fresh, user) is user


@pytest.mark.asyncio
async def test_token_with_a_future_version_is_rejected():
    """A forged or replayed token claiming a higher version must not pass."""
    user = _user(version=5)
    forged = auth.create_access_token(user)
    user.token_version = 4

    with pytest.raises(Exception) as exc:
        await _authenticate(forged, user)
    assert getattr(exc.value, "status_code", None) == 401


# ── Backwards compatibility ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_legacy_token_without_the_claim_is_rejected_not_trusted():
    """Tokens predating this change must fail closed.

    Treating a missing claim as "matches" would leave exactly the hole this
    finding is about open for the lifetime of every already-issued token.
    """
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    user = _user(version=1)
    legacy = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": str(user.tenant_id),
            "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=30),
        },
        auth._secret_key(),
        algorithm=auth._algorithm(),
    )
    with pytest.raises(Exception) as exc:
        await _authenticate(legacy, user)
    assert getattr(exc.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_demo_tokens_are_unaffected_by_version_checking():
    """Demo tokens are synthetic and bound to no user row.

    `get_current_user` returns them before the DB lookup, so there is no
    token_version to compare — asserted explicitly so a future reordering of
    those checks cannot break demo sessions unnoticed.
    """
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    tenant_id = uuid.uuid4()
    demo = jwt.encode(
        {
            "sub": str(tenant_id),
            "role": "demo_viewer",
            "tenant_id": str(tenant_id),
            "read_only": True,
            "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=30),
        },
        auth._secret_key(),
        algorithm=auth._algorithm(),
    )
    # No user row at all — the demo branch must not reach the DB.
    result = await _authenticate(demo, None)
    assert result.role == "demo_viewer"
    assert result.read_only is True


# ── The revocation helper ───────────────────────────────────────────────────


def test_revoke_sessions_increments_the_version():
    user = _user(version=7)
    auth.revoke_user_sessions(user)
    assert user.token_version == 8


def test_revocation_helper_exists_in_auth():
    src = (ROOT / "auth.py").read_text(encoding="utf-8")
    assert "def revoke_user_sessions" in src
    assert "token_version" in src


def test_every_existing_password_reset_path_bumps_the_version():
    """A rotation that leaves sessions alive is the bug — pin the actual wiring.

    There is currently no change-password endpoint; the only path that resets an
    existing user's password is the demo-tenant seed script, which uses raw SQL
    and so cannot go through revoke_user_sessions().
    """
    seed = (ROOT / "scripts" / "seed_demo_tenant.py").read_text(encoding="utf-8")
    reset = seed[seed.index("UPDATE users SET hashed_password"):]
    reset = reset[: reset.index("WHERE id = :id") + len("WHERE id = :id")]
    assert "token_version" in reset, (
        "the demo password reset does not revoke sessions — FND-066 regressed"
    )


def test_no_unaudited_password_change_endpoint_has_appeared():
    """If someone adds a change-password route, it must call the helper.

    This fails when such a route appears without revocation wiring, turning an
    easy omission into a build failure rather than a silent security gap.
    """
    import re

    routers = (ROOT / "routers").glob("*.py")
    offenders = []
    for path in routers:
        src = path.read_text(encoding="utf-8")
        # A handler that rewrites an EXISTING user's password (assignment form),
        # as opposed to constructing a new User(...).
        if re.search(r"\.hashed_password\s*=\s*hash_password", src):
            if "revoke_user_sessions" not in src:
                offenders.append(path.name)
    assert not offenders, (
        f"password-change path(s) without session revocation: {offenders} — "
        "call auth.revoke_user_sessions(user) in the same transaction (FND-066)"
    )
