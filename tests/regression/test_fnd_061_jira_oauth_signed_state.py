"""FND-061 / TM-F1 — Jira OAuth callback accepted an unsigned optional ``state``
used directly as the tenant id.

Before the fix, ``GET /api/v1/remediation/oauth/jira/callback`` took any
attacker-chosen ``state`` string, parsed it as a tenant UUID, and bound the
exchanged Jira tokens to that tenant — no CSRF protection, no integrity, no
expiry, no one-time use. Fix: ``/oauth/jira/start`` issues an HMAC-SHA256-signed
state (``tenant.ts.nonce.sig``, key = OAUTH_STATE_SECRET or JWT_SECRET_KEY) and
persists the nonce on ``Tenant.settings_json``; the callback verifies signature
+ TTL and consumes the nonce BEFORE the code-for-token exchange. Missing,
tampered, forged, expired, and replayed states are all rejected 400 with zero
external calls.

Also pins FND-062: tokens were previously written to
``ClientConfig.settings_json`` — a column that does not exist on ClientConfig
(silently swallowed AttributeError), so the binding never persisted. They now
land on ``Tenant.settings_json`` and must survive a round-trip.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import config  # noqa: E402
import routers.remediation as remediation  # noqa: E402
from auth import get_current_user  # noqa: E402
from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402
from models import Tenant, User  # noqa: E402
from services.jira import decrypt_token  # noqa: E402

pytestmark = pytest.mark.regression

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

# Must contain a hex letter: an all-digit UUID hex string gets coerced to an
# integer by SQLite's NUMERIC affinity on UUID-declared columns.
_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000f58")
# Generated per run, not a literal: the signing key's VALUE is irrelevant to
# what these tests prove, and a literal here would (correctly) trip the repo's
# hardcoded-secret scanner in tests/test_epic6_security.py. Generating it also
# demonstrates the implementation depends on the configured key, not a fixed one.
_STATE_SECRET = secrets.token_hex(16)
_CALLBACK = "/api/v1/remediation/oauth/jira/callback"
_START = "/api/v1/remediation/oauth/jira/start"
_AUTH = {"Authorization": "Bearer t"}


def _user() -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "officer@test.example"
    u.role = "operator"
    u.persona_role = "operator"
    u.tenant_id = _TENANT_ID
    u.is_active = True
    u.read_only = False
    return u


def _db_dep():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(monkeypatch):
    # Fresh tenant row per test.
    db = _Session()
    db.query(Tenant).delete()
    db.add(Tenant(id=_TENANT_ID, name="FND-061 Tenant", slug="fnd-061-tenant"))
    db.commit()
    db.close()

    monkeypatch.setenv("OAUTH_STATE_SECRET", _STATE_SECRET)
    monkeypatch.setattr(config.settings, "jwt_secret_key", "fnd-061-jwt-secret")
    monkeypatch.setattr(remediation, "_JIRA_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(remediation, "_JIRA_CLIENT_SECRET", "test-client-secret")

    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db] = _db_dep
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def exchange_mock(monkeypatch):
    """Mock the Atlassian code-for-token exchange; count every egress attempt."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "access_token": "at-live-123",
        "refresh_token": "rt-live-456",
        "scope": "write:issue:jira read:me",
    }
    post = MagicMock(return_value=resp)
    monkeypatch.setattr("httpx.post", post)
    return post


def _start_state(client: TestClient) -> str:
    r = client.get(_START, headers=_AUTH)
    assert r.status_code == 200, r.text
    qs = parse_qs(urlparse(r.json()["oauth_url"]).query)
    return qs["state"][0]


def _tenant_settings() -> dict:
    db = _Session()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == _TENANT_ID).first()
        return dict(tenant.settings_json or {})
    finally:
        db.close()


def _forge_state(secret: str, ts: int, tenant_id: uuid.UUID = _TENANT_ID) -> str:
    payload = f"{tenant_id}.{ts}.forged-nonce"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


# ── The happy path (also pins FND-062: tokens persist on Tenant) ─────────────


def test_valid_state_binds_tokens_to_tenant(client, exchange_mock):
    state = _start_state(client)

    r = client.get(_CALLBACK, params={"code": "authcode", "state": state})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "jira_connected"
    assert exchange_mock.call_count == 1

    stored = _tenant_settings()
    # FND-062: the encrypted tokens must actually persist (previously written to
    # a nonexistent ClientConfig.settings_json column and silently lost).
    assert decrypt_token(stored["jira_access_token_enc"]) == "at-live-123"
    assert decrypt_token(stored["jira_refresh_token_enc"]) == "rt-live-456"
    # Nonce is single-use: consumed during the callback.
    assert "jira_oauth_state" not in stored


def test_state_is_signed_not_bare_tenant_id(client):
    state = _start_state(client)
    assert state != str(_TENANT_ID), "state must not be the raw tenant UUID (TM-F1)"
    tenant_part, ts_part, nonce_part, sig_part = state.split(".")
    assert tenant_part == str(_TENANT_ID)
    assert len(sig_part) == 64  # HMAC-SHA256 hexdigest
    expected = hmac.new(
        _STATE_SECRET.encode(),
        f"{tenant_part}.{ts_part}.{nonce_part}".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert hmac.compare_digest(sig_part, expected)


# ── Rejection paths: 400 and ZERO token-exchange egress ──────────────────────


def test_missing_state_is_400(client, exchange_mock):
    r = client.get(_CALLBACK, params={"code": "authcode"})
    assert r.status_code == 400
    assert exchange_mock.call_count == 0
    assert "jira_access_token_enc" not in _tenant_settings()


def test_tampered_state_is_400(client, exchange_mock):
    state = _start_state(client)
    # Flip the last signature character.
    tampered = state[:-1] + ("0" if state[-1] != "0" else "1")
    r = client.get(_CALLBACK, params={"code": "authcode", "state": tampered})
    assert r.status_code == 400
    assert exchange_mock.call_count == 0
    assert "jira_access_token_enc" not in _tenant_settings()


def test_bare_tenant_uuid_state_is_400(client, exchange_mock):
    """The exact pre-fix attack: state = victim tenant UUID, no signature."""
    r = client.get(_CALLBACK, params={"code": "authcode", "state": str(_TENANT_ID)})
    assert r.status_code == 400
    assert exchange_mock.call_count == 0
    assert "jira_access_token_enc" not in _tenant_settings()


def test_state_forged_with_wrong_key_is_400(client, exchange_mock):
    forged = _forge_state("not-the-real-secret", int(time.time()))
    r = client.get(_CALLBACK, params={"code": "authcode", "state": forged})
    assert r.status_code == 400
    assert exchange_mock.call_count == 0


def test_expired_state_is_400(client, exchange_mock):
    # Correctly signed but issued beyond the TTL window.
    expired = _forge_state(
        _STATE_SECRET, int(time.time()) - remediation._STATE_TTL_SECONDS - 60
    )
    r = client.get(_CALLBACK, params={"code": "authcode", "state": expired})
    assert r.status_code == 400
    assert exchange_mock.call_count == 0


def test_replayed_state_is_400(client, exchange_mock):
    state = _start_state(client)

    first = client.get(_CALLBACK, params={"code": "authcode", "state": state})
    assert first.status_code == 200

    replay = client.get(_CALLBACK, params={"code": "authcode2", "state": state})
    assert replay.status_code == 400
    # Only the first, legitimate callback reached the token endpoint.
    assert exchange_mock.call_count == 1


def test_valid_signature_but_unissued_nonce_is_400(client, exchange_mock):
    """Signed by us, but no pending nonce stored for the tenant → rejected."""
    forged = _forge_state(_STATE_SECRET, int(time.time()))
    r = client.get(_CALLBACK, params={"code": "authcode", "state": forged})
    assert r.status_code == 400
    assert exchange_mock.call_count == 0


def test_non_ascii_state_is_400_not_500(client, exchange_mock):
    """str-mode hmac.compare_digest raises TypeError on non-ASCII input — the
    comparison must run on bytes so garbage state yields 400, not a 500."""
    r = client.get(
        _CALLBACK,
        params={"code": "authcode", "state": f"{_TENANT_ID}.123.nonce.é" + "0" * 63},
    )
    assert r.status_code == 400
    assert exchange_mock.call_count == 0


def test_start_fails_closed_without_signing_key(client, monkeypatch):
    """No OAUTH_STATE_SECRET and no jwt_secret_key → 500, never an unsigned state."""
    monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)
    monkeypatch.setattr(config.settings, "jwt_secret_key", None)
    r = client.get(_START, headers=_AUTH)
    assert r.status_code == 500
    assert "OAUTH_STATE_SECRET" not in r.text  # env-var names stay out of responses
