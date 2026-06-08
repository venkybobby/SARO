"""
LIVE-005: Per-tenant token expiry via ClientConfig.token_expire_minutes
LIVE-006: Slack sales notification on new DemoRequest
"""
from __future__ import annotations

import os
import sys
import uuid
from unittest.mock import MagicMock, patch

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-live005-006")

from fastapi.testclient import TestClient  # noqa: E402
from database import get_db  # noqa: E402
from main import app  # noqa: E402
from models import ClientConfig, DemoRequest, Tenant, User  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_user(tenant_id=None) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "test@example.com"
    u.role = "operator"
    u.persona_role = "compliance_lead"
    u.tenant_id = tenant_id or uuid.uuid4()
    u.is_active = True
    u.hashed_password = None
    return u


def _make_config(token_expire_minutes=None, warning_banner_active=False,
                 allow_magic_link_fallback=False, tenant_id=None) -> MagicMock:
    c = MagicMock(spec=ClientConfig)
    c.tenant_id = tenant_id or uuid.uuid4()
    c.token_expire_minutes = token_expire_minutes
    c.warning_banner_active = warning_banner_active
    c.allow_magic_link_fallback = allow_magic_link_fallback
    return c


def _db_override(user=None, config=None):
    def _inner():
        mock_db = MagicMock()

        def _query(model):
            q = MagicMock()
            name = model.__name__ if hasattr(model, "__name__") else str(model)
            if name == "User":
                q.filter.return_value.first.return_value = user
            elif name == "ClientConfig":
                q.filter.return_value.first.return_value = config
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = _query
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        yield mock_db

    return _inner


# ── LIVE-005 tests ─────────────────────────────────────────────────────────────

class TestLive005TokenExpiry:
    def teardown_method(self, _):
        app.dependency_overrides.pop(get_db, None)

    def test_create_access_token_uses_custom_expire_minutes(self):
        """create_access_token respects expire_minutes override."""
        from auth import create_access_token
        from jose import jwt

        user = _make_user()
        token = create_access_token(user, expire_minutes=120)
        payload = jwt.decode(
            token,
            os.environ["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        import datetime
        exp = datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.timezone.utc)
        iat = datetime.datetime.now(tz=datetime.timezone.utc)
        delta_minutes = (exp - iat).total_seconds() / 60
        # Should be ~120 min (allow ±2 for test execution time)
        assert 118 <= delta_minutes <= 122, f"Expected ~120 min expiry, got {delta_minutes:.1f}"

    def test_create_access_token_default_expire_is_global(self):
        """create_access_token with no override uses ACCESS_TOKEN_EXPIRE_MINUTES."""
        from auth import create_access_token
        from jose import jwt

        user = _make_user()
        with patch.dict(os.environ, {"ACCESS_TOKEN_EXPIRE_MINUTES": "480"}):
            token = create_access_token(user, expire_minutes=None)
        payload = jwt.decode(
            token,
            os.environ["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        import datetime
        exp = datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.timezone.utc)
        iat = datetime.datetime.now(tz=datetime.timezone.utc)
        delta_minutes = (exp - iat).total_seconds() / 60
        assert 478 <= delta_minutes <= 482, f"Expected ~480 min expiry, got {delta_minutes:.1f}"

    def test_login_uses_tenant_token_expire_minutes(self):
        """POST /auth/token uses ClientConfig.token_expire_minutes when set."""
        from jose import jwt

        tenant_id = uuid.uuid4()
        user = _make_user(tenant_id=tenant_id)
        config = _make_config(token_expire_minutes=60, tenant_id=tenant_id)
        app.dependency_overrides[get_db] = _db_override(user=user, config=config)

        # Patch authenticate_user where it is imported in the router module
        with patch("routers.auth.authenticate_user", return_value=user):
            resp = client.post(
                "/api/v1/auth/token",
                json={"email": "test@example.com", "password": "password123"},
            )
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        payload = jwt.decode(
            token,
            os.environ["JWT_SECRET_KEY"],
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        import datetime
        exp = datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.timezone.utc)
        iat = datetime.datetime.now(tz=datetime.timezone.utc)
        delta_minutes = (exp - iat).total_seconds() / 60
        assert 58 <= delta_minutes <= 62, f"Expected ~60 min expiry, got {delta_minutes:.1f}"

    def test_login_uses_global_default_when_no_tenant_config(self):
        """POST /auth/token falls back to global default when ClientConfig absent."""
        user = _make_user()
        app.dependency_overrides[get_db] = _db_override(user=user, config=None)

        with patch("routers.auth.authenticate_user", return_value=user), \
             patch.dict(os.environ, {"ACCESS_TOKEN_EXPIRE_MINUTES": "480"}):
            resp = client.post(
                "/api/v1/auth/token",
                json={"email": "test@example.com", "password": "password123"},
            )
        assert resp.status_code == 200, resp.text


# ── LIVE-006 tests ─────────────────────────────────────────────────────────────

class TestLive006DemoAlert:
    def teardown_method(self, _):
        app.dependency_overrides.pop(get_db, None)

    def _demo_db_override(self, existing=None, new_record=None):
        """DB override for demo signup — supports returning existing or None."""
        captured = []

        def _inner():
            mock_db = MagicMock()

            def _query(model):
                q = MagicMock()
                name = model.__name__ if hasattr(model, "__name__") else str(model)
                if name == "DemoRequest":
                    q.filter.return_value.order_by.return_value.first.return_value = existing
                return q

            def _add(obj):
                captured.append(obj)
                # Give it an id and created_at for the notification service
                if not hasattr(obj, "_mock_name"):
                    obj.id = uuid.uuid4()
                    from datetime import datetime, timezone
                    obj.created_at = datetime.now(tz=timezone.utc)

            mock_db.query.side_effect = _query
            mock_db.add.side_effect = _add
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            yield mock_db

        return _inner, captured

    def test_new_demo_request_fires_background_notification(self):
        """POST /demo/signup triggers Slack notification background task."""
        override, _ = self._demo_db_override(existing=None)
        app.dependency_overrides[get_db] = override

        with patch(
            "services.sales_notification_service.notify_new_demo_request_sync"
        ) as mock_notify:
            resp = client.post(
                "/api/v1/demo/signup",
                json={
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "email": "alice@example.com",
                    "company_name": "Acme Corp",
                },
            )
        assert resp.status_code == 201
        # BackgroundTasks runs synchronously in TestClient
        assert mock_notify.called, "notify_new_demo_request_sync should have been called"

    def test_duplicate_demo_request_does_not_fire_notification(self):
        """Duplicate submissions do not fire a second notification."""
        from datetime import datetime, timezone
        existing = MagicMock(spec=DemoRequest)
        existing.id = uuid.uuid4()
        existing.status = "pending"
        existing.first_name = "Alice"
        existing.last_name = "Smith"
        existing.email = "alice@example.com"
        existing.company_name = "Acme Corp"
        existing.contact_number = None
        existing.message = None
        existing.created_at = datetime.now(tz=timezone.utc)
        existing.updated_at = None

        override, _ = self._demo_db_override(existing=existing)
        app.dependency_overrides[get_db] = override

        with patch(
            "services.sales_notification_service.notify_new_demo_request_sync"
        ) as mock_notify:
            resp = client.post(
                "/api/v1/demo/signup",
                json={
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "email": "alice@example.com",
                    "company_name": "Acme Corp",
                },
            )
        assert resp.status_code in (200, 201)  # route returns 201; duplicate returns existing
        assert not mock_notify.called, "Duplicate should NOT re-notify"

    def test_notify_logs_warning_when_webhook_url_not_set(self):
        """notify_new_demo_request_sync logs a warning when webhook URL is absent."""
        from services.sales_notification_service import notify_new_demo_request_sync

        record = MagicMock(spec=DemoRequest)
        record.id = uuid.uuid4()
        record.first_name = "Bob"
        record.last_name = "Jones"
        record.email = "bob@example.com"
        record.company_name = "Corp"
        record.message = None
        record.created_at = None

        env = {k: v for k, v in os.environ.items() if k != "SARO_SALES_WEBHOOK_URL"}
        with patch.dict(os.environ, env, clear=True), \
             patch("services.sales_notification_service.logger") as mock_log:
            notify_new_demo_request_sync(record)

        mock_log.warning.assert_called()

    def test_notify_sends_slack_when_webhook_url_set(self):
        """notify_new_demo_request_sync POSTs to the Slack webhook URL."""
        from services.sales_notification_service import notify_new_demo_request_sync

        record = MagicMock(spec=DemoRequest)
        record.id = uuid.uuid4()
        record.first_name = "Carol"
        record.last_name = "White"
        record.email = "carol@example.com"
        record.company_name = "BigCo"
        record.message = "Interested in enterprise plan"
        record.created_at = None

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.dict(os.environ, {"SARO_SALES_WEBHOOK_URL": "https://hooks.slack.com/test"}), \
             patch("services.sales_notification_service._requests.post", return_value=mock_resp) as mock_post:
            notify_new_demo_request_sync(record)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "https://hooks.slack.com/test"
