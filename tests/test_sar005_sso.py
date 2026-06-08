"""
SAR-005: SAML 2.0 SSO endpoint tests.

Covers: metadata, login redirect, ACS (valid/invalid/expired/mfa),
magic-link guard, and the sso-setup.md doc file.

Uses app.dependency_overrides[get_db] with MagicMock sessions — no SQLite.
"""
from __future__ import annotations

import base64
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-sar005")

from database import get_db  # noqa: E402
from main import app  # noqa: E402
from models import ClientConfig, Tenant, User  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_tenant(slug: str = "test-tenant") -> MagicMock:
    t = MagicMock(spec=Tenant)
    t.id = uuid.uuid4()
    t.slug = slug
    return t


def _make_mock_config(
    sso_enabled: bool = True,
    idp_metadata: dict | None = None,
    mfa_required: bool = False,
    allow_magic_link_fallback: bool = True,
) -> MagicMock:
    c = MagicMock(spec=ClientConfig)
    c.sso_enabled = sso_enabled
    c.idp_metadata = idp_metadata or {"sso_url": "https://idp.example.com/sso"}
    c.mfa_required = mfa_required
    c.allow_magic_link_fallback = allow_magic_link_fallback
    return c


def _make_mock_user(email: str = "user@test.com", tenant_id=None) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = email
    u.persona_role = "compliance_lead"
    u.tenant_id = tenant_id or uuid.uuid4()
    return u


def _override_db(tenant=None, config=None, user=None):
    """Build a get_db override that returns a fully-mocked session."""
    def _inner():
        mock_db = MagicMock()

        def _query(model):
            q = MagicMock()
            name = model.__name__ if hasattr(model, "__name__") else str(model)
            if name == "Tenant":
                q.filter.return_value.first.return_value = tenant
            elif name == "ClientConfig":
                q.filter.return_value.first.return_value = config
            elif name == "User":
                q.filter.return_value.first.return_value = user
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = _query
        mock_db.add.return_value = None
        mock_db.commit.return_value = None

        # db.refresh(user) should set id/email/persona_role on the object
        def _refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db.refresh.side_effect = _refresh
        yield mock_db

    return _inner


def _make_saml_response(
    with_signature: bool = True,
    expired: bool = False,
    with_mfa: bool = False,
    email: str = "user@test.com",
    assertion_id: str | None = None,
) -> str:
    not_after = "2099-01-01T00:00:00Z" if not expired else "2020-01-01T00:00:00Z"
    sig = (
        "<ds:Signature xmlns:ds='http://www.w3.org/2000/09/xmldsig#'>"
        "<placeholder/></ds:Signature>"
        if with_signature
        else ""
    )
    mfa = (
        "<saml:AuthnContextClassRef>"
        "urn:oasis:names:tc:SAML:2.0:ac:classes:MobileTwoFactorContract"
        "</saml:AuthnContextClassRef>"
        if with_mfa
        else ""
    )
    id_attr = f' ID="{assertion_id}"' if assertion_id else ""
    xml = f"""<?xml version="1.0"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
  {sig}
  <saml:Assertion{id_attr}>
    <saml:Subject>
      <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{email}</saml:NameID>
    </saml:Subject>
    <saml:Conditions NotOnOrAfter="{not_after}"/>
    <saml:AuthnStatement><saml:AuthnContext>{mfa}</saml:AuthnContext></saml:AuthnStatement>
  </saml:Assertion>
</samlp:Response>"""
    return base64.b64encode(xml.encode()).decode()


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestSar005Sso:
    def teardown_method(self, _method):
        app.dependency_overrides.pop(get_db, None)

    # 1 — metadata returns XML with EntityDescriptor
    def test_saml_metadata_endpoint_returns_xml(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config()
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config)

        resp = client.get("/api/v1/sso/metadata/test-tenant")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "xml" in ct
        assert "EntityDescriptor" in resp.text

    # 2 — login redirects to IdP with SAMLRequest
    def test_sso_login_redirects_to_idp(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config(idp_metadata={"sso_url": "https://idp.example.com/sso"})
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config)

        resp = client.get("/api/v1/sso/login/test-tenant", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "SAMLRequest" in location

    # 3 — login returns 400 if sso not enabled
    def test_sso_login_returns_400_if_sso_not_enabled(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config(sso_enabled=False)
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config)

        resp = client.get("/api/v1/sso/login/test-tenant")
        assert resp.status_code == 400

    # 4 — login returns 404 if tenant not found
    def test_sso_login_returns_404_if_tenant_not_found(self):
        app.dependency_overrides[get_db] = _override_db(tenant=None)

        resp = client.get("/api/v1/sso/login/nonexistent")
        assert resp.status_code == 404

    # 5 — valid SAML assertion issues JWT
    def test_valid_saml_assertion_issues_jwt(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config()
        user = _make_mock_user(tenant_id=tenant.id)
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config, user=user)

        saml = _make_saml_response(with_signature=True)
        with patch("routers.sso.create_access_token", return_value="mock-jwt-token"):
            resp = client.post(
                "/api/v1/sso/acs/test-tenant",
                data={"SAMLResponse": saml},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body

    # 6 — missing signature returns 400
    def test_invalid_signature_returns_400(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config()
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config)

        saml = _make_saml_response(with_signature=False)
        with patch("routers.sso.create_access_token", return_value="mock-jwt-token"):
            resp = client.post(
                "/api/v1/sso/acs/test-tenant",
                data={"SAMLResponse": saml},
            )
        assert resp.status_code == 400

    # 7 — expired assertion returns 400
    def test_expired_assertion_returns_400(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config()
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config)

        saml = _make_saml_response(with_signature=True, expired=True)
        with patch("routers.sso.create_access_token", return_value="mock-jwt-token"):
            resp = client.post(
                "/api/v1/sso/acs/test-tenant",
                data={"SAMLResponse": saml},
            )
        assert resp.status_code == 400

    # 8 — magic link disabled returns 403
    def test_magic_link_disabled_returns_403_for_sso_tenant(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config(allow_magic_link_fallback=False)
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config)

        resp = client.post(
            "/api/v1/sso/magic-link",
            json={"email": "user@test.com", "tenant_slug": "test-tenant"},
        )
        assert resp.status_code == 403

    # 9 — magic link returns 200 when no tenant found
    def test_magic_link_returns_200_when_no_tenant_found(self):
        app.dependency_overrides[get_db] = _override_db(tenant=None)

        resp = client.post(
            "/api/v1/sso/magic-link",
            json={"email": "user@test.com", "tenant_slug": "unknown-tenant"},
        )
        assert resp.status_code == 200

    # 10 — mfa_required without MFA claim returns 401
    def test_mfa_required_returns_401_without_mfa_claim(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config(mfa_required=True)
        user = _make_mock_user(tenant_id=tenant.id)
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config, user=user)

        saml = _make_saml_response(with_signature=True, with_mfa=False)
        with patch("routers.sso.create_access_token", return_value="mock-jwt-token"):
            resp = client.post(
                "/api/v1/sso/acs/test-tenant",
                data={"SAMLResponse": saml},
            )
        assert resp.status_code == 401

    # 11 — metadata includes AssertionConsumerService
    def test_saml_metadata_includes_acs_url(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config()
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config)

        resp = client.get("/api/v1/sso/metadata/test-tenant")
        assert resp.status_code == 200
        assert "AssertionConsumerService" in resp.text

    # 12 — sso-setup.md doc file exists
    def test_sso_docs_file_exists(self):
        assert Path(_REPO_ROOT, "docs", "sso-setup.md").exists()

    # 13 — magic-link response carries X-SARO-Auth-Type header
    def test_magic_link_response_has_auth_type_header(self):
        app.dependency_overrides[get_db] = _override_db(tenant=None)

        resp = client.post(
            "/api/v1/sso/magic-link",
            json={"email": "user@test.com", "tenant_slug": "no-tenant"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("x-saro-auth-type") == "magic-link-testing-only"

    # LIVE-008: replay guard — second use of same assertion_id returns 400
    def test_replay_attack_returns_400(self):
        from routers.sso import _SEEN_ASSERTION_IDS  # type: ignore[attr-defined]

        tenant = _make_mock_tenant()
        config = _make_mock_config()
        user = _make_mock_user(tenant_id=tenant.id)

        # Use a unique assertion ID so this test is isolated from others
        aid = f"_test_replay_{uuid.uuid4().hex}"
        # Clear any leftover state for this ID
        _SEEN_ASSERTION_IDS.pop(aid, None)

        saml = _make_saml_response(with_signature=True, assertion_id=aid)

        with patch("routers.sso.create_access_token", return_value="mock-jwt-token"):
            # First use — should succeed
            app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config, user=user)
            r1 = client.post("/api/v1/sso/acs/test-tenant", data={"SAMLResponse": saml})
            assert r1.status_code == 200, f"First use should succeed, got {r1.status_code}: {r1.text}"

            # Second use with the same assertion — must be rejected
            app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config, user=user)
            r2 = client.post("/api/v1/sso/acs/test-tenant", data={"SAMLResponse": saml})
            assert r2.status_code == 400, f"Replay should be rejected, got {r2.status_code}: {r2.text}"
            assert "replay" in r2.json().get("detail", "").lower()

    # LIVE-008: unsigned assertion is still rejected (presence check intact)
    def test_unsigned_assertion_still_rejected(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config()
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config)

        saml = _make_saml_response(with_signature=False)
        resp = client.post("/api/v1/sso/acs/test-tenant", data={"SAMLResponse": saml})
        assert resp.status_code == 400

    # LIVE-008: SSO JIT user is created with hashed_password=None (LIVE-002 compat)
    def test_sso_jit_user_created_with_null_password(self):
        tenant = _make_mock_tenant()
        config = _make_mock_config()
        app.dependency_overrides[get_db] = _override_db(tenant=tenant, config=config, user=None)

        captured_users: list = []

        def _capturing_override():
            mock_db = MagicMock()

            def _query(model):
                q = MagicMock()
                name = model.__name__ if hasattr(model, "__name__") else str(model)
                if name == "Tenant":
                    q.filter.return_value.first.return_value = tenant
                elif name == "ClientConfig":
                    q.filter.return_value.first.return_value = config
                elif name == "User":
                    q.filter.return_value.first.return_value = None  # force JIT
                else:
                    q.filter.return_value.first.return_value = None
                return q

            def _add(obj):
                captured_users.append(obj)

            mock_db.query.side_effect = _query
            mock_db.add.side_effect = _add
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            yield mock_db

        app.dependency_overrides[get_db] = _capturing_override
        saml = _make_saml_response(with_signature=True)

        with patch("routers.sso.create_access_token", return_value="mock-jwt"):
            client.post("/api/v1/sso/acs/test-tenant", data={"SAMLResponse": saml})

        user_rows = [u for u in captured_users if hasattr(u, "hashed_password")]
        assert user_rows, "Expected a User to be added via db.add()"
        assert user_rows[0].hashed_password is None, (
            f"SSO JIT user should have hashed_password=None, got {user_rows[0].hashed_password!r}"
        )
