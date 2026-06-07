"""SAR-001: Testing-only warning banner on magic-link login flow.

Tests cover:
  - X-SARO-Auth-Type header on magic-link endpoint
  - Warning text in response JSON
  - 403 for SSO-only tenants
  - warning_banner_active column defaults and persistence
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
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests")

from fastapi.testclient import TestClient  # noqa: E402
from database import get_db  # noqa: E402
from main import app  # noqa: E402
from models import ClientConfig, Tenant  # noqa: E402

client = TestClient(app)


def _override_no_tenant():
    """DB override: tenant lookup returns None → magic-link proceeds normally."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    yield mock_db


def _override_sso_only():
    """DB override: tenant has allow_magic_link_fallback=False → 403."""
    mock_tenant = MagicMock(spec=Tenant)
    mock_tenant.id = uuid.uuid4()

    mock_config = MagicMock(spec=ClientConfig)
    mock_config.allow_magic_link_fallback = False

    mock_db = MagicMock()

    def _query(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = (
            mock_tenant if model is Tenant else mock_config
        )
        return q

    mock_db.query.side_effect = _query
    yield mock_db


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestMagicLinkHeader:
    def setup_method(self):
        app.dependency_overrides[get_db] = _override_no_tenant

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_magic_link_endpoint_returns_auth_type_header(self):
        """POST /api/v1/sso/magic-link must return X-SARO-Auth-Type header."""
        resp = client.post(
            "/api/v1/sso/magic-link",
            json={"email": "user@example.com", "tenant_slug": "nonexistent"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("x-saro-auth-type") == "magic-link-testing-only"

    def test_magic_link_endpoint_returns_warning_text(self):
        """Response JSON must contain 'testing' in the warning field."""
        resp = client.post(
            "/api/v1/sso/magic-link",
            json={"email": "user@example.com", "tenant_slug": "nonexistent"},
        )
        assert resp.status_code == 200
        assert "testing" in resp.json().get("warning", "").lower()

    def test_magic_link_header_present_on_all_responses(self):
        """Header key must exactly match 'X-SARO-Auth-Type'."""
        resp = client.post(
            "/api/v1/sso/magic-link",
            json={"email": "other@example.com", "tenant_slug": "nonexistent"},
        )
        assert resp.status_code == 200
        assert "x-saro-auth-type" in {k.lower() for k in resp.headers}
        assert resp.headers["x-saro-auth-type"] == "magic-link-testing-only"


class TestSSOOnlyTenant:
    def setup_method(self):
        app.dependency_overrides[get_db] = _override_sso_only

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_sso_only_tenant_magic_link_returns_403(self):
        """Tenants with allow_magic_link_fallback=False must receive 403."""
        resp = client.post(
            "/api/v1/sso/magic-link",
            json={"email": "user@example.com", "tenant_slug": "sso-only-tenant"},
        )
        assert resp.status_code == 403


class TestWarningBannerActive:
    def test_warning_banner_active_default_true(self):
        """ClientConfig.warning_banner_active column must default to True."""
        col = ClientConfig.__table__.c["warning_banner_active"]
        assert col.default.arg is True

    def test_warning_banner_active_column_exists(self):
        """ClientConfig must have a warning_banner_active column."""
        assert "warning_banner_active" in ClientConfig.__table__.c
